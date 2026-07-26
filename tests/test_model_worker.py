from __future__ import annotations

import numpy as np

from atpiano.corrected_commit import CommitModelOutput
from atpiano.live import LiveModelOutput
from atpiano.model_worker import CommitModelWorker, PreviewModelWorker


class _PreviewModel:
    sample_rate_hz = 8_000
    window_samples = 8
    fft_hop_samples = 1
    overlapping_frames = 0
    left_guard_samples = 0
    right_guard_samples = 0

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        return LiveModelOutput(
            candidates=[],
            raw={"onset": audio.reshape(1, -1)},
            inference_s=0.0,
            decode_s=0.0,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "spawn-preview"}


class _CommitModel:
    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        return CommitModelOutput(
            events=(),
            inference_s=0.0,
            source_frame_count=len(pcm_s16le) // 2,
            model_frame_count=source_sample_rate_hz,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "spawn-commit"}


def test_preview_worker_spawns_and_returns_native_output() -> None:
    worker = PreviewModelWorker(_PreviewModel)
    try:
        output = worker.predict(np.arange(8, dtype=np.float32))
        assert output.raw["onset"].shape == (1, 8)
        assert worker.window_samples == 8
        assert worker.provenance()["execution"]["boundary"] == "spawned-process"
        assert worker.status()["request_count"] == 1
    finally:
        worker.close()


def test_commit_worker_spawns_with_thread_budget() -> None:
    worker = CommitModelWorker(_CommitModel, thread_limit=2)
    try:
        output = worker.transcribe(
            bytes(12),
            source_sample_rate_hz=8_000,
        )
        assert output.source_frame_count == 6
        assert output.model_frame_count == 8_000
        assert worker.status()["thread_limit"] == 2
    finally:
        worker.close()
