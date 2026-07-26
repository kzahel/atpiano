from __future__ import annotations

import struct
import threading
import time
from pathlib import Path

from atpiano.corrected import CorrectedSession, LaneUpdate
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
    assert read_json(session.directory / "session.json")["status"] == "complete"


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
