from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from atpiano.corrected import CorrectedSession
from atpiano.corrected_preview import CorrectedPreviewLane
from atpiano.live import LiveModelOutput, PcmBlock
from atpiano.midi import MidiNote


class _PreviewModel:
    sample_rate_hz = 8_000
    window_samples = 8_000
    fft_hop_samples = 80
    overlapping_frames = 0
    left_guard_samples = 160
    right_guard_samples = 400

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        assert audio.shape == (self.window_samples,)
        self.calls += 1
        return LiveModelOutput(
            candidates=[
                (
                    MidiNote(
                        onset_s=0.5,
                        offset_s=0.82,
                        pitch=60 + self.calls % 3,
                        velocity=82,
                    ),
                    0.9,
                )
            ],
            raw={"onset": np.array([[self.calls]], dtype=np.float32)},
            inference_s=0.001,
            decode_s=0.0001,
            candidate_evidence=[{"source": "fake-onset"}],
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "fake-preview", "calls": self.calls}


def _block(
    sequence: int,
    first_sample: int,
    values: np.ndarray,
) -> PcmBlock:
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=values.shape[0],
        sample_rate_hz=8_000,
        page_sent_ms=0.0,
        worklet_time_s=0.0,
        pcm_s16le=values.astype("<i2").tobytes(),
    )


def test_preview_lane_persists_events_and_bounds_native_state(tmp_path: Path) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="preview-test",
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        pcm_ring_s=2.0,
        segment_s=2.0,
        minimum_free_bytes=0,
    )
    model = _PreviewModel()
    lane = CorrectedPreviewLane(
        session,
        model=model,
        native_retention_windows=3,
        identity_retention_s=1.0,
    )
    session.add_lane(lane)

    block_frames = 2_000
    total_frames = 20 * 8_000
    for first_sample in range(0, total_frames, block_frames):
        values = np.zeros(block_frames, dtype=np.int16)
        if first_sample >= 8_000:
            values.fill(12_000)
        session.accept_block(
            _block(first_sample // block_frames, first_sample, values),
            received_ns=time.perf_counter_ns(),
        )

    events = session.events.query_since(0, limit=10_000)
    assert events
    assert all(event["lane"] == "preview" for event in events)
    assert all(
        event["lifecycle"] in {"provisional", "retracted"} for event in events
    )
    assert all(event["source_to_emission_latency_s"] is None for event in events)
    assert session.horizons.provisional_sample >= 18 * 8_000
    assert session.ring.frame_count == session.ring.capacity_frames
    assert len(list(lane.raw_directory.glob("*.npz"))) == 3
    assert len(lane.reconciler.tracks) <= 8
    assert lane.status()["retention"]["native_windows_evicted"] > 0
    assert lane.status()["retention"]["active_identity_high_water"] <= 8

    manifest = session.finalize()
    assert manifest["status"] == "complete"
    assert manifest["lanes"][0]["name"] == "preview"
    assert manifest["lanes"][0]["window"]["processed"] == model.calls


class _LongClockModel(_PreviewModel):
    sample_rate_hz = 100
    window_samples = 100
    fft_hop_samples = 1
    overlapping_frames = 0
    left_guard_samples = 2
    right_guard_samples = 5


def test_preview_lane_bounds_state_over_eight_hour_source_clock(
    tmp_path: Path,
) -> None:
    sample_rate_hz = 100
    session = CorrectedSession(
        tmp_path / "long-session",
        session_id="long-preview-test",
        sample_rate_hz=sample_rate_hz,
        source="replay",
        realtime=False,
        pcm_ring_s=40.0,
        segment_s=4 * 60 * 60,
        minimum_free_bytes=0,
        horizon_snapshot_s=60.0,
    )
    model = _LongClockModel()
    lane = CorrectedPreviewLane(
        session,
        model=model,
        hop_s=60.0,
        native_retention_windows=3,
        identity_retention_s=40.0,
    )
    session.add_lane(lane)

    block_frames = 1_000
    total_frames = 8 * 60 * 60 * sample_rate_hz
    for first_sample in range(0, total_frames, block_frames):
        values = np.full(block_frames, 12_000, dtype=np.int16)
        if first_sample == 0:
            values.fill(0)
        session.accept_block(
            PcmBlock(
                sequence=first_sample // block_frames,
                first_sample=first_sample,
                frame_count=block_frames,
                sample_rate_hz=sample_rate_hz,
                page_sent_ms=0.0,
                worklet_time_s=0.0,
                pcm_s16le=values.astype("<i2").tobytes(),
            ),
            received_ns=time.perf_counter_ns(),
        )

    status = lane.status()
    assert session.horizons.audio_head_sample == total_frames
    assert session.ring.frame_count == 40 * sample_rate_hz
    assert status["window"]["processed"] == 480
    assert status["retention"]["native_windows_retained"] == 3
    assert status["retention"]["active_identity_count"] <= 1
    assert status["retention"]["active_identity_high_water"] <= 1
    session.finalize()
