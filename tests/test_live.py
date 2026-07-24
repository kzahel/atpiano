from __future__ import annotations

import struct
from pathlib import Path

import pytest

from atpiano.capture import BROWSER_CAPTURE_SCHEMA
from atpiano.live import LiveCaptureSession, PcmBlock, pack_pcm_block, parse_pcm_block
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

    manifest = session.finalize(
        expected_frame_count=5,
        expected_block_count=2,
        capture_elapsed_s=5 / 22_050,
    )

    assert manifest["capture"]["adapter"] == "web-audio-worklet-live-v1"
    assert manifest["capture"]["block_count"] == 2
    assert manifest["audio"]["frame_count"] == 5
    recording = session.input_directory / "recording.wav"
    assert recording.read_bytes()[-10:] == first.pcm_s16le + second.pcm_s16le
    live = read_json(session.live_directory / "session.json")
    assert live["status"] == "captured"
    assert live["source_frame_count"] == 5


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
