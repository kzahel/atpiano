from __future__ import annotations

from atpiano.midi import MidiNote
from atpiano.quality import score_notes


def test_identical_notes_score_perfectly() -> None:
    notes = [
        MidiNote(0.25, 0.75, 60, 64),
        MidiNote(1.00, 1.50, 64, 96),
    ]

    scores = score_notes(notes, notes)

    assert scores["onset"]["50_ms"]["f1"] == 1.0
    assert scores["onset"]["25_ms"]["f1"] == 1.0
    assert scores["note_with_offset"]["f1"] == 1.0
    assert scores["frame"]["f1"] == 1.0
    assert scores["matched_velocity_mae"] == 0.0


def test_empty_estimate_scores_zero() -> None:
    scores = score_notes([MidiNote(0.25, 0.75, 60, 64)], [])

    assert scores["onset"]["50_ms"]["precision"] == 0.0
    assert scores["onset"]["50_ms"]["recall"] == 0.0
    assert scores["onset"]["50_ms"]["f1"] == 0.0
