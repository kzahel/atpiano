from __future__ import annotations

import time
from pathlib import Path

from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.corrected_commit import (
    CommitModelEvent,
    CommitModelOutput,
    CorrectedCommitLane,
)
from atpiano.live import PcmBlock


class _CommitModel:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        assert source_sample_rate_hz == 100
        self.calls += 1
        common = (
            CommitModelEvent(1.02, 4.0 if self.calls == 1 else 4.5, 60, 90),
            CommitModelEvent(2.0, 2.5, 64, 84),
            CommitModelEvent(1.5, 3.5 if self.calls == 1 else 4.2, -64, 127),
            CommitModelEvent(2.6, 2.8, 72, 78),
        )
        later = (
            (CommitModelEvent(4.0, 4.5, 67, 82),)
            if self.calls >= 2
            else ()
        )
        return CommitModelOutput(
            events=common + later,
            inference_s=0.01,
            source_frame_count=len(pcm_s16le) // 2,
            model_frame_count=len(pcm_s16le) // 2,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "fake-commit", "calls": self.calls}


def _preview(
    event_id: str,
    pitch: int,
    onset_sample: int,
    offset_sample: int,
) -> dict[str, object]:
    return {
        "schema_version": CORRECTED_EVENT_SCHEMA,
        "session_id": "commit-test",
        "event_id": event_id,
        "revision": 1,
        "lane": "preview",
        "lifecycle": "provisional",
        "pitch": pitch,
        "controller": None,
        "onset_sample": onset_sample,
        "offset_sample": offset_sample,
        "offset_state": "closed",
        "velocity": 70,
        "confidence": 0.8,
    }


def _block(sequence: int, first_sample: int, frame_count: int) -> PcmBlock:
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=frame_count,
        sample_rate_hz=100,
        page_sent_ms=0.0,
        worklet_time_s=0.0,
        pcm_s16le=bytes(frame_count * 2),
    )


def test_commit_lane_replaces_preview_and_closes_boundary_events(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="commit-test",
        sample_rate_hz=100,
        source="replay",
        realtime=False,
        pcm_ring_s=10.0,
        segment_s=10.0,
        minimum_free_bytes=0,
    )
    model = _CommitModel()
    lane = CorrectedCommitLane(
        session,
        model=model,
        buffer_s=6.0,
        hop_s=2.0,
        guard_s=1.0,
        minimum_context_s=4.0,
        onset_match_s=0.12,
    )
    session.add_lane(lane)
    session.append_events(
        [
            _preview("preview-60", 60, 100, 400),
            _preview("preview-64", 64, 200, 250),
            _preview("preview-drop", 65, 250, 300),
        ]
    )

    session.accept_block(_block(0, 0, 400), received_ns=time.perf_counter_ns())
    assert session.horizons.commit_sample == 300
    first_materialized = session.events.query_materialized(0, 300)
    first_by_id = {event["event_id"]: event for event in first_materialized}
    assert first_by_id["preview-60"]["offset_state"] == "open"
    assert first_by_id["preview-60"]["revision"] == 2
    assert first_by_id["preview-64"]["lifecycle"] == "committed"
    assert "preview-drop" not in first_by_id
    assert any(event["controller"] == 64 for event in first_materialized)
    assert any(event["pitch"] == 72 for event in first_materialized)

    session.accept_block(_block(1, 400, 200), received_ns=time.perf_counter_ns())
    assert session.horizons.commit_sample == 500
    materialized = session.events.query_materialized(0, 600)
    by_id = {event["event_id"]: event for event in materialized}
    assert by_id["preview-60"]["event_id"] == "preview-60"
    assert by_id["preview-60"]["revision"] == 3
    assert by_id["preview-60"]["offset_state"] == "closed"
    assert by_id["preview-60"]["offset_sample"] == 450
    assert any(
        event["controller"] == 64 and event["offset_state"] == "closed"
        for event in materialized
    )
    assert any(event["pitch"] == 67 for event in materialized)
    assert lane.status()["retention"]["pending_offset_count"] == 0

    manifest = session.finalize()
    assert manifest["status"] == "complete"
    assert manifest["lanes"][0]["events"] == {
        "closed_open_tails": 2,
        "commit_additions": 3,
        "emissions": 8,
        "matched_preview": 2,
        "preview_retractions": 1,
    }
    assert model.calls == 3
