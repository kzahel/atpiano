from __future__ import annotations

from pathlib import Path
from typing import Any

import mido
import pytest

from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.score_snapshot import generate_score_snapshot


def _event(
    event_id: str,
    *,
    pitch: int,
    onset_sample: int,
    offset_sample: int | None,
    lifecycle: str = "committed",
) -> dict[str, object]:
    return {
        "schema_version": CORRECTED_EVENT_SCHEMA,
        "session_id": "score-test",
        "event_id": event_id,
        "revision": 1,
        "lane": "commit" if lifecycle == "committed" else "preview",
        "lifecycle": lifecycle,
        "pitch": pitch,
        "onset_sample": onset_sample,
        "offset_sample": offset_sample,
        "offset_state": "closed" if offset_sample is not None else "open",
        "velocity": 80,
        "confidence": 0.9,
    }


def _fake_runner(
    input_midi: Path,
    output_musicxml: Path,
    runtime_directory: Path,
) -> dict[str, Any]:
    assert input_midi.is_file()
    assert runtime_directory.name == "runtime"
    output_musicxml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration><voice>1</voice>
      </note>
    </measure>
  </part>
</score-partwise>
""",
        encoding="utf-8",
    )
    return {"schema_version": "test-score-runner.v1"}


def test_score_snapshot_selects_only_closed_committed_prefix(
    tmp_path: Path,
) -> None:
    session_directory = tmp_path / "session"
    session = CorrectedSession(
        session_directory,
        session_id="score-test",
        sample_rate_hz=1_000,
        source="replay",
        minimum_free_bytes=0,
    )
    session.append_events(
        [
            _event(
                "included",
                pitch=60,
                onset_sample=100,
                offset_sample=300,
            ),
            _event(
                "provisional",
                pitch=62,
                onset_sample=200,
                offset_sample=400,
                lifecycle="provisional",
            ),
            _event(
                "open",
                pitch=64,
                onset_sample=300,
                offset_sample=None,
            ),
            _event(
                "past-commit",
                pitch=65,
                onset_sample=400,
                offset_sample=1_100,
            ),
        ]
    )
    session.finalize()

    manifest = generate_score_snapshot(
        session_directory,
        tmp_path / "runtime",
        commit_sample=1_000,
        runner=_fake_runner,
    )

    assert manifest["session_id"] == "score-test"
    assert manifest["commit_sample"] == 1_000
    assert manifest["note_count"] == 1
    assert manifest["musicxml"]["summary"]["pitched_note_elements"] == 1
    midi = mido.MidiFile(session_directory / manifest["midi"]["path"])
    note_ons = [
        message.note
        for track in midi.tracks
        for message in track
        if message.type == "note_on" and message.velocity
    ]
    assert note_ons == [60]
    assert (session_directory / "score" / "current.json").read_bytes() == (
        session_directory / "score" / "snapshots" / "0000000000001000" / "manifest.json"
    ).read_bytes()


def test_score_snapshot_rejects_empty_committed_prefix(tmp_path: Path) -> None:
    session_directory = tmp_path / "session"
    session = CorrectedSession(
        session_directory,
        session_id="score-test",
        sample_rate_hz=1_000,
        source="replay",
        minimum_free_bytes=0,
    )
    session.append_events(
        [
            _event(
                "open",
                pitch=60,
                onset_sample=100,
                offset_sample=None,
            )
        ]
    )
    session.finalize()

    with pytest.raises(ValueError, match="no closed committed notes"):
        generate_score_snapshot(
            session_directory,
            tmp_path / "runtime",
            commit_sample=1_000,
            runner=_fake_runner,
        )
