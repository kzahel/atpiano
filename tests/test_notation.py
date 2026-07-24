from __future__ import annotations

import json
from pathlib import Path

import pytest

from atpiano.notation import (
    generate_notation_artifacts,
    import_oracle_musicxml,
    oracle_status,
    summarize_musicxml,
)
from atpiano.util import read_json, write_json


def _write_prediction(run_directory: Path) -> None:
    notes = [
        {"onset_s": 0.00, "offset_s": 1.20, "pitch": 48, "velocity": 80},
        {"onset_s": 0.00, "offset_s": 1.00, "pitch": 60, "velocity": 88},
        {"onset_s": 0.05, "offset_s": 1.00, "pitch": 64, "velocity": 86},
        {"onset_s": 0.10, "offset_s": 1.00, "pitch": 67, "velocity": 84},
        {"onset_s": 1.00, "offset_s": 1.50, "pitch": 72, "velocity": 78},
    ]
    write_json(
        run_directory / "prediction.json",
        {
            "schema_version": "atpiano.note-set.v1",
            "notes": notes,
            "pedals": [],
        },
    )
    events = [
        {
            "lifecycle": "committed",
            "event_id": f"event-{index}",
        }
        for index in range(len(notes))
    ]
    (run_directory / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def test_notation_generation_preserves_source_mapping_and_variants(
    tmp_path: Path,
) -> None:
    _write_prediction(tmp_path)

    manifest = generate_notation_artifacts(
        tmp_path,
        overrides={
            "tempo_bpm": 120,
            "meter_numerator": 4,
            "meter_denominator": 4,
            "first_beat_s": 0,
            "key": "C",
            "quantization": "sixteenth",
            "staff_split_pitch": 60,
        },
    )

    musicxml_path = tmp_path / manifest["artifacts"]["musicxml"]
    assert musicxml_path.is_file()
    assert manifest["summary"]["version"] == "4.0"
    assert manifest["summary"]["parts"] == 2
    assert manifest["summary"]["arpeggiate_marks"] == 3
    assert len(manifest["source_mapping"]) == 5
    assert {item["source_event_id"] for item in manifest["source_mapping"]} == {
        f"event-{index}" for index in range(5)
    }
    assert read_json(tmp_path / "notation/current.json")["variant_id"] == (
        manifest["variant_id"]
    )

    alternate = generate_notation_artifacts(
        tmp_path,
        overrides={
            "tempo_bpm": 90,
            "meter_numerator": 3,
            "meter_denominator": 4,
            "first_beat_s": 0,
            "key": "G",
            "quantization": "eighth",
            "staff_split_pitch": 60,
        },
    )
    assert alternate["variant_id"] != manifest["variant_id"]
    assert musicxml_path.is_file()
    assert (tmp_path / alternate["artifacts"]["musicxml"]).is_file()


def test_oracle_import_keeps_both_input_lanes(tmp_path: Path) -> None:
    musicxml = b"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1"><measure number="1"><attributes><divisions>1</divisions>
  <key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time>
  </attributes><note><pitch><step>C</step><octave>4</octave></pitch>
  <duration>1</duration><voice>1</voice><type>quarter</type></note></measure></part>
</score-partwise>
"""
    audio_manifest = import_oracle_musicxml(
        tmp_path,
        lane="audio",
        data=musicxml,
        original_filename="ivory from recording.musicxml",
    )
    assert audio_manifest["lanes"]["audio"]["summary"]["pitched_note_elements"] == 1
    midi_manifest = import_oracle_musicxml(
        tmp_path,
        lane="midi",
        data=musicxml.replace(b"<step>C</step>", b"<step>D</step>"),
        original_filename="../../ivory-midi.musicxml",
    )
    assert set(midi_manifest["lanes"]) == {"audio", "midi"}
    assert midi_manifest["lanes"]["midi"]["original_filename"] == "ivory-midi.musicxml"
    assert oracle_status(tmp_path) == midi_manifest


def test_musicxml_summary_rejects_unrelated_xml() -> None:
    with pytest.raises(ValueError, match="root"):
        summarize_musicxml(b"<html></html>")
