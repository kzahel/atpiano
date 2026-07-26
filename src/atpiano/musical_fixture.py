"""Deterministic aligned musical fixture for corrected-note integration."""

from __future__ import annotations

import math
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import mido
import numpy as np

from atpiano.fixture import INPUT_SCHEMA
from atpiano.midi import MidiNote, midi_to_hz
from atpiano.util import sha256_file, utc_now, write_json

MUSICAL_FIXTURE_ID = "deterministic-musical-loop-v1"
MUSICAL_SAMPLE_RATE = 48_000
MUSICAL_TEMPO_BPM = 96
MUSICAL_TEMPO_US_PER_BEAT = round(60_000_000 / MUSICAL_TEMPO_BPM)
MUSICAL_TICKS_PER_BEAT = 480
MUSICAL_BEAT_S = 60.0 / MUSICAL_TEMPO_BPM
MUSICAL_BAR_S = MUSICAL_BEAT_S * 4
MUSICAL_LEAD_S = 1.0
MUSICAL_MUSIC_S = MUSICAL_BAR_S * 16
MUSICAL_TAIL_S = 1.0
MUSICAL_DURATION_S = MUSICAL_LEAD_S + MUSICAL_MUSIC_S + MUSICAL_TAIL_S
MUSICAL_RENDERER_VERSION = "musical-harmonic-v1"
MUSICAL_PROGRESSION = (
    "C",
    "G/B",
    "Am",
    "F",
    "Dm",
    "G7",
    "C",
    "C",
)


@dataclass(frozen=True)
class ControlInterval:
    controller: int
    onset_s: float
    offset_s: float
    value: int = 127


@dataclass(frozen=True)
class MusicalBar:
    number: int
    start_s: float
    end_s: float
    harmony: str
    section: str
    texture: str
    block_pitches: tuple[int, ...]
    alberti_pattern: tuple[int, ...] | None


_CHORDS: dict[str, dict[str, tuple[int, ...] | int]] = {
    "C": {
        "bass": 36,
        "block": (60, 64, 67),
        "alberti": (36, 43, 40, 43),
    },
    "G/B": {
        "bass": 47,
        "block": (59, 62, 67),
        "alberti": (47, 55, 50, 55),
    },
    "Am": {
        "bass": 45,
        "block": (57, 60, 64),
        "alberti": (45, 52, 48, 52),
    },
    "F": {
        "bass": 41,
        "block": (53, 57, 60),
        "alberti": (41, 48, 45, 48),
    },
    "Dm": {
        "bass": 38,
        "block": (50, 53, 57),
        "alberti": (38, 45, 41, 45),
    },
    "G7": {
        "bass": 43,
        "block": (55, 59, 62, 65),
        "alberti": (43, 50, 47, 50),
    },
}

_MELODIES: tuple[tuple[int, ...], ...] = (
    (72, 76, 79, 76),
    (71, 74, 79, 74),
    (69, 72, 76, 72),
    (69, 72, 77, 72),
    (69, 74, 77, 74),
    (71, 74, 77, 79),
    (72, 76, 79, 84),
    (79, 76, 74, 72),
    (76, 79, 81, 79),
    (74, 79, 83, 79),
    (72, 76, 81, 76),
    (72, 77, 81, 77),
    (74, 77, 81, 77),
    (74, 77, 79, 79),
    (76, 79, 84, 79),
    (79, 76, 74, 72),
)


def _build_musical_score() -> tuple[
    tuple[MidiNote, ...],
    tuple[ControlInterval, ...],
    tuple[MusicalBar, ...],
]:
    notes: list[MidiNote] = []
    controls: list[ControlInterval] = []
    bars: list[MusicalBar] = []

    for index in range(16):
        harmony = MUSICAL_PROGRESSION[index % len(MUSICAL_PROGRESSION)]
        chord = _CHORDS[harmony]
        block = tuple(int(pitch) for pitch in chord["block"])
        alberti = tuple(int(pitch) for pitch in chord["alberti"])
        bar_start = MUSICAL_LEAD_S + index * MUSICAL_BAR_S
        bar_end = bar_start + MUSICAL_BAR_S
        section = "block-chords" if index < 8 else "alberti"
        texture = (
            "bass-block-chords-melody"
            if index < 8
            else "alberti-bass-melody"
        )

        if index < 8:
            bass_pitch = int(chord["bass"])
            notes.append(
                MidiNote(
                    bar_start,
                    bar_start + 3.75 * MUSICAL_BEAT_S,
                    bass_pitch,
                    70,
                )
            )
            for chord_beat, velocity in ((0.0, 82), (2.0, 76)):
                onset = bar_start + chord_beat * MUSICAL_BEAT_S
                offset = onset + 1.72 * MUSICAL_BEAT_S
                notes.extend(
                    MidiNote(onset, offset, pitch, velocity) for pitch in block
                )
        else:
            eighth_s = MUSICAL_BEAT_S / 2
            repeated_pattern = alberti * 2
            for step, pitch in enumerate(repeated_pattern):
                onset = bar_start + step * eighth_s
                notes.append(
                    MidiNote(
                        onset,
                        onset + 0.82 * eighth_s,
                        pitch,
                        62 + (step % 4 == 0) * 6,
                    )
                )
            if index >= 14:
                for chord_beat, velocity in ((0.0, 74), (2.0, 86)):
                    onset = bar_start + chord_beat * MUSICAL_BEAT_S
                    offset = onset + 1.65 * MUSICAL_BEAT_S
                    notes.extend(
                        MidiNote(onset, offset, pitch, velocity) for pitch in block
                    )

        for beat, pitch in enumerate(_MELODIES[index]):
            onset = bar_start + beat * MUSICAL_BEAT_S
            notes.append(
                MidiNote(
                    onset,
                    onset + 0.78 * MUSICAL_BEAT_S,
                    pitch,
                    78 + ((index + beat) % 4) * 4,
                )
            )

        controls.append(
            ControlInterval(
                controller=64,
                onset_s=bar_start + 0.08 * MUSICAL_BEAT_S,
                offset_s=bar_end - 0.08 * MUSICAL_BEAT_S,
            )
        )
        bars.append(
            MusicalBar(
                number=index + 1,
                start_s=bar_start,
                end_s=bar_end,
                harmony=harmony,
                section=section,
                texture=texture,
                block_pitches=block,
                alberti_pattern=alberti if index >= 8 else None,
            )
        )

    soft_start = MUSICAL_LEAD_S + 10 * MUSICAL_BAR_S
    controls.append(
        ControlInterval(
            controller=67,
            onset_s=soft_start,
            offset_s=soft_start + 2 * MUSICAL_BAR_S,
            value=96,
        )
    )
    return (
        tuple(sorted(notes)),
        tuple(sorted(controls, key=lambda item: (item.onset_s, item.controller))),
        tuple(bars),
    )


MUSICAL_NOTES, MUSICAL_CONTROLS, MUSICAL_BARS = _build_musical_score()


def _seconds_to_ticks(seconds: float) -> int:
    return round(
        mido.second2tick(
            seconds,
            MUSICAL_TICKS_PER_BEAT,
            MUSICAL_TEMPO_US_PER_BEAT,
        )
    )


def _write_reference_midi(path: Path) -> None:
    midi = mido.MidiFile(type=1, ticks_per_beat=MUSICAL_TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=MUSICAL_FIXTURE_ID, time=0))
    track.append(
        mido.MetaMessage(
            "time_signature",
            numerator=4,
            denominator=4,
            clocks_per_click=24,
            notated_32nd_notes_per_beat=8,
            time=0,
        )
    )
    track.append(
        mido.MetaMessage("set_tempo", tempo=MUSICAL_TEMPO_US_PER_BEAT, time=0)
    )
    track.append(mido.Message("program_change", program=0, channel=0, time=0))

    events: list[tuple[int, int, mido.Message]] = []
    for note in MUSICAL_NOTES:
        events.append(
            (
                _seconds_to_ticks(note.onset_s),
                2,
                mido.Message(
                    "note_on",
                    note=note.pitch,
                    velocity=note.velocity,
                    channel=0,
                    time=0,
                ),
            )
        )
        events.append(
            (
                _seconds_to_ticks(note.offset_s),
                0,
                mido.Message(
                    "note_off",
                    note=note.pitch,
                    velocity=0,
                    channel=0,
                    time=0,
                ),
            )
        )
    for control in MUSICAL_CONTROLS:
        events.append(
            (
                _seconds_to_ticks(control.onset_s),
                1,
                mido.Message(
                    "control_change",
                    control=control.controller,
                    value=control.value,
                    channel=0,
                    time=0,
                ),
            )
        )
        events.append(
            (
                _seconds_to_ticks(control.offset_s),
                0,
                mido.Message(
                    "control_change",
                    control=control.controller,
                    value=0,
                    channel=0,
                    time=0,
                ),
            )
        )

    previous_tick = 0
    for absolute_tick, _, message in sorted(events, key=lambda item: (item[0], item[1])):
        message.time = absolute_tick - previous_tick
        track.append(message)
        previous_tick = absolute_tick
    final_tick = _seconds_to_ticks(MUSICAL_DURATION_S)
    track.append(mido.MetaMessage("end_of_track", time=final_tick - previous_tick))
    midi.save(path)


def _sounding_offset(note: MidiNote) -> float:
    for control in MUSICAL_CONTROLS:
        if (
            control.controller == 64
            and control.onset_s <= note.offset_s < control.offset_s
        ):
            return control.offset_s
    return note.offset_s


def _soft_multiplier(onset_s: float) -> float:
    return (
        0.78
        if any(
            control.controller == 67
            and control.onset_s <= onset_s < control.offset_s
            for control in MUSICAL_CONTROLS
        )
        else 1.0
    )


def _render_wave(path: Path) -> tuple[int, float, float]:
    release_s = 0.08
    frame_count = round(MUSICAL_DURATION_S * MUSICAL_SAMPLE_RATE)
    audio = np.zeros(frame_count, dtype=np.float64)
    harmonic_weights = (1.0, 0.19, 0.065, 0.024, 0.009, 0.003)

    for note in MUSICAL_NOTES:
        start_frame = round(note.onset_s * MUSICAL_SAMPLE_RATE)
        sounding_offset = _sounding_offset(note)
        end_frame = min(
            frame_count,
            round((sounding_offset + release_s) * MUSICAL_SAMPLE_RATE),
        )
        relative_time = (
            np.arange(end_frame - start_frame, dtype=np.float64)
            / MUSICAL_SAMPLE_RATE
        )
        frequency = midi_to_hz(note.pitch)
        tone = np.zeros_like(relative_time)
        weight_total = 0.0
        for harmonic, weight in enumerate(harmonic_weights, start=1):
            if frequency * harmonic >= MUSICAL_SAMPLE_RATE / 2:
                break
            phase = ((note.pitch * 23 + harmonic * 31) % 101) / 101 * 2 * math.pi
            tone += weight * np.sin(
                2 * math.pi * frequency * harmonic * relative_time + phase
            )
            weight_total += weight
        tone /= weight_total

        attack = np.minimum(relative_time / 0.009, 1.0)
        decay = 0.67 + 0.33 * np.exp(-relative_time * 2.2)
        release_start = max(0.0, sounding_offset - note.onset_s)
        release = np.ones_like(relative_time)
        release_region = relative_time > release_start
        release[release_region] = np.maximum(
            0.0,
            1.0 - (relative_time[release_region] - release_start) / release_s,
        )
        amplitude = (
            0.115
            * ((note.velocity / 127.0) ** 1.3)
            * _soft_multiplier(note.onset_s)
        )
        audio[start_frame:end_frame] += amplitude * attack * decay * release * tone

    peak_before_scale = float(np.max(np.abs(audio)))
    scale = min(1.0, 0.92 / max(peak_before_scale, 1e-12))
    pcm = np.rint(audio * scale * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(MUSICAL_SAMPLE_RATE)
        output.writeframes(pcm.tobytes())
    return frame_count, frame_count / MUSICAL_SAMPLE_RATE, scale


def generate_musical_fixture(
    output_directory: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    midi_path = output_directory / "reference.mid"
    audio_path = output_directory / "fixture.wav"
    manifest_path = output_directory / "input.json"
    existing = [path for path in (midi_path, audio_path, manifest_path) if path.exists()]
    if existing and not force:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(f"refusing to overwrite existing fixture files: {names}")

    _write_reference_midi(midi_path)
    frame_count, duration_s, render_scale = _render_wave(audio_path)
    manifest: dict[str, Any] = {
        "schema_version": INPUT_SCHEMA,
        "input_id": MUSICAL_FIXTURE_ID,
        "created_at": utc_now(),
        "license": "project-generated test fixture",
        "audio": {
            "path": audio_path.name,
            "sha256": sha256_file(audio_path),
            "format": "wav-pcm-s16le",
            "sample_rate_hz": MUSICAL_SAMPLE_RATE,
            "channels": 1,
            "first_sample_index": 0,
            "frame_count": frame_count,
            "duration_s": duration_s,
        },
        "reference": {
            "path": midi_path.name,
            "sha256": sha256_file(midi_path),
            "format": "standard-midi-file",
            "note_count": len(MUSICAL_NOTES),
            "control_interval_count": len(MUSICAL_CONTROLS),
        },
        "musical_structure": {
            "tempo_bpm": MUSICAL_TEMPO_BPM,
            "meter": {"numerator": 4, "denominator": 4},
            "lead_s": MUSICAL_LEAD_S,
            "music_s": MUSICAL_MUSIC_S,
            "tail_s": MUSICAL_TAIL_S,
            "progression": list(MUSICAL_PROGRESSION),
            "bars": [asdict(bar) for bar in MUSICAL_BARS],
        },
        "renderer": {
            "name": "atpiano deterministic musical harmonic synthesizer",
            "version": MUSICAL_RENDERER_VERSION,
            "sample_rate_hz": MUSICAL_SAMPLE_RATE,
            "release_s": 0.08,
            "peak_scale": render_scale,
            "notes": [asdict(note) for note in MUSICAL_NOTES],
            "controls": [asdict(control) for control in MUSICAL_CONTROLS],
        },
    }
    write_json(manifest_path, manifest)
    return manifest
