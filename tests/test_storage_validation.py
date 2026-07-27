from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from atpiano.fixture import generate_fixture
from atpiano.storage_validation import run_storage_validation
from atpiano.util import read_json


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="storage validation requires FFmpeg and FFprobe",
)
def test_storage_validation_emits_reconciled_evidence(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture"
    source = generate_fixture(fixture)
    evidence_path, evidence = run_storage_validation(
        fixture / "input.json",
        tmp_path / "workspace",
        minimum_hours=(
            float(source["audio"]["duration_s"]) / 3600
        ),
        minimum_free_bytes=0,
        timeout_s=30,
    )

    assert evidence_path.is_file()
    assert read_json(evidence_path) == evidence
    assert evidence["assertions"] == {
        "minimum_duration_met": True,
        "compact_recording_verified": True,
        "raw_wav_segments_retained": 0,
        "ordinary_debug_files_retained": 0,
        "every_repetition_boundary_aligned": True,
        "category_total_reconciles": True,
    }
    assert evidence["alignment"]["boundary_count"] == 1
    assert evidence["alignment"]["minimum_correlation"] >= 0.9
