"""Deterministic WAV replay source for the application capture service."""

from __future__ import annotations

import time
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atpiano.live import MAX_PCM_BLOCK_FRAMES, PcmBlock
from atpiano.util import read_json, sha256_file


class LocalReplaySource:
    """Produce sample-indexed PCM blocks from one validated replay fixture."""

    def __init__(
        self,
        input_manifest_path: Path,
        *,
        repeat: int = 1,
        silence_s: float = 0.0,
        realtime: bool = True,
        block_samples: int = 4096,
    ) -> None:
        if repeat <= 0:
            raise ValueError("replay repetition count must be positive")
        if silence_s < 0:
            raise ValueError("replay silence cannot be negative")
        if not 0 < block_samples <= MAX_PCM_BLOCK_FRAMES:
            raise ValueError("replay block size is invalid")
        self.input_manifest_path = input_manifest_path.resolve()
        self.repeat = repeat
        self.silence_s = silence_s
        self.realtime = realtime
        self.block_samples = block_samples
        self.manifest = read_json(self.input_manifest_path)
        audio = self.manifest.get("audio")
        if not isinstance(audio, dict):
            raise ValueError("replay manifest is missing audio")
        self.audio_path = (
            self.input_manifest_path.parent
            / str(audio.get("path", ""))
        ).resolve()
        if not self.audio_path.is_file():
            raise FileNotFoundError(
                f"replay audio does not exist: {self.audio_path}"
            )
        if sha256_file(self.audio_path) != audio.get("sha256"):
            raise ValueError(
                "replay audio hash does not match input manifest"
            )
        self.sample_rate_hz = int(audio["sample_rate_hz"])
        self.input_frame_count = int(audio["frame_count"])
        with wave.open(str(self.audio_path), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise ValueError("replay requires mono PCM16 WAV")
            if source.getframerate() != self.sample_rate_hz:
                raise ValueError(
                    "replay WAV sample rate does not match manifest"
                )
            if source.getnframes() != self.input_frame_count:
                raise ValueError(
                    "replay WAV frame count does not match manifest"
                )

    def stream(
        self,
        *,
        accept: Callable[[PcmBlock, int], None],
        boundary: Callable[..., None],
    ) -> tuple[int, int]:
        """Feed all configured repetitions and return frames plus blocks."""

        sequence = 0
        source_head = 0
        origin_ns = time.perf_counter_ns()

        def accept_pcm(pcm: bytes) -> None:
            nonlocal sequence, source_head
            frame_count = len(pcm) // 2
            source_end = source_head + frame_count
            scheduled_ns = origin_ns + round(
                source_end
                / self.sample_rate_hz
                * 1_000_000_000
            )
            if self.realtime:
                remaining_s = (
                    scheduled_ns - time.perf_counter_ns()
                ) / 1_000_000_000
                if remaining_s > 0:
                    time.sleep(remaining_s)
            block = PcmBlock(
                sequence=sequence,
                first_sample=source_head,
                frame_count=frame_count,
                sample_rate_hz=self.sample_rate_hz,
                page_sent_ms=(
                    source_end / self.sample_rate_hz * 1000
                ),
                worklet_time_s=(
                    source_end / self.sample_rate_hz
                ),
                pcm_s16le=pcm,
            )
            accept(block, time.perf_counter_ns())
            source_head = source_end
            sequence += 1

        for repetition in range(self.repeat):
            repetition_start = source_head
            with wave.open(str(self.audio_path), "rb") as source:
                while True:
                    pcm = source.readframes(self.block_samples)
                    if not pcm:
                        break
                    accept_pcm(pcm)
            boundary(
                repetition=repetition,
                start_sample=repetition_start,
                end_sample=source_head,
                input_id=str(
                    self.manifest.get(
                        "input_id",
                        self.input_manifest_path.stem,
                    )
                ),
                audio_sha256=str(
                    self.manifest["audio"]["sha256"]
                ),
            )
            silence_frames = round(
                self.silence_s * self.sample_rate_hz
            )
            if repetition + 1 < self.repeat and silence_frames:
                silence_start = source_head
                remaining_frames = silence_frames
                while remaining_frames:
                    frames = min(
                        remaining_frames,
                        self.block_samples,
                    )
                    accept_pcm(bytes(frames * 2))
                    remaining_frames -= frames
                boundary(
                    repetition=repetition,
                    start_sample=silence_start,
                    end_sample=source_head,
                    input_id="inserted-silence",
                    audio_sha256=None,
                    kind="inserted-silence",
                )
        return source_head, sequence

    def configuration(self) -> dict[str, Any]:
        return {
            "configured": True,
            "manifest": str(self.input_manifest_path),
            "repeat": self.repeat,
            "silence_s": self.silence_s,
            "realtime": self.realtime,
        }
