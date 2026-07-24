from __future__ import annotations

from atpiano.midi import MidiNote
from atpiano.quality import unscored_notes


def test_unaligned_input_is_explicitly_unscored() -> None:
    scores = unscored_notes([MidiNote(0.1, 0.5, 60, 80)])

    assert scores["quality_available"] is False
    assert scores["reference_note_count"] is None
    assert scores["estimated_note_count"] == 1
    assert scores["onset"]["50_ms"]["f1"] is None
