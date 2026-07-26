from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import mido
import pytest

from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.score_snapshot import (
    generate_score_snapshot,
    score_snapshot_is_plausible,
)
from atpiano.util import sha256_file, write_json


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
    input_notes: Path,
    output_musicxml: Path,
    output_alignment: Path,
    runtime_directory: Path,
) -> dict[str, Any]:
    assert input_midi.is_file()
    source = json.loads(input_notes.read_text(encoding="utf-8"))
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
      <note id="test-note-1">
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration><voice>1</voice>
      </note>
    </measure>
  </part>
</score-partwise>
""",
        encoding="utf-8",
    )
    note = source["notes"][0]
    segment = {
        "musicxml_note_id": "test-note-1",
        "part": 1,
        "pitch": 60,
        "score_time_quarters": {"numerator": 0, "denominator": 1},
        "score_duration_quarters": {"numerator": 1, "denominator": 1},
        "tie": None,
    }
    write_json(
        output_alignment,
        {
            "schema_version": "atpiano.score-alignment.v1",
            "session_id": source["session_id"],
            "sample_rate_hz": source["sample_rate_hz"],
            "source": {
                "schema_version": source["schema_version"],
                "sha256": sha256_file(input_notes),
            },
            "musicxml": {"sha256": sha256_file(output_musicxml)},
            "summary": {
                "source_notes": 1,
                "mapped_source_notes": 1,
                "unmatched_source_notes": 0,
                "musicxml_note_elements": 1,
                "inserted_score_note_elements": 0,
            },
            "rows": [
                {
                    "source_index": 0,
                    "event_id": note["event_id"],
                    "pitch": note["pitch"],
                    "onset_sample": note["onset_sample"],
                    "offset_sample": note["offset_sample"],
                    "status": "mapped",
                    "score_time_quarters": {
                        "numerator": 0,
                        "denominator": 1,
                    },
                    "segments": [segment],
                }
            ],
            "inserted_score_segments": [],
        },
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
    try:
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
        assert manifest["alignment"]["summary"] == {
            "source_notes": 1,
            "mapped_source_notes": 1,
            "unmatched_source_notes": 0,
            "musicxml_note_elements": 1,
            "inserted_score_note_elements": 0,
        }
        midi = mido.MidiFile(session_directory / manifest["midi"]["path"])
        note_ons = [
            message.note
            for track in midi.tracks
            for message in track
            if message.type == "note_on" and message.velocity
        ]
        assert note_ons == [60]
        assert (session_directory / "score" / "current.json").read_bytes() == (
            session_directory
            / "score"
            / "snapshots"
            / "0000000000001000"
            / "manifest.json"
        ).read_bytes()
    finally:
        session.finalize()


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


def test_score_snapshot_rejects_pathological_note_expansion() -> None:
    manifest = {
        "note_count": 13,
        "musicxml": {
            "summary": {
                "pitched_note_elements": 491,
            }
        },
    }

    assert score_snapshot_is_plausible(manifest) is False


def test_score_snapshot_accepts_bounded_notation_expansion() -> None:
    manifest = {
        "note_count": 13,
        "musicxml": {
            "summary": {
                "pitched_note_elements": 29,
            }
        },
    }

    assert score_snapshot_is_plausible(manifest) is True
