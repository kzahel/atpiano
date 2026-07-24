from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

from atpiano.capture import write_capture_artifacts
from atpiano.util import sha256_file


def test_capture_writer_produces_unaligned_input_manifest(tmp_path: Path) -> None:
    sample_rate_hz = 22_050
    audio = np.linspace(-0.25, 0.25, sample_rate_hz, dtype=np.float32)
    block_records = [
        {
            "schema_version": "atpiano.capture-block.v1",
            "source_first_sample": 0,
            "source_frame_count": sample_rate_hz,
            "callback_monotonic_ns": 123,
            "input_adc_time_s": 1.5,
            "status": "",
        }
    ]

    manifest = write_capture_artifacts(
        tmp_path,
        audio,
        sample_rate_hz=sample_rate_hz,
        block_records=block_records,
        device={"name": "test"},
        requested_duration_s=1.0,
        block_samples=1024,
    )

    assert manifest["reference"] is None
    assert manifest["audio"]["frame_count"] == sample_rate_hz
    assert manifest["audio"]["sha256"] == sha256_file(tmp_path / "recording.wav")
    assert manifest["capture"]["block_count"] == 1
    with wave.open(str(tmp_path / "recording.wav"), "rb") as recording:
        assert recording.getframerate() == sample_rate_hz
        assert recording.getnchannels() == 1
    timing = [
        json.loads(line)
        for line in (tmp_path / "capture-timing.jsonl").read_text().splitlines()
    ]
    assert timing == block_records
