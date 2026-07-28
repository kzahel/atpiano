"""Bounded local WAV/MP3 upload spooling and sample-indexed decoding."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from atpiano.live import MAX_PCM_BLOCK_FRAMES, PcmBlock
from atpiano.util import utc_now

UPLOAD_SCHEMA = "atpiano.recording-upload.v1"
MAX_RECORDING_UPLOAD_BYTES = 2 * 1024**3
UPLOAD_SPOOL_MAX_AGE_S = 24 * 60 * 60
UPLOAD_BLOCK_FRAMES = 16_384
UPLOAD_DIRECTORY_NAME = ".recording-imports"
_SUPPORTED_SUFFIXES = {".wav", ".mp3"}
_SUPPORTED_MEDIA_TYPES = {
    "application/octet-stream",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
}


def normalized_upload_filename(value: str) -> str:
    """Return a display-only basename without accepting path semantics."""

    normalized = value.strip().replace("\\", "/").rsplit("/", 1)[-1]
    if (
        not normalized
        or len(normalized) > 255
        or any(ord(character) < 32 for character in normalized)
        or Path(normalized).suffix.lower() not in _SUPPORTED_SUFFIXES
    ):
        raise ValueError("recording filename must end in .wav or .mp3")
    return normalized


def normalized_upload_media_type(value: str) -> str:
    normalized = value.split(";", 1)[0].strip().lower()
    if normalized not in _SUPPORTED_MEDIA_TYPES:
        raise ValueError("recording must be a WAV or MP3 file")
    return normalized


class LocalUploadSource:
    """Validated upload decoded to contiguous mono PCM16 blocks."""

    def __init__(
        self,
        path: Path,
        *,
        filename: str,
        media_type: str,
        byte_count: int,
        sha256: str,
        ffmpeg_executable: str,
        ffprobe_executable: str,
        block_frames: int = UPLOAD_BLOCK_FRAMES,
        popen: Callable[..., Any] = subprocess.Popen,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        if not 0 < block_frames <= MAX_PCM_BLOCK_FRAMES:
            raise ValueError("recording decode block size is invalid")
        self.path = path.resolve()
        self.filename = normalized_upload_filename(filename)
        self.media_type = normalized_upload_media_type(media_type)
        self.byte_count = byte_count
        self.sha256 = sha256
        self.ffmpeg_executable = ffmpeg_executable
        self.ffprobe_executable = ffprobe_executable
        self.block_frames = block_frames
        self._popen = popen
        self._runner = runner
        if (
            not self.path.is_file()
            or self.path.stat().st_size != byte_count
            or not 0 < byte_count <= MAX_RECORDING_UPLOAD_BYTES
        ):
            raise ValueError("recording upload size is invalid")
        probe = self._probe()
        self.sample_rate_hz = int(probe["sample_rate"])
        if not 8_000 <= self.sample_rate_hz <= 384_000:
            raise ValueError("recording sample rate is unsupported")
        self.source_codec = str(probe.get("codec_name") or "unknown")
        self.source_channels = int(probe["channels"])
        if not 1 <= self.source_channels <= 64:
            raise ValueError("recording channel count is unsupported")
        self.source_format = str(probe.get("format_name") or "unknown")

    def _probe(self) -> dict[str, Any]:
        try:
            result = self._runner(
                [
                    self.ffprobe_executable,
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name,sample_rate,channels",
                    "-show_entries",
                    "format=format_name",
                    "-of",
                    "json",
                    str(self.path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            document = json.loads(result.stdout)
        except (
            OSError,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError(
                "recording could not be read as WAV or MP3"
            ) from error
        streams = document.get("streams")
        if not isinstance(streams, list) or len(streams) != 1:
            raise ValueError("recording must contain one readable audio stream")
        stream = streams[0]
        if not isinstance(stream, dict):
            raise ValueError("recording audio metadata is invalid")
        source_format = document.get("format")
        return {
            **stream,
            "format_name": (
                source_format.get("format_name")
                if isinstance(source_format, dict)
                else None
            ),
        }

    def provenance(
        self,
        *,
        state: str,
        decoded_frame_count: int = 0,
        decoded_block_count: int = 0,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": UPLOAD_SCHEMA,
            "state": state,
            "updated_at": utc_now(),
            "original": {
                "filename": self.filename,
                "media_type": self.media_type,
                "byte_count": self.byte_count,
                "sha256": self.sha256,
            },
            "detected": {
                "format": self.source_format,
                "codec": self.source_codec,
                "sample_rate_hz": self.sample_rate_hz,
                "channel_count": self.source_channels,
            },
            "decode": {
                "sample_format": "pcm-s16le",
                "channel_count": 1,
                "downmix": (
                    "none" if self.source_channels == 1 else "ffmpeg-default"
                ),
                "frame_count": decoded_frame_count,
                "block_count": decoded_block_count,
            },
            "error": error,
        }

    def stream(
        self,
        *,
        accept: Callable[[PcmBlock, int], None],
    ) -> tuple[int, int]:
        sequence = 0
        source_head = 0
        block_bytes = self.block_frames * 2
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024) as error_output:
            process = self._popen(
                [
                    self.ffmpeg_executable,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-xerror",
                    "-nostdin",
                    "-i",
                    str(self.path),
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    str(self.sample_rate_hz),
                    "-f",
                    "s16le",
                    "-acodec",
                    "pcm_s16le",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=error_output,
            )
            if process.stdout is None:
                process.kill()
                raise RuntimeError("recording decoder did not provide PCM")
            pending = b""
            try:
                while True:
                    chunk = process.stdout.read(block_bytes - len(pending))
                    if not chunk:
                        break
                    pending += chunk
                    if len(pending) < block_bytes:
                        continue
                    source_head, sequence = self._accept_pcm(
                        pending,
                        source_head=source_head,
                        sequence=sequence,
                        accept=accept,
                    )
                    pending = b""
                if len(pending) % 2:
                    raise ValueError("recording decoder returned partial PCM")
                if pending:
                    source_head, sequence = self._accept_pcm(
                        pending,
                        source_head=source_head,
                        sequence=sequence,
                        accept=accept,
                    )
                return_code = process.wait()
                if return_code != 0:
                    error_output.seek(0)
                    detail = error_output.read(4096).decode(
                        "utf-8",
                        errors="replace",
                    ).strip()
                    raise ValueError(
                        detail or "recording could not be decoded"
                    )
                if source_head == 0:
                    raise ValueError("recording contains no audio frames")
                return source_head, sequence
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            finally:
                process.stdout.close()
    def _accept_pcm(
        self,
        pcm: bytes,
        *,
        source_head: int,
        sequence: int,
        accept: Callable[[PcmBlock, int], None],
    ) -> tuple[int, int]:
        frame_count = len(pcm) // 2
        source_end = source_head + frame_count
        accept(
            PcmBlock(
                sequence=sequence,
                first_sample=source_head,
                frame_count=frame_count,
                sample_rate_hz=self.sample_rate_hz,
                page_sent_ms=source_end / self.sample_rate_hz * 1000,
                worklet_time_s=source_end / self.sample_rate_hz,
                pcm_s16le=pcm,
            ),
            time.perf_counter_ns(),
        )
        return source_end, sequence + 1

    def close(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class LocalRecordingUploadAdapter:
    """Own known upload spools and prepare validated decoder sources."""

    def __init__(
        self,
        workspace_directory: Path,
        *,
        minimum_free_bytes: int,
        ffmpeg_executable: str | None = None,
        ffprobe_executable: str | None = None,
    ) -> None:
        self.workspace_directory = workspace_directory.resolve()
        self.spool_directory = (
            self.workspace_directory / UPLOAD_DIRECTORY_NAME
        ).resolve()
        self.minimum_free_bytes = minimum_free_bytes
        self.ffmpeg_executable = (
            ffmpeg_executable
            if ffmpeg_executable is not None
            else shutil.which("ffmpeg")
        )
        self.ffprobe_executable = (
            ffprobe_executable
            if ffprobe_executable is not None
            else shutil.which("ffprobe")
        )
        self.spool_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cleanup_stale()

    @property
    def available(self) -> bool:
        return (
            self.ffmpeg_executable is not None
            and self.ffprobe_executable is not None
        )

    def validate_request(
        self,
        *,
        filename: str,
        media_type: str,
        byte_count: int,
    ) -> tuple[str, str]:
        if not self.available:
            raise RuntimeError("recording import is unavailable")
        normalized_filename = normalized_upload_filename(filename)
        normalized_media_type = normalized_upload_media_type(media_type)
        if not 0 < byte_count <= MAX_RECORDING_UPLOAD_BYTES:
            raise ValueError("recording upload size is invalid")
        free_bytes = shutil.disk_usage(self.workspace_directory).free
        if free_bytes - byte_count < self.minimum_free_bytes:
            raise OSError("recording upload would cross the free-space reserve")
        return normalized_filename, normalized_media_type

    def new_spool_path(self) -> Path:
        return self.spool_directory / f"{uuid.uuid4().hex}.part"

    @staticmethod
    def write_spool(
        path: Path,
        chunks: Iterable[bytes],
        *,
        expected_bytes: int,
    ) -> tuple[int, str]:
        digest = hashlib.sha256()
        received = 0
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                for chunk in chunks:
                    if not chunk:
                        continue
                    received += len(chunk)
                    if received > expected_bytes:
                        raise ValueError(
                            "recording body exceeds Content-Length"
                        )
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise
        if received != expected_bytes:
            path.unlink()
            raise ValueError("recording body is truncated")
        return received, digest.hexdigest()

    def prepare(
        self,
        path: Path,
        *,
        filename: str,
        media_type: str,
        byte_count: int,
        sha256: str,
    ) -> LocalUploadSource:
        if self.ffmpeg_executable is None or self.ffprobe_executable is None:
            raise RuntimeError("recording import is unavailable")
        return LocalUploadSource(
            path,
            filename=filename,
            media_type=media_type,
            byte_count=byte_count,
            sha256=sha256,
            ffmpeg_executable=self.ffmpeg_executable,
            ffprobe_executable=self.ffprobe_executable,
        )

    def cleanup_stale(self) -> None:
        threshold = time.time() - UPLOAD_SPOOL_MAX_AGE_S
        for path in self.spool_directory.glob("*.part"):
            try:
                if path.is_file() and path.stat().st_mtime < threshold:
                    path.unlink()
            except FileNotFoundError:
                pass
