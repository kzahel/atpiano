"""Sample-indexed live browser transport and capture artifacts."""

from __future__ import annotations

import json
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atpiano.capture import BROWSER_CAPTURE_SCHEMA, write_browser_capture_artifacts
from atpiano.util import sha256_file, utc_now, write_json, write_jsonl

LIVE_STREAM_SCHEMA = "atpiano.live-stream.v1"
LIVE_SESSION_SCHEMA = "atpiano.live-session.v1"
PCM_BLOCK_MAGIC = b"ATPB"
PCM_BLOCK_VERSION = 1
PCM_BLOCK_KIND_AUDIO = 1
PCM_BLOCK_HEADER = struct.Struct("<4sBBHIIQII2d")
PCM_BLOCK_HEADER_BYTES = PCM_BLOCK_HEADER.size
MAX_PCM_BLOCK_FRAMES = 16_384
MAX_LIVE_SECONDS = 120


@dataclass(frozen=True)
class PcmBlock:
    sequence: int
    first_sample: int
    frame_count: int
    sample_rate_hz: int
    page_sent_ms: float
    worklet_time_s: float
    pcm_s16le: bytes


def parse_pcm_block(data: bytes) -> PcmBlock:
    """Parse and validate one versioned mono PCM16 browser block."""
    if len(data) < PCM_BLOCK_HEADER_BYTES:
        raise ValueError("live PCM block is shorter than its header")
    (
        magic,
        version,
        kind,
        header_bytes,
        sequence,
        flags,
        first_sample,
        frame_count,
        sample_rate_hz,
        page_sent_ms,
        worklet_time_s,
    ) = PCM_BLOCK_HEADER.unpack_from(data)
    if magic != PCM_BLOCK_MAGIC:
        raise ValueError("live PCM block has invalid magic")
    if version != PCM_BLOCK_VERSION or kind != PCM_BLOCK_KIND_AUDIO:
        raise ValueError("live PCM block has an unsupported version or kind")
    if header_bytes != PCM_BLOCK_HEADER_BYTES or flags != 0:
        raise ValueError("live PCM block has unsupported header fields")
    if not 0 < frame_count <= MAX_PCM_BLOCK_FRAMES:
        raise ValueError("live PCM block frame count is out of bounds")
    if not 8_000 <= sample_rate_hz <= 192_000:
        raise ValueError("live PCM block sample rate is out of bounds")
    expected_bytes = PCM_BLOCK_HEADER_BYTES + frame_count * 2
    if len(data) != expected_bytes:
        raise ValueError("live PCM block payload length does not match its frame count")
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=frame_count,
        sample_rate_hz=sample_rate_hz,
        page_sent_ms=page_sent_ms,
        worklet_time_s=worklet_time_s,
        pcm_s16le=data[PCM_BLOCK_HEADER_BYTES:],
    )


def pack_pcm_block(block: PcmBlock) -> bytes:
    """Serialize one block for deterministic replay and protocol tests."""
    if len(block.pcm_s16le) != block.frame_count * 2:
        raise ValueError("PCM payload length does not match frame count")
    return PCM_BLOCK_HEADER.pack(
        PCM_BLOCK_MAGIC,
        PCM_BLOCK_VERSION,
        PCM_BLOCK_KIND_AUDIO,
        PCM_BLOCK_HEADER_BYTES,
        block.sequence,
        0,
        block.first_sample,
        block.frame_count,
        block.sample_rate_hz,
        block.page_sent_ms,
        block.worklet_time_s,
    ) + block.pcm_s16le


class LiveCaptureSession:
    """Persist one continuous Web Audio PCM stream without silent repair."""

    def __init__(
        self,
        job_root: Path,
        *,
        job_id: str,
        sample_rate_hz: int,
        client_metadata: dict[str, Any],
    ) -> None:
        if client_metadata.get("schema_version") != BROWSER_CAPTURE_SCHEMA:
            raise ValueError("unsupported browser capture metadata schema")
        if not 8_000 <= sample_rate_hz <= 192_000:
            raise ValueError("live sample rate is out of bounds")
        self.job_root = job_root.resolve()
        self.job_id = job_id
        self.sample_rate_hz = sample_rate_hz
        self.client_metadata = dict(client_metadata)
        self.input_directory = self.job_root / "input"
        self.live_directory = self.job_root / "live"
        self.input_directory.mkdir(parents=True)
        self.live_directory.mkdir()
        self.pcm_path = self.live_directory / ".capture.pcm"
        self.block_timing_path = self.input_directory / "live-blocks.jsonl"
        self._pcm = self.pcm_path.open("wb")
        self._block_rows: list[dict[str, Any]] = []
        self.next_sequence = 0
        self.next_sample = 0
        self.closed = False
        self.started_at = utc_now()

    def accept_block(self, block: PcmBlock, *, received_ns: int) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("live capture is already closed")
        if block.sample_rate_hz != self.sample_rate_hz:
            raise ValueError("live PCM block sample rate changed during capture")
        if block.sequence != self.next_sequence:
            raise ValueError(
                f"live PCM sequence gap: expected {self.next_sequence}, "
                f"received {block.sequence}"
            )
        if block.first_sample != self.next_sample:
            raise ValueError(
                f"live source sample gap: expected {self.next_sample}, "
                f"received {block.first_sample}"
            )
        if block.first_sample + block.frame_count > self.sample_rate_hz * MAX_LIVE_SECONDS:
            raise ValueError(f"live capture exceeds {MAX_LIVE_SECONDS} seconds")
        self._pcm.write(block.pcm_s16le)
        row = {
            "schema_version": "atpiano.live-block.v1",
            "sequence": block.sequence,
            "source_first_sample": block.first_sample,
            "source_frame_count": block.frame_count,
            "sample_rate_hz": block.sample_rate_hz,
            "page_sent_ms": block.page_sent_ms,
            "worklet_time_s": block.worklet_time_s,
            "host_received_monotonic_ns": received_ns,
        }
        self._block_rows.append(row)
        self.next_sequence += 1
        self.next_sample += block.frame_count
        return row

    def finalize(
        self,
        *,
        expected_frame_count: int,
        expected_block_count: int,
        capture_elapsed_s: float,
    ) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("live capture is already closed")
        if expected_frame_count != self.next_sample:
            raise ValueError(
                f"live Stop frame count {expected_frame_count} does not match "
                f"received {self.next_sample}"
            )
        if expected_block_count != self.next_sequence:
            raise ValueError(
                f"live Stop block count {expected_block_count} does not match "
                f"received {self.next_sequence}"
            )
        if expected_frame_count <= 0:
            raise ValueError("live capture contains no audio samples")
        self._pcm.close()
        self.closed = True
        write_jsonl(self.block_timing_path, self._block_rows)
        wav_path = self.input_directory / ".live.wav"
        with wave.open(str(wav_path), "wb") as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(self.sample_rate_hz)
            recording.writeframes(self.pcm_path.read_bytes())
        metadata = self.client_metadata | {
            "sample_rate_hz": self.sample_rate_hz,
            "frame_count": self.next_sample,
            "chunk_count": self.next_sequence,
            "capture_elapsed_s": capture_elapsed_s,
        }
        manifest = write_browser_capture_artifacts(
            self.input_directory,
            wav_path,
            client_metadata=metadata,
            adapter="web-audio-worklet-live-v1",
            transport="same-origin loopback WebSocket PCM16 blocks",
            capture_details={
                "block_timing_path": self.block_timing_path.name,
                "block_timing_sha256": sha256_file(self.block_timing_path),
                "block_count": self.next_sequence,
                "continuity": "exact; gaps, duplicates, and reordering rejected",
            },
        )
        wav_path.unlink()
        session = {
            "schema_version": LIVE_SESSION_SCHEMA,
            "job_id": self.job_id,
            "status": "captured",
            "started_at": self.started_at,
            "completed_at": utc_now(),
            "sample_rate_hz": self.sample_rate_hz,
            "source_frame_count": self.next_sample,
            "block_count": self.next_sequence,
            "pcm_sha256": sha256_file(self.pcm_path),
            "audio_sha256": manifest["audio"]["sha256"],
            "input_manifest": str(self.input_directory / "input.json"),
            "transport": "same-origin loopback WebSocket PCM16 blocks",
        }
        write_json(self.live_directory / "session.json", session)
        self.pcm_path.unlink()
        return manifest

    def abort(self, error: str) -> None:
        if not self.closed:
            self._pcm.close()
            self.closed = True
        write_jsonl(self.block_timing_path, self._block_rows)
        write_json(
            self.live_directory / "session.json",
            {
                "schema_version": LIVE_SESSION_SCHEMA,
                "job_id": self.job_id,
                "status": "failed",
                "started_at": self.started_at,
                "completed_at": utc_now(),
                "sample_rate_hz": self.sample_rate_hz,
                "source_frame_count": self.next_sample,
                "block_count": self.next_sequence,
                "error": error,
            },
        )


def decode_live_message(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("live control message is not valid JSON") from error
    if not isinstance(value, dict) or value.get("schema_version") != LIVE_STREAM_SCHEMA:
        raise ValueError("live control message has an unsupported schema")
    if not isinstance(value.get("type"), str):
        raise ValueError("live control message is missing its type")
    return value
