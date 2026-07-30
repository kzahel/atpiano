from __future__ import annotations

import json
from pathlib import Path

import mido
import pretty_midi
import pytest

from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.corrected_export import (
    query_history_index,
    query_materialized_index,
    write_corrected_exports,
    write_midi,
    write_playback_audio,
)


def _event(
    event_id: str,
    revision: int,
    *,
    onset: int,
    offset: int | None,
    lifecycle: str,
    pitch: int | None = 60,
    controller: int | None = None,
) -> dict[str, object]:
    return {
        "schema_version": CORRECTED_EVENT_SCHEMA,
        "session_id": "export-test",
        "event_id": event_id,
        "revision": revision,
        "lane": "commit" if lifecycle == "committed" else "preview",
        "lifecycle": lifecycle,
        "pitch": pitch,
        "controller": controller,
        "onset_sample": onset,
        "offset_sample": offset,
        "offset_state": "closed" if offset is not None else "open",
        "velocity": 80,
    }


def test_index_range_uses_latest_revision_and_interval_overlap(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="export-test",
        sample_rate_hz=100,
        source="replay",
        minimum_free_bytes=0,
    )
    session.append_events(
        [
            _event("moved", 1, onset=20, offset=40, lifecycle="provisional"),
            _event("moved", 2, onset=80, offset=100, lifecycle="committed"),
            _event("overlap", 1, onset=10, offset=70, lifecycle="committed"),
            _event("gone", 1, onset=55, offset=60, lifecycle="provisional"),
            _event("gone", 2, onset=55, offset=60, lifecycle="retracted"),
        ]
    )
    database_path = session.directory / "event-index.sqlite3"

    visible = query_materialized_index(
        database_path,
        start_sample=50,
        end_sample=75,
    )

    assert [row["event_id"] for row in visible] == ["overlap"]
    assert [row["event_id"] for row in query_history_index(
        database_path,
        after_sequence=2,
        limit=2,
    )] == ["overlap", "gone"]
    session.finalize()


def test_exports_preserve_history_and_emit_latest_notes_and_pedals(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="export-test",
        sample_rate_hz=100,
        source="replay",
        minimum_free_bytes=0,
    )
    session.append_events(
        [
            _event("note", 1, onset=10, offset=None, lifecycle="provisional"),
            _event("note", 2, onset=12, offset=62, lifecycle="committed"),
            _event(
                "pedal",
                1,
                onset=20,
                offset=70,
                lifecycle="committed",
                pitch=None,
                controller=64,
            ),
            _event("gone", 1, onset=30, offset=40, lifecycle="provisional"),
            _event("gone", 2, onset=30, offset=40, lifecycle="retracted"),
        ]
    )
    session.finalize()

    manifest = write_corrected_exports(session.directory)

    rows = [
        json.loads(line)
        for line in (session.directory / "exports" / "session.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["sequence"] for row in rows] == list(range(1, 6))
    assert manifest["jsonl"]["event_count"] == 5
    assert manifest["midi"]["note_count"] == 1
    assert manifest["midi"]["pedal_interval_count"] == 1
    midi = mido.MidiFile(session.directory / "exports" / "session.mid")
    messages = [message for track in midi.tracks for message in track]
    assert [message.type for message in messages].count("note_on") == 1
    assert [message.type for message in messages].count("note_off") == 1
    assert [message.type for message in messages].count("control_change") == 2


def test_midi_preserves_overlapping_same_pitch_note_offsets(
    tmp_path: Path,
) -> None:
    midi_path = tmp_path / "overlapping.mid"
    events = [
        _event(
            "earlier",
            1,
            onset=2_685_315,
            offset=2_878_440,
            lifecycle="committed",
            pitch=46,
        ),
        _event(
            "later",
            1,
            onset=2_849_542,
            offset=2_976_217,
            lifecycle="committed",
            pitch=46,
        ),
        _event(
            "pedal",
            1,
            onset=2_600_000,
            offset=3_000_000,
            lifecycle="committed",
            pitch=None,
            controller=64,
        ),
    ]

    note_count, pedal_count = write_midi(
        midi_path,
        events,
        sample_rate_hz=48_000,
    )

    raw = mido.MidiFile(midi_path)
    assert (note_count, pedal_count) == (2, 1)
    note_on_channels = [
        message.channel
        for message in raw.tracks[0]
        if message.type == "note_on" and message.velocity
    ]
    assert note_on_channels == [0, 1]
    assert [
        message.channel
        for message in raw.tracks[0]
        if message.type == "control_change"
    ] == [0, 1, 0, 1]
    parsed = sorted(
        [
            note
            for instrument in pretty_midi.PrettyMIDI(
                str(midi_path)
            ).instruments
            for note in instrument.notes
        ],
        key=lambda note: (note.start, note.pitch, note.end - note.start),
    )
    assert len(parsed) == 2
    assert parsed[0].start == pytest.approx(2_685_315 / 48_000, abs=0.002)
    assert parsed[0].end == pytest.approx(2_878_440 / 48_000, abs=0.002)
    assert parsed[1].start == pytest.approx(2_849_542 / 48_000, abs=0.002)
    assert parsed[1].end == pytest.approx(2_976_217 / 48_000, abs=0.002)


def test_playback_mp3_is_derived_without_replacing_wav_segments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = tmp_path / "session"
    audio = session / "audio"
    audio.mkdir(parents=True)
    first = audio / "000000.wav"
    second = audio / "000001.wav"
    first.write_bytes(b"first-lossless-segment")
    second.write_bytes(b"second-lossless-segment")
    observed: dict[str, object] = {}

    def fake_run(arguments: list[str], **_options: object) -> None:
        observed["arguments"] = arguments
        observed["concat"] = Path(arguments[arguments.index("-i") + 1]).read_text(
            encoding="utf-8"
        )
        Path(arguments[-1]).write_bytes(b"derived-mp3")

    monkeypatch.setattr("atpiano.corrected_export.subprocess.run", fake_run)

    result = write_playback_audio(
        session,
        ffmpeg_executable="/fake/ffmpeg",
    )

    assert result is not None
    assert result["media_type"] == "audio/mpeg"
    assert result["path"] == "playback/session.mp3"
    assert observed["concat"] == "file '000000.wav'\nfile '000001.wav'\n"
    assert first.read_bytes() == b"first-lossless-segment"
    assert second.read_bytes() == b"second-lossless-segment"
    assert (session / "playback" / "session.mp3").read_bytes() == b"derived-mp3"
