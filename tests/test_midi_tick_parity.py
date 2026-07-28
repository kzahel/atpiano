from __future__ import annotations

import json
from pathlib import Path

from atpiano.corrected_export import midi_tick_at_sample
from atpiano.score_alignment import score_input_notes_document

FIXTURE = (
    Path(__file__).parents[1]
    / "contracts"
    / "fixtures"
    / "v1"
    / "midi-tick-parity.json"
)


def test_python_producer_matches_canonical_midi_tick_fixture() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert (
        document["operation_identity"]
        == "mido-second2tick-float-python-half-even-v1"
    )
    sample_rate_hz = int(document["parameters"]["sample_rate_hz"])
    for case in document["tick_cases"]:
        assert midi_tick_at_sample(
            int(case["source_sample"]),
            sample_rate_hz=sample_rate_hz,
        ) == int(case["expected_tick"]), case["label"]
    for case in document["duration_cases"]:
        onset_tick = midi_tick_at_sample(
            int(case["onset_sample"]),
            sample_rate_hz=sample_rate_hz,
        )
        offset_tick = midi_tick_at_sample(
            int(case["offset_sample"]),
            sample_rate_hz=sample_rate_hz,
        )
        assert onset_tick == int(case["expected_onset_tick"]), case["label"]
        assert offset_tick == int(case["expected_offset_tick"]), case["label"]
        assert (
            offset_tick - onset_tick
            == int(case["expected_duration_ticks"])
        ), case["label"]


def test_python_producer_matches_canonical_transformer_order() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ordering = document["ordering"]
    ordered = score_input_notes_document(
        session_id="midi-tick-parity",
        sample_rate_hz=int(document["parameters"]["sample_rate_hz"]),
        notes=ordering["notes"],
    )

    assert [
        note["event_id"] for note in ordered["notes"]
    ] == ordering["expected_event_ids"]
