from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from atpiano.midi2score_adapter import _monotonic_exact_pitch_pairs
from atpiano.score_alignment import (
    score_input_notes_document,
    validate_score_alignment,
)
from atpiano.util import sha256_file, write_json


def _source_document() -> dict:
    return score_input_notes_document(
        session_id="alignment-test",
        sample_rate_hz=1_000,
        notes=[
            {
                "event_id": "later-c",
                "pitch": 60,
                "onset_sample": 200,
                "offset_sample": 500,
                "velocity": 80,
            },
            {
                "event_id": "chord-g",
                "pitch": 67,
                "onset_sample": 100,
                "offset_sample": 700,
                "velocity": 90,
            },
            {
                "event_id": "chord-e",
                "pitch": 64,
                "onset_sample": 100,
                "offset_sample": 700,
                "velocity": 90,
            },
        ],
    )


def test_source_notes_follow_transformer_order_after_midi_tick_collision() -> None:
    document = score_input_notes_document(
        session_id="tick-collision",
        sample_rate_hz=48_000,
        notes=[
            {
                "event_id": "earlier-high",
                "pitch": 60,
                "onset_sample": 1_421_403,
                "offset_sample": 1_460_087,
                "velocity": 36,
            },
            {
                "event_id": "later-low",
                "pitch": 48,
                "onset_sample": 1_421_409,
                "offset_sample": 1_505_777,
                "velocity": 33,
            },
        ],
    )

    assert [
        (note["source_index"], note["event_id"])
        for note in document["notes"]
    ] == [
        (0, "later-low"),
        (1, "earlier-high"),
    ]


def test_reconciliation_does_not_shift_identity_across_dropped_slots() -> None:
    source = [
        {"pitch": pitch}
        for pitch in (57, 69, 68, 61, 80, 69, 78, 71, 76, 68)
    ]
    score = [
        {"pitch": pitch}
        for pitch in (57, 61, 69, 78, 68, 71, 76)
    ]

    pairs = _monotonic_exact_pitch_pairs(source, score)

    assert pairs == sorted(pairs)
    assert all(source[left]["pitch"] == score[right]["pitch"] for left, right in pairs)
    assert (0, 0) in pairs
    assert (3, 1) in pairs
    assert (6, 3) in pairs
    assert (7, 5) in pairs
    assert (8, 6) in pairs


def test_reconciliation_prefers_nearby_repeated_pitch_identity() -> None:
    source = [{"pitch": pitch} for pitch in (60, 61, 60)]
    score = [{"pitch": pitch} for pitch in (60, 60)]

    assert _monotonic_exact_pitch_pairs(source, score) == [(0, 0), (2, 1)]


def _alignment(source_path: Path, musicxml_path: Path) -> dict:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    rows = []
    identifiers = ["note-e", "note-g", "note-c-a", "note-c-b"]
    for index, note in enumerate(source["notes"]):
        segment_ids = (
            identifiers[index : index + 1]
            if index < 2
            else identifiers[2:]
        )
        score_time = (
            {"numerator": 0, "denominator": 1}
            if index < 2
            else {"numerator": 1, "denominator": 1}
        )
        rows.append(
            {
                "source_index": index,
                "event_id": note["event_id"],
                "pitch": note["pitch"],
                "onset_sample": note["onset_sample"],
                "offset_sample": note["offset_sample"],
                "status": "mapped",
                "score_time_quarters": score_time,
                "segments": [
                    {
                        "musicxml_note_id": identifier,
                        "part": 1,
                        "pitch": note["pitch"],
                        "score_time_quarters": {
                            "numerator": 1 + segment_index,
                            "denominator": 1,
                        }
                        if index == 2
                        else score_time,
                        "score_duration_quarters": {
                            "numerator": 1,
                            "denominator": 1,
                        },
                        "tie": (
                            ["start", "stop"][segment_index]
                            if index == 2
                            else None
                        ),
                    }
                    for segment_index, identifier in enumerate(segment_ids)
                ],
            }
        )
    return {
        "schema_version": "atpiano.score-alignment.v2",
        "session_id": source["session_id"],
        "sample_rate_hz": source["sample_rate_hz"],
        "source": {
            "schema_version": source["schema_version"],
            "sha256": sha256_file(source_path),
        },
        "musicxml": {"sha256": sha256_file(musicxml_path)},
        "mapping": {
            "algorithm": "monotonic-exact-pitch-lcs-v1",
            "source_order": "onset-sample,pitch,duration,source-index",
            "score_order": "attack-quarters,pitch,output-index",
        },
        "summary": {
            "source_notes": 3,
            "mapped_source_notes": 3,
            "unmatched_source_notes": 0,
            "musicxml_note_elements": 4,
            "inserted_score_note_elements": 0,
        },
        "rows": rows,
        "inserted_score_segments": [],
    }


def test_score_alignment_orders_chords_and_preserves_tie_segments(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source-notes.json"
    musicxml_path = tmp_path / "score.musicxml"
    write_json(source_path, _source_document())
    musicxml_path.write_text(
        """<score-partwise version="4.0">
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1">
<note id="note-e"><pitch><step>E</step><octave>4</octave></pitch></note>
<note id="note-g"><chord/><pitch><step>G</step><octave>4</octave></pitch></note>
<note id="note-c-a"><pitch><step>C</step><octave>4</octave></pitch></note>
<note id="note-c-b"><pitch><step>C</step><octave>4</octave></pitch></note>
</measure></part></score-partwise>
""",
        encoding="utf-8",
    )
    source = _source_document()
    assert [note["event_id"] for note in source["notes"]] == [
        "chord-e",
        "chord-g",
        "later-c",
    ]

    summary = validate_score_alignment(
        _alignment(source_path, musicxml_path),
        source_notes_path=source_path,
        musicxml_path=musicxml_path,
    )

    assert summary == {
        "source_notes": 3,
        "mapped_source_notes": 3,
        "unmatched_source_notes": 0,
        "musicxml_note_elements": 4,
        "inserted_score_note_elements": 0,
    }


def test_score_alignment_rejects_nonmonotonic_score_positions(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source-notes.json"
    musicxml_path = tmp_path / "score.musicxml"
    write_json(source_path, _source_document())
    musicxml_path.write_text(
        """<score-partwise version="4.0">
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1">
<note id="note-e"><pitch><step>E</step><octave>4</octave></pitch></note>
<note id="note-g"><pitch><step>G</step><octave>4</octave></pitch></note>
<note id="note-c-a"><pitch><step>C</step><octave>4</octave></pitch></note>
<note id="note-c-b"><pitch><step>C</step><octave>4</octave></pitch></note>
</measure></part></score-partwise>
""",
        encoding="utf-8",
    )
    alignment = deepcopy(_alignment(source_path, musicxml_path))
    alignment["rows"][2]["score_time_quarters"] = {
        "numerator": -1,
        "denominator": 1,
    }
    alignment["rows"][2]["segments"][0]["score_time_quarters"] = {
        "numerator": -1,
        "denominator": 1,
    }

    with pytest.raises(ValueError, match="not monotonic"):
        validate_score_alignment(
            alignment,
            source_notes_path=source_path,
            musicxml_path=musicxml_path,
        )


def test_score_alignment_rejects_mapped_pitch_substitution(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source-notes.json"
    musicxml_path = tmp_path / "score.musicxml"
    write_json(source_path, _source_document())
    musicxml_path.write_text(
        """<score-partwise version="4.0">
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1">
<note id="note-e"><pitch><step>E</step><octave>4</octave></pitch></note>
<note id="note-g"><chord/><pitch><step>G</step><octave>4</octave></pitch></note>
<note id="note-c-a"><pitch><step>C</step><octave>4</octave></pitch></note>
<note id="note-c-b"><pitch><step>C</step><octave>4</octave></pitch></note>
</measure></part></score-partwise>
""",
        encoding="utf-8",
    )
    alignment = deepcopy(_alignment(source_path, musicxml_path))
    alignment["rows"][0]["segments"][0]["pitch"] = 61

    with pytest.raises(ValueError, match="pitch differs"):
        validate_score_alignment(
            alignment,
            source_notes_path=source_path,
            musicxml_path=musicxml_path,
        )
