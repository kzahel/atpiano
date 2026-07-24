from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from atpiano.capture import BROWSER_CAPTURE_SCHEMA
from atpiano.decoder import STRICT_ONSET_DECODER_POLICY
from atpiano.live import (
    BasicPitchLiveModel,
    LiveCaptureSession,
    LiveModelOutput,
    LiveRecognitionProcessor,
    OnsetEnergyGate,
    PcmBlock,
    pack_pcm_block,
    parse_pcm_block,
)
from atpiano.midi import MidiNote
from atpiano.util import read_json


def _block(
    sequence: int,
    first_sample: int,
    samples: list[int],
    *,
    sample_rate_hz: int = 22_050,
) -> PcmBlock:
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=len(samples),
        sample_rate_hz=sample_rate_hz,
        page_sent_ms=100.0 + sequence,
        worklet_time_s=first_sample / sample_rate_hz,
        pcm_s16le=struct.pack(f"<{len(samples)}h", *samples),
    )


def _metadata() -> dict[str, object]:
    return {
        "schema_version": BROWSER_CAPTURE_SCHEMA,
        "started_at": "2026-07-24T12:00:00.000Z",
        "requested_constraints": {"echoCancellation": False},
    }


def test_pcm_block_round_trip_and_length_validation() -> None:
    block = _block(3, 12, [-32768, -1, 0, 32767])

    assert parse_pcm_block(pack_pcm_block(block)) == block
    with pytest.raises(ValueError, match="payload length"):
        parse_pcm_block(pack_pcm_block(block)[:-1])


def test_live_capture_preserves_exact_pcm_and_continuity(tmp_path: Path) -> None:
    session = LiveCaptureSession(
        tmp_path / "job",
        job_id="test-job",
        sample_rate_hz=22_050,
        client_metadata=_metadata(),
    )
    first = _block(0, 0, [-32768, -1, 0])
    second = _block(1, 3, [1, 32767])
    session.accept_block(first, received_ns=1_000)
    session.accept_block(second, received_ns=2_000)
    session.record_clock_observation(
        {
            "page_send_ms": 10.0,
            "page_receive_ms": 12.0,
            "host_receive_ns": 10_500_000,
            "host_send_ns": 10_600_000,
        },
        received_ns=12_500_000,
    )
    session.record_paint(
        {
            "batch_id": "test-1",
            "page_paint_ms": 13.0,
            "first_event_ids": ["event-1"],
        },
        received_ns=13_500_000,
    )

    manifest = session.finalize(
        expected_frame_count=5,
        expected_block_count=2,
        capture_elapsed_s=5 / 22_050,
    )

    assert manifest["capture"]["adapter"] == "web-audio-worklet-live-v1"
    assert manifest["capture"]["block_count"] == 2
    assert manifest["capture"]["clock_observations_path"] == "../live/clock.jsonl"
    assert manifest["capture"]["browser_paint_path"] == "../live/paint.jsonl"
    assert manifest["audio"]["frame_count"] == 5
    recording = session.input_directory / "recording.wav"
    assert recording.read_bytes()[-10:] == first.pcm_s16le + second.pcm_s16le
    live = read_json(session.live_directory / "session.json")
    assert live["status"] == "captured"
    assert live["source_frame_count"] == 5
    assert live["clock_observation_count"] == 1
    assert live["paint_acknowledgement_count"] == 1


def test_live_capture_rejects_sequence_and_source_gaps(tmp_path: Path) -> None:
    session = LiveCaptureSession(
        tmp_path / "job",
        job_id="test-job",
        sample_rate_hz=22_050,
        client_metadata=_metadata(),
    )

    with pytest.raises(ValueError, match="sequence gap"):
        session.accept_block(_block(1, 0, [0]), received_ns=1_000)
    session.accept_block(_block(0, 0, [0]), received_ns=2_000)
    with pytest.raises(ValueError, match="source sample gap"):
        session.accept_block(_block(1, 2, [0]), received_ns=3_000)
    session.abort("test complete")


def test_onset_energy_gate_calibrates_and_rejects_background() -> None:
    gate = OnsetEnergyGate(sample_rate_hz=1_000)
    samples = np.zeros(2_000, dtype="<i2")
    samples[1_380:1_520] = 8_000
    pcm = samples.tobytes()

    assert gate.calibrate(pcm) is True
    assert gate.noise_floor_dbfs == -120.0
    assert gate.threshold_dbfs == -48.0

    calibration_note = MidiNote(onset_s=0.5, offset_s=0.8, pitch=60, velocity=80)
    background_note = MidiNote(onset_s=1.7, offset_s=1.9, pitch=62, velocity=80)
    audible_note = MidiNote(onset_s=1.4, offset_s=1.8, pitch=64, velocity=80)

    assert gate.evaluate(calibration_note, pcm)[2] == "calibration"
    assert gate.evaluate(background_note, pcm)[2] == "below_threshold"
    accepted, level_dbfs, reason = gate.evaluate(audible_note, pcm)
    assert accepted is True
    assert reason == "accepted"
    assert level_dbfs is not None and level_dbfs > gate.threshold_dbfs
    assert gate.status()["accepted_candidate_count"] == 1
    assert gate.status()["rejected_calibration_count"] == 1
    assert gate.status()["rejected_level_count"] == 1


class _WindowModel:
    sample_rate_hz = 1_000
    window_samples = 2_000
    fft_hop_samples = 10
    overlapping_frames = 40
    left_guard_samples = 100
    right_guard_samples = 300

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        assert audio.shape == (2_000,)
        window_start_s = -0.2 + self.calls * 0.25
        self.calls += 1
        note = MidiNote(
            onset_s=1.4 - window_start_s,
            offset_s=1.8 - window_start_s,
            pitch=60,
            velocity=80,
        )
        return LiveModelOutput(
            candidates=[(note, 0.8)],
            raw={"onset": np.zeros((2, 88), dtype=np.float32)},
            inference_s=0.001,
            decode_s=0.001,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "test-live-model"}


class _NativeOutputModel:
    def predict(self, audio: np.ndarray) -> dict[str, np.ndarray]:
        assert audio.shape == (1, 2_000, 1)
        note = np.zeros((1, 50, 88), dtype=np.float32)
        onset = np.zeros((1, 50, 88), dtype=np.float32)
        contour = np.zeros((1, 50, 264), dtype=np.float32)
        note[0, 5:30, 39] = 0.8
        onset[0, 5, 39] = 0.65
        return {"note": note, "onset": onset, "contour": contour}


def test_basic_pitch_live_model_uses_selected_strict_decoder() -> None:
    model = BasicPitchLiveModel.__new__(BasicPitchLiveModel)
    model.model = _NativeOutputModel()
    model.decoder_policy = STRICT_ONSET_DECODER_POLICY

    output = model.predict(np.zeros(2_000, dtype=np.float32))

    assert len(output.candidates) == 1
    assert output.candidates[0][0].pitch == 60
    assert output.candidates[0][1] == pytest.approx(0.65)
    assert output.candidate_evidence == [
        {
            "decoder_source": "explicit_onset",
            "onset_confidence": pytest.approx(0.65),
            "decoder_confidence": pytest.approx(0.65),
            "frame_confidence": pytest.approx(0.8),
            "start_frame": 5,
            "end_frame": 30,
        }
    ]


def test_live_recognition_revises_onset_then_commits(tmp_path: Path) -> None:
    processor = LiveRecognitionProcessor(
        tmp_path / "recognition",
        session_id="test",
        source_sample_rate_hz=1_000,
        session_origin_ns=0,
        model=_WindowModel(),
    )
    batches = []
    cursor = 0
    for sequence, frame_count in enumerate((1_800, 250, 250, 250)):
        samples = [0] * frame_count
        signal_start = max(cursor, 1_380)
        signal_end = min(cursor + frame_count, 1_520)
        for sample in range(signal_start, signal_end):
            samples[sample - cursor] = 8_000
        block = _block(
            sequence,
            cursor,
            samples,
            sample_rate_hz=1_000,
        )
        batches.append(processor.accept_block(block, received_ns=sequence + 1))
        cursor += frame_count

    events = [event for batch in batches for event in batch["events"]]
    assert [event["lifecycle"] for event in events] == [
        "provisional",
        "committed",
    ]
    assert events[0]["event_id"] == events[1]["event_id"]
    assert events[1]["observation_count"] == 4
    manifest = processor.finalize()
    assert manifest["window"]["window_count"] == 4
    assert manifest["events"]["committed_tracks"] == 1
    assert manifest["noise_gate"]["accepted_candidate_count"] == 4
    assert manifest["noise_gate"]["rejected_level_count"] == 0
    assert (tmp_path / "recognition" / "gate.jsonl").is_file()
