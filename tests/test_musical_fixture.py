from __future__ import annotations

import wave
from collections import Counter
from pathlib import Path

import mido

from atpiano.midi import load_notes
from atpiano.musical_fixture import (
    MUSICAL_BARS,
    MUSICAL_CONTROLS,
    MUSICAL_DURATION_S,
    MUSICAL_FIXTURE_ID,
    MUSICAL_NOTES,
    MUSICAL_PROGRESSION,
    MUSICAL_SAMPLE_RATE,
    MUSICAL_TEMPO_BPM,
    generate_musical_fixture,
)
from atpiano.util import sha256_file


def test_musical_fixture_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = generate_musical_fixture(first)
    second_manifest = generate_musical_fixture(second)

    assert first_manifest["audio"]["sha256"] == second_manifest["audio"]["sha256"]
    assert first_manifest["reference"]["sha256"] == second_manifest["reference"]["sha256"]
    assert sha256_file(first / "fixture.wav") == sha256_file(second / "fixture.wav")
    assert sha256_file(first / "reference.mid") == sha256_file(second / "reference.mid")


def test_musical_fixture_has_declared_form_and_textures(tmp_path: Path) -> None:
    manifest = generate_musical_fixture(tmp_path)

    assert manifest["input_id"] == MUSICAL_FIXTURE_ID
    assert manifest["musical_structure"]["tempo_bpm"] == MUSICAL_TEMPO_BPM
    assert manifest["musical_structure"]["meter"] == {
        "numerator": 4,
        "denominator": 4,
    }
    assert tuple(manifest["musical_structure"]["progression"]) == MUSICAL_PROGRESSION
    assert len(MUSICAL_BARS) == 16
    assert [bar.harmony for bar in MUSICAL_BARS[:8]] == list(MUSICAL_PROGRESSION)
    assert all(bar.section == "block-chords" for bar in MUSICAL_BARS[:8])
    assert all(bar.section == "alberti" for bar in MUSICAL_BARS[8:])
    assert all(bar.alberti_pattern is not None for bar in MUSICAL_BARS[8:])

    second_section_start = MUSICAL_BARS[8].start_s
    second_bar_notes = [
        note
        for note in MUSICAL_NOTES
        if second_section_start <= note.onset_s < MUSICAL_BARS[8].end_s
        and note.pitch < 60
    ]
    expected_pattern = MUSICAL_BARS[8].alberti_pattern * 2
    assert tuple(note.pitch for note in second_bar_notes[:8]) == expected_pattern

    simultaneous = Counter(round(note.onset_s, 6) for note in MUSICAL_NOTES)
    assert sum(count >= 4 for count in simultaneous.values()) >= 16
    assert min(note.pitch for note in MUSICAL_NOTES) <= 36
    assert max(note.pitch for note in MUSICAL_NOTES) >= 84

    onsets_by_pitch: dict[int, list[float]] = {}
    for note in MUSICAL_NOTES:
        onsets_by_pitch.setdefault(note.pitch, []).append(note.onset_s)
    assert any(
        any(0.2 <= right - left <= 0.7 for left, right in zip(onsets, onsets[1:]))
        for onsets in onsets_by_pitch.values()
    )
    assert {control.controller for control in MUSICAL_CONTROLS} == {64, 67}


def test_musical_fixture_midi_and_wave_match_manifest(tmp_path: Path) -> None:
    manifest = generate_musical_fixture(tmp_path)
    midi_path = tmp_path / "reference.mid"
    notes = load_notes(midi_path)
    midi = mido.MidiFile(midi_path)
    messages = list(mido.merge_tracks(midi.tracks))

    assert len(notes) == len(MUSICAL_NOTES)
    assert manifest["reference"]["note_count"] == len(MUSICAL_NOTES)
    assert any(
        message.type == "time_signature"
        and message.numerator == 4
        and message.denominator == 4
        for message in messages
    )
    assert any(
        message.type == "set_tempo"
        and round(mido.tempo2bpm(message.tempo)) == MUSICAL_TEMPO_BPM
        for message in messages
    )
    assert {
        message.control
        for message in messages
        if message.type == "control_change" and message.value > 0
    } == {64, 67}

    with wave.open(str(tmp_path / "fixture.wav"), "rb") as audio:
        assert audio.getframerate() == MUSICAL_SAMPLE_RATE
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == round(MUSICAL_DURATION_S * MUSICAL_SAMPLE_RATE)
        assert manifest["audio"]["frame_count"] == audio.getnframes()
