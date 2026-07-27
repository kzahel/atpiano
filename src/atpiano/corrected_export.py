"""Indexed review queries and bounded corrected-session exports."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

import mido

from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CORRECTED_SESSION_SCHEMA
from atpiano.util import read_json, sha256_file, utc_now, write_json

CORRECTED_EXPORT_SCHEMA = "atpiano.corrected-exports.v1"
DEFAULT_QUERY_LIMIT = 1024
MAX_QUERY_LIMIT = 4096
MIDI_TICKS_PER_BEAT = 480
MIDI_TEMPO_US_PER_BEAT = 500_000
PLAYBACK_BITRATE = "128k"

_LATEST_JOIN = """
    FROM events AS latest
    JOIN (
        SELECT event_id, MAX(revision) AS revision
        FROM events
        GROUP BY event_id
    ) AS selected
      ON latest.event_id = selected.event_id
     AND latest.revision = selected.revision
"""


def midi_tick_at_sample(source_sample: int, *, sample_rate_hz: int) -> int:
    """Return the exact tick written for one source-sample position."""

    if sample_rate_hz <= 0:
        raise ValueError("MIDI export sample rate must be positive")
    return round(
        mido.second2tick(
            source_sample / sample_rate_hz,
            MIDI_TICKS_PER_BEAT,
            MIDI_TEMPO_US_PER_BEAT,
        )
    )


def ensure_materialized_index(database_path: Path) -> None:
    """Add or rebuild the bounded range-query table in an older v2 index."""

    database_path = database_path.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"corrected event index does not exist: {database_path}")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS materialized_events (
                event_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL,
                onset_sample INTEGER NOT NULL,
                offset_sample INTEGER,
                lane TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS materialized_events_visible
                ON materialized_events(onset_sample, offset_sample, event_id);
            """
        )
        materialized_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM materialized_events"
            ).fetchone()[0]
        )
        event_count = int(
            connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        )
        if materialized_count == 0 and event_count:
            connection.execute(
                f"""
                INSERT INTO materialized_events (
                    event_id, revision, onset_sample, offset_sample,
                    lane, lifecycle, payload
                )
                SELECT latest.event_id, latest.revision, latest.onset_sample,
                       latest.offset_sample, latest.lane, latest.lifecycle,
                       latest.payload
                {_LATEST_JOIN}
                """
            )


def _connect_index(database_path: Path) -> sqlite3.Connection:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"corrected event index does not exist: {database_path}")
    connection = sqlite3.connect(
        f"file:{database_path.as_posix()}?mode=ro",
        uri=True,
    )
    connection.execute("PRAGMA query_only=ON")
    return connection


def query_materialized_index(
    database_path: Path,
    *,
    start_sample: int,
    end_sample: int,
) -> list[dict[str, Any]]:
    """Read latest visible identities overlapping one source-sample range."""

    if start_sample < 0 or end_sample < start_sample:
        raise ValueError("event query range is invalid")
    with _connect_index(database_path) as connection:
        rows = connection.execute(
            """
            SELECT payload
            FROM materialized_events
            WHERE lifecycle != 'retracted'
              AND onset_sample < ?
              AND (
                offset_sample IS NULL
                OR offset_sample >= ?
              )
            ORDER BY onset_sample, event_id
            """,
            (end_sample, start_sample),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def query_history_index(
    database_path: Path,
    *,
    after_sequence: int,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[dict[str, Any]]:
    """Read a bounded append-history page after a global sequence cursor."""

    if after_sequence < 0 or not 0 < limit <= MAX_QUERY_LIMIT:
        raise ValueError("event sequence query is invalid")
    with _connect_index(database_path) as connection:
        rows = connection.execute(
            """
            SELECT payload
            FROM events
            WHERE sequence > ?
            ORDER BY sequence
            LIMIT ?
            """,
            (after_sequence, limit),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def iter_history_index(database_path: Path) -> Iterator[dict[str, Any]]:
    """Stream the complete revision history without reading session PCM."""

    with _connect_index(database_path) as connection:
        cursor = connection.execute(
            "SELECT payload FROM events ORDER BY sequence"
        )
        for row in cursor:
            yield json.loads(row[0])


def iter_latest_committed_index(database_path: Path) -> Iterator[dict[str, Any]]:
    """Stream the latest committed revision of each identity."""

    with _connect_index(database_path) as connection:
        cursor = connection.execute(
            f"""
            SELECT latest.payload
            {_LATEST_JOIN}
            WHERE latest.lifecycle = 'committed'
            ORDER BY latest.onset_sample, latest.event_id
            """
        )
        for row in cursor:
            yield json.loads(row[0])


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if row.get("schema_version") != CORRECTED_EVENT_SCHEMA:
                raise ValueError("corrected export encountered an unsupported event")
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False))
            handle.write("\n")
            count += 1
    return count


def _write_midi(
    path: Path,
    events: Iterable[dict[str, Any]],
    *,
    sample_rate_hz: int,
) -> tuple[int, int]:
    timeline: list[tuple[int, int, mido.Message]] = []
    note_count = 0
    pedal_count = 0
    for event in events:
        onset_sample = int(event["onset_sample"])
        offset_value = event.get("offset_sample")
        offset_sample = (
            max(onset_sample, int(offset_value))
            if offset_value is not None
            else onset_sample
        )
        velocity = max(1, min(127, int(event.get("velocity") or 64)))
        pitch = event.get("pitch")
        controller = event.get("controller")
        if isinstance(pitch, int) and 0 <= pitch <= 127:
            timeline.append(
                (
                    onset_sample,
                    2,
                    mido.Message("note_on", note=pitch, velocity=velocity),
                )
            )
            timeline.append(
                (
                    offset_sample,
                    0,
                    mido.Message("note_off", note=pitch, velocity=0),
                )
            )
            note_count += 1
        elif isinstance(controller, int) and 0 <= controller <= 127:
            timeline.append(
                (
                    onset_sample,
                    3,
                    mido.Message("control_change", control=controller, value=velocity),
                )
            )
            timeline.append(
                (
                    offset_sample,
                    1,
                    mido.Message("control_change", control=controller, value=0),
                )
            )
            pedal_count += 1

    midi = mido.MidiFile(type=1, ticks_per_beat=MIDI_TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(
        mido.MetaMessage(
            "set_tempo",
            tempo=MIDI_TEMPO_US_PER_BEAT,
            time=0,
        )
    )
    previous_tick = 0
    for source_sample, _, message in sorted(
        timeline,
        key=lambda item: (item[0], item[1]),
    ):
        tick = midi_tick_at_sample(
            source_sample,
            sample_rate_hz=sample_rate_hz,
        )
        message.time = max(0, tick - previous_tick)
        track.append(message)
        previous_tick = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(path)
    return note_count, pedal_count


def write_midi(
    path: Path,
    events: Iterable[dict[str, Any]],
    *,
    sample_rate_hz: int,
) -> tuple[int, int]:
    """Write normalized note/controller events to a source-time MIDI file."""

    return _write_midi(path, events, sample_rate_hz=sample_rate_hz)


def write_corrected_exports(
    session_directory: Path,
    *,
    allow_settling: bool = False,
    playback_ffmpeg_executable: str | None = None,
    process_runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Write full JSONL history and latest committed MIDI from the event index."""

    session_directory = session_directory.resolve()
    session = read_json(session_directory / "session.json")
    if session.get("schema_version") != CORRECTED_SESSION_SCHEMA:
        raise ValueError("corrected export requires a corrected-session manifest")
    status = session.get("status")
    if status != "complete" and not (
        allow_settling and status == "stopping"
    ):
        raise ValueError("corrected export requires a stopped session")
    if status == "stopping":
        horizons = read_json(session_directory / "horizons.json")
        if int(horizons.get("commit_sample", -1)) != int(
            session["source_frame_count"]
        ):
            raise ValueError(
                "corrected export requires the stopping commit horizon "
                "to cover accepted audio"
            )
    sample_rate_hz = int(session["sample_rate_hz"])
    database_path = session_directory / "event-index.sqlite3"
    export_directory = session_directory / "exports"
    export_directory.mkdir(parents=True, exist_ok=True)
    jsonl_path = export_directory / "session.jsonl"
    midi_path = export_directory / "session.mid"
    history_count = _write_jsonl(jsonl_path, iter_history_index(database_path))
    note_count, pedal_count = _write_midi(
        midi_path,
        iter_latest_committed_index(database_path),
        sample_rate_hz=sample_rate_hz,
    )
    playback = write_playback_audio(
        session_directory,
        ffmpeg_executable=playback_ffmpeg_executable,
        process_runner=process_runner,
    )
    manifest = {
        "schema_version": CORRECTED_EXPORT_SCHEMA,
        "session_id": session["session_id"],
        "generated_at": utc_now(),
        "source_timeline": {
            "sample_rate_hz": sample_rate_hz,
            "frame_count": int(session["source_frame_count"]),
        },
        "jsonl": {
            "path": "session.jsonl",
            "sha256": sha256_file(jsonl_path),
            "event_count": history_count,
            "history": "all append-only revisions in global sequence order",
        },
        "midi": {
            "path": "session.mid",
            "sha256": sha256_file(midi_path),
            "note_count": note_count,
            "pedal_interval_count": pedal_count,
            "selection": "latest committed revision per identity",
        },
    }
    if playback is not None:
        manifest["playback"] = playback
    write_json(export_directory / "manifest.json", manifest)
    return manifest


def write_playback_audio(
    session_directory: Path,
    *,
    ffmpeg_executable: str | None = None,
    process_runner: Callable[..., Any] | None = None,
) -> dict[str, Any] | None:
    """Create one seekable MP3 derivative without replacing source WAVs."""

    session_directory = session_directory.resolve()
    ffmpeg = ffmpeg_executable or shutil.which("ffmpeg")
    runner = process_runner or subprocess.run
    segments = sorted((session_directory / "audio").glob("*.wav"))
    if ffmpeg is None or not segments:
        return None

    playback_directory = session_directory / "playback"
    playback_directory.mkdir(exist_ok=True)
    concat_path = session_directory / "audio" / ".playback-concat.txt"
    temporary_path = playback_directory / ".session.mp3"
    final_path = playback_directory / "session.mp3"
    concat_path.write_text(
        "".join(f"file '{segment.name}'\n" for segment in segments),
        encoding="utf-8",
    )
    try:
        runner(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(concat_path),
                "-map_metadata",
                "-1",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                PLAYBACK_BITRATE,
                "-write_xing",
                "1",
                str(temporary_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        os.replace(temporary_path, final_path)
    except (OSError, subprocess.CalledProcessError):
        temporary_path.unlink(missing_ok=True)
        return None
    finally:
        concat_path.unlink(missing_ok=True)

    return {
        "path": final_path.relative_to(session_directory).as_posix(),
        "sha256": sha256_file(final_path),
        "byte_count": final_path.stat().st_size,
        "media_type": "audio/mpeg",
        "codec": "mp3",
        "bitrate": PLAYBACK_BITRATE,
        "source": "derived from the complete segmented WAV source",
    }
