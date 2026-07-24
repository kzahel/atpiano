from __future__ import annotations

from atpiano.decoder_study import _same_pitch_restarts
from atpiano.midi import MidiNote


def test_same_pitch_restarts_only_count_adjacent_same_pitch() -> None:
    notes = [
        MidiNote(0.0, 1.0, 60, 80),
        MidiNote(0.2, 0.4, 64, 80),
        MidiNote(0.45, 1.0, 60, 80),
        MidiNote(1.2, 1.5, 60, 80),
    ]

    assert _same_pitch_restarts(notes) == {
        "under_250_ms": 0,
        "under_500_ms": 1,
        "under_1000_ms": 2,
    }
