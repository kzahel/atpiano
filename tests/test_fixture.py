from __future__ import annotations

import wave
from pathlib import Path

from atpiano.fixture import FIXTURE_NOTES, generate_fixture
from atpiano.midi import load_notes, load_pedal_intervals
from atpiano.util import sha256_file


def test_fixture_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = generate_fixture(first)
    second_manifest = generate_fixture(second)

    assert first_manifest["audio"]["sha256"] == second_manifest["audio"]["sha256"]
    assert first_manifest["reference"]["sha256"] == second_manifest["reference"]["sha256"]
    assert sha256_file(first / "fixture.wav") == sha256_file(second / "fixture.wav")
    assert sha256_file(first / "reference.mid") == sha256_file(second / "reference.mid")


def test_fixture_contains_expected_events(tmp_path: Path) -> None:
    generate_fixture(tmp_path)
    notes = load_notes(tmp_path / "reference.mid")
    pedals = load_pedal_intervals(tmp_path / "reference.mid")

    assert len(notes) == len(FIXTURE_NOTES)
    assert [note.pitch for note in notes].count(64) >= 3
    assert len(pedals) == 1
    assert pedals[0].onset_s == 9.0
    assert pedals[0].offset_s == 10.55

    with wave.open(str(tmp_path / "fixture.wav"), "rb") as audio:
        assert audio.getframerate() == 22_050
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2

