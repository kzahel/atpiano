"""Deterministic MIDI-derived audio fixture."""

from __future__ import annotations

import math
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any

import mido
import numpy as np

from atpiano.midi import MidiNote, PedalInterval, load_notes, load_pedal_intervals, midi_to_hz
from atpiano.util import sha256_file, utc_now, write_json

INPUT_SCHEMA = "atpiano.input.v1"
FIXTURE_ID = "deterministic-midi-smoke-v2"
SAMPLE_RATE = 22_050
TEMPO_US_PER_BEAT = 500_000
TICKS_PER_BEAT = 480
RENDERER_VERSION = "harmonic-v2"

FIXTURE_NOTES = (
    MidiNote(0.50, 1.10, 36, 72),
    MidiNote(1.45, 1.90, 60, 44),
    MidiNote(2.25, 2.75, 69, 108),
    # Deliberately crosses the replay adapter's wider right-edge guard.
    MidiNote(3.25, 3.50, 64, 84),
    MidiNote(3.70, 3.95, 64, 76),
    MidiNote(4.45, 5.30, 48, 82),
    MidiNote(4.45, 5.30, 55, 82),
    MidiNote(5.75, 6.80, 48, 88),
    MidiNote(5.75, 6.80, 55, 88),
    MidiNote(5.75, 6.80, 60, 88),
    MidiNote(5.75, 6.80, 64, 88),
    MidiNote(5.75, 6.80, 67, 88),
    MidiNote(5.75, 6.80, 72, 88),
    MidiNote(7.20, 8.35, 60, 64),
    MidiNote(7.75, 8.85, 64, 70),
    MidiNote(9.25, 9.72, 57, 58),
    MidiNote(9.25, 9.72, 60, 62),
    MidiNote(9.25, 9.72, 64, 66),
    MidiNote(11.00, 11.40, 96, 92),
)
FIXTURE_PEDALS = (PedalInterval(9.00, 10.55),)
FIXTURE_DURATION_S = 12.25


def _seconds_to_ticks(seconds: float) -> int:
    return round(mido.second2tick(seconds, TICKS_PER_BEAT, TEMPO_US_PER_BEAT))


def _write_reference_midi(path: Path) -> None:
    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=FIXTURE_ID, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=TEMPO_US_PER_BEAT, time=0))
    track.append(mido.Message("program_change", program=0, channel=0, time=0))

    events: list[tuple[int, int, mido.Message]] = []
    for note in FIXTURE_NOTES:
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
    for pedal in FIXTURE_PEDALS:
        events.append(
            (
                _seconds_to_ticks(pedal.onset_s),
                1,
                mido.Message("control_change", control=64, value=127, channel=0, time=0),
            )
        )
        events.append(
            (
                _seconds_to_ticks(pedal.offset_s),
                0,
                mido.Message("control_change", control=64, value=0, channel=0, time=0),
            )
        )

    previous_tick = 0
    for absolute_tick, _, message in sorted(events, key=lambda item: (item[0], item[1])):
        message.time = absolute_tick - previous_tick
        track.append(message)
        previous_tick = absolute_tick
    final_tick = _seconds_to_ticks(FIXTURE_DURATION_S)
    track.append(mido.MetaMessage("end_of_track", time=max(0, final_tick - previous_tick)))
    midi.save(path)


def _sounding_offset(note: MidiNote, pedals: tuple[PedalInterval, ...]) -> float:
    for pedal in pedals:
        if pedal.onset_s <= note.offset_s < pedal.offset_s:
            return pedal.offset_s
    return note.offset_s


def _render_wave(path: Path) -> tuple[int, float]:
    release_s = 0.06
    frame_count = math.ceil((FIXTURE_DURATION_S + release_s) * SAMPLE_RATE)
    audio = np.zeros(frame_count, dtype=np.float64)
    harmonic_weights = (1.0, 0.16, 0.045, 0.016, 0.006, 0.002)

    for note in FIXTURE_NOTES:
        start_frame = round(note.onset_s * SAMPLE_RATE)
        sounding_offset = _sounding_offset(note, FIXTURE_PEDALS)
        end_frame = min(frame_count, round((sounding_offset + release_s) * SAMPLE_RATE))
        relative_time = np.arange(end_frame - start_frame, dtype=np.float64) / SAMPLE_RATE
        frequency = midi_to_hz(note.pitch)

        tone = np.zeros_like(relative_time)
        for harmonic, weight in enumerate(harmonic_weights, start=1):
            if frequency * harmonic >= SAMPLE_RATE / 2:
                break
            phase = ((note.pitch * 17 + harmonic * 29) % 97) / 97.0 * 2.0 * math.pi
            tone += weight * np.sin(2.0 * math.pi * frequency * harmonic * relative_time + phase)
        tone /= sum(harmonic_weights)

        attack = np.minimum(relative_time / 0.008, 1.0)
        decay = 0.72 + 0.28 * np.exp(-relative_time * 2.6)
        release_start = max(0.0, sounding_offset - note.onset_s)
        release = np.ones_like(relative_time)
        release_region = relative_time > release_start
        release[release_region] = np.maximum(
            0.0,
            1.0 - ((relative_time[release_region] - release_start) / release_s),
        )
        amplitude = 0.34 * ((note.velocity / 127.0) ** 1.35)
        audio[start_frame:end_frame] += amplitude * attack * decay * release * tone

    pcm = np.rint(np.clip(audio, -0.98, 0.98) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm.tobytes())
    return frame_count, frame_count / SAMPLE_RATE


def generate_fixture(output_directory: Path, *, force: bool = False) -> dict[str, Any]:
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
    frame_count, duration_s = _render_wave(audio_path)
    loaded_notes = load_notes(midi_path)
    loaded_pedals = load_pedal_intervals(midi_path)
    manifest: dict[str, Any] = {
        "schema_version": INPUT_SCHEMA,
        "input_id": FIXTURE_ID,
        "created_at": utc_now(),
        "license": "project-generated test fixture",
        "audio": {
            "path": audio_path.name,
            "sha256": sha256_file(audio_path),
            "format": "wav-pcm-s16le",
            "sample_rate_hz": SAMPLE_RATE,
            "channels": 1,
            "first_sample_index": 0,
            "frame_count": frame_count,
            "duration_s": duration_s,
        },
        "reference": {
            "path": midi_path.name,
            "sha256": sha256_file(midi_path),
            "format": "standard-midi-file",
            "note_count": len(loaded_notes),
            "pedal_interval_count": len(loaded_pedals),
        },
        "renderer": {
            "name": "atpiano deterministic harmonic synthesizer",
            "version": RENDERER_VERSION,
            "sample_rate_hz": SAMPLE_RATE,
            "release_s": 0.06,
            "notes": [asdict(note) for note in FIXTURE_NOTES],
            "pedals": [asdict(pedal) for pedal in FIXTURE_PEDALS],
        },
    }
    write_json(manifest_path, manifest)
    return manifest
