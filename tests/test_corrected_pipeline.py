from __future__ import annotations

import struct
import threading
import time
from pathlib import Path

from atpiano.corrected import CorrectedSession, LaneUpdate
from atpiano.corrected_commit import (
    CommitModelOutput,
    CorrectedCommitLane,
)
from atpiano.corrected_pipeline import CorrectedSessionPipeline
from atpiano.live import PcmBlock
from atpiano.util import read_json


def _block(sequence: int, first_sample: int, frames: int) -> PcmBlock:
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=frames,
        sample_rate_hz=8_000,
        page_sent_ms=0.0,
        worklet_time_s=first_sample / 8_000,
        pcm_s16le=struct.pack(f"<{frames}h", *range(frames)),
    )


class _BlockingLane:
    name = "blocking"

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.processed = 0

    def has_pending_work(self, session: CorrectedSession) -> bool:
        return self.processed == 0 and session.horizons.audio_head_sample > 0

    def process_available(
        self,
        session: CorrectedSession,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> LaneUpdate:
        del received_ns, max_work_items
        self.started.set()
        if not self.release.wait(2):
            raise TimeoutError("test lane was not released")
        self.processed += 1
        return LaneUpdate(commit_sample=session.horizons.audio_head_sample)

    def accept_block(
        self,
        session: CorrectedSession,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> LaneUpdate:
        del block
        return self.process_available(session, received_ns=received_ns)

    def finalize(self, session: CorrectedSession) -> LaneUpdate:
        return LaneUpdate(commit_sample=session.horizons.audio_head_sample)

    def status(self) -> dict[str, object]:
        return {"name": self.name}


class _ImmediateLane:
    name = "immediate"

    def __init__(self) -> None:
        self.processed_sample = 0

    def has_pending_work(self, session: CorrectedSession) -> bool:
        return self.processed_sample < session.horizons.audio_head_sample

    def process_available(
        self,
        session: CorrectedSession,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> LaneUpdate:
        del received_ns, max_work_items
        self.processed_sample = session.horizons.audio_head_sample
        return LaneUpdate(provisional_sample=self.processed_sample)

    def accept_block(
        self,
        session: CorrectedSession,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> LaneUpdate:
        del block
        return self.process_available(session, received_ns=received_ns)

    def finalize(self, session: CorrectedSession) -> LaneUpdate:
        return LaneUpdate(provisional_sample=self.processed_sample)

    def status(self) -> dict[str, object]:
        return {"name": self.name}


class _FailingLane(_ImmediateLane):
    name = "failing"

    def process_available(
        self,
        session: CorrectedSession,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> LaneUpdate:
        del session, received_ns, max_work_items
        raise RuntimeError("intentional lane failure")


class _EmptyCommitModel:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        self.calls += 1
        return CommitModelOutput(
            events=(),
            inference_s=0.0,
            source_frame_count=len(pcm_s16le) // 2,
            model_frame_count=len(pcm_s16le) // 2,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "empty-commit"}


def test_blocked_lane_does_not_block_pcm_or_other_lane(tmp_path: Path) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
    )
    blocking = _BlockingLane()
    immediate = _ImmediateLane()
    session.add_lane(immediate)
    session.add_lane(blocking)
    pipeline = CorrectedSessionPipeline(session)

    pipeline.accept_block(_block(0, 0, 4), received_ns=1)
    assert blocking.started.wait(1)
    started = time.perf_counter()
    pipeline.accept_block(_block(1, 4, 4), received_ns=2)
    elapsed = time.perf_counter() - started

    deadline = time.monotonic() + 1
    while (
        session.horizons.provisional_sample != 8
        and time.monotonic() < deadline
    ):
        time.sleep(0.005)
    assert elapsed < 0.25
    assert session.horizons.audio_head_sample == 8
    assert session.horizons.provisional_sample == 8
    assert session.horizons.commit_sample == 0
    assert pipeline.status()["accepted_blocks"] == 2

    stopping = pipeline.begin_stop()
    assert stopping["status"] == "stopping"
    assert not pipeline.wait(0.05)
    blocking.release.set()
    assert pipeline.wait(1)
    manifest = read_json(session.directory / "session.json")
    assert manifest["status"] == "complete"
    assert manifest["pipeline"]["state"] == "complete"
    assert manifest["pipeline"]["accepted_frames"] == 8


def test_pipeline_abort_preserves_accepted_audio(tmp_path: Path) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
    )
    pipeline = CorrectedSessionPipeline(session)
    pipeline.accept_block(_block(0, 0, 4), received_ns=1)

    pipeline.abort(RuntimeError("socket closed before Stop"))

    manifest = read_json(session.directory / "session.json")
    assert manifest["status"] == "failed"
    assert manifest["source_frame_count"] == 4
    assert session.read_pcm(0, 4) == _block(0, 0, 4).pcm_s16le


def test_pipeline_defers_named_lane_until_stop(tmp_path: Path) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
        correction_mode="after-stop",
        correction_reason="test policy",
    )
    blocking = _BlockingLane()
    session.add_lane(blocking)
    pipeline = CorrectedSessionPipeline(
        session,
        defer_until_stop=frozenset({"blocking"}),
    )

    pipeline.accept_block(_block(0, 0, 4), received_ns=1)

    assert not blocking.started.wait(0.05)
    assert pipeline.status()["lanes"]["blocking"]["deferred_until_stop"]
    pipeline.begin_stop()
    assert blocking.started.wait(1)
    blocking.release.set()
    assert pipeline.wait(1)


def test_after_stop_lane_catches_up_beyond_pcm_ring_from_durable_audio(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        pcm_ring_s=0.5,
        segment_s=1.0,
        minimum_free_bytes=0,
        correction_mode="after-stop",
        correction_reason="test policy",
    )
    model = _EmptyCommitModel()
    lane = CorrectedCommitLane(
        session,
        model=model,
        buffer_s=0.5,
        hop_s=0.25,
        maximum_hop_s=0.25,
        guard_s=0.125,
        minimum_context_s=0.25,
    )
    session.add_lane(lane)
    pipeline = CorrectedSessionPipeline(
        session,
        defer_until_stop=frozenset({"commit"}),
    )
    block_frames = 4_000
    for sequence in range(6):
        pipeline.accept_block(
            _block(sequence, sequence * block_frames, block_frames),
            received_ns=sequence + 1,
        )

    assert session.horizons.audio_head_sample == 24_000
    assert session.ring.start_sample == 20_000
    assert model.calls == 0
    pipeline.begin_stop()
    assert pipeline.wait(2)

    assert model.calls > 1
    assert session.horizons.commit_sample == 24_000
    assert read_json(session.directory / "session.json")["status"] == "complete"


def test_lane_failure_preserves_capture_and_completes_with_stage_error(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
    )
    failing = _FailingLane()
    immediate = _ImmediateLane()
    session.add_lane(failing)
    session.add_lane(immediate)
    pipeline = CorrectedSessionPipeline(session)

    pipeline.accept_block(_block(0, 0, 4), received_ns=1)
    deadline = time.monotonic() + 1
    while (
        pipeline.status()["lanes"]["failing"]["error"] is None
        and time.monotonic() < deadline
    ):
        time.sleep(0.005)
    pipeline.accept_block(_block(1, 4, 4), received_ns=2)
    pipeline.begin_stop()

    assert pipeline.wait(1)
    manifest = read_json(session.directory / "session.json")
    assert manifest["status"] == "complete"
    assert manifest["source_frame_count"] == 8
    assert "intentional lane failure" in (
        manifest["processing"]["stage_errors"]["failing"]
    )


def test_commit_pressure_demotes_one_way_and_persists_reason(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
        correction_mode="live",
        correction_reason="measured profile",
    )
    delayed = session.observe_lane_pressure(
        "commit",
        {
            "scheduler": {
                "degraded_mode": True,
                "maximum_hop_frames": 64_000,
            },
            "decode_wall_s": {"max": 4.5},
        },
    )
    after_stop = session.observe_lane_pressure(
        "commit",
        {
            "scheduler": {
                "degraded_mode": True,
                "maximum_hop_frames": 64_000,
            },
            "decode_wall_s": {"max": 9.0},
        },
    )
    no_promotion = session.observe_lane_pressure(
        "commit",
        {
            "scheduler": {
                "degraded_mode": False,
                "maximum_hop_frames": 64_000,
            },
            "decode_wall_s": {"max": 1.0},
        },
    )

    manifest = read_json(session.directory / "session.json")
    assert delayed == "delayed"
    assert after_stop == "after-stop"
    assert no_promotion is None
    assert manifest["processing"]["correction_mode"] == "after-stop"
    assert "exceeded maximum scheduler hop" in (
        manifest["processing"]["correction_reason"]
    )


def test_commit_stage_failure_demotes_to_unavailable(tmp_path: Path) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
        correction_mode="delayed",
        correction_reason="measured profile",
    )

    session.record_stage_error("commit", RuntimeError("worker exited"))

    manifest = read_json(session.directory / "session.json")
    assert manifest["processing"]["correction_mode"] == "unavailable"
    assert "worker exited" in manifest["processing"]["correction_reason"]
