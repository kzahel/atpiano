"""MIDI loading and normalized note helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pretty_midi


@dataclass(frozen=True, order=True)
class MidiNote:
    onset_s: float
    offset_s: float
    pitch: int
    velocity: int


@dataclass(frozen=True, order=True)
class PedalInterval:
    onset_s: float
    offset_s: float


def load_notes(path: Path) -> list[MidiNote]:
    midi = pretty_midi.PrettyMIDI(str(path))
    notes = [
        MidiNote(
            onset_s=float(note.start),
            offset_s=float(note.end),
            pitch=int(note.pitch),
            velocity=int(note.velocity),
        )
        for instrument in midi.instruments
        if not instrument.is_drum
        for note in instrument.notes
    ]
    return sorted(notes)


def load_pedal_intervals(path: Path) -> list[PedalInterval]:
    midi = pretty_midi.PrettyMIDI(str(path))
    changes = sorted(
        (
            float(control.time),
            int(control.value),
        )
        for instrument in midi.instruments
        if not instrument.is_drum
        for control in instrument.control_changes
        if control.number == 64
    )
    intervals: list[PedalInterval] = []
    active_onset: float | None = None
    for event_time, value in changes:
        if value >= 64 and active_onset is None:
            active_onset = event_time
        elif value < 64 and active_onset is not None:
            intervals.append(PedalInterval(active_onset, event_time))
            active_onset = None
    if active_onset is not None:
        intervals.append(PedalInterval(active_onset, midi.get_end_time()))
    return intervals


def midi_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))

