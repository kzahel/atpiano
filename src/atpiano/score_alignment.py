"""Durable source-performance to committed-score alignment artifacts."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any

from atpiano.corrected_export import midi_tick_at_sample
from atpiano.util import sha256_file

SCORE_INPUT_NOTES_SCHEMA = "atpiano.score-input-notes.v1"
SCORE_ALIGNMENT_SCHEMA = "atpiano.score-alignment.v1"


def score_input_notes_document(
    *,
    session_id: str,
    sample_rate_hz: int,
    notes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze selected source notes in the transformer's MIDI-note order."""

    def midi_order(event: dict[str, Any]) -> tuple[int, int, int, int, int, str]:
        onset_sample = int(event["onset_sample"])
        offset_sample = int(event["offset_sample"])
        onset_tick = midi_tick_at_sample(
            onset_sample,
            sample_rate_hz=sample_rate_hz,
        )
        offset_tick = midi_tick_at_sample(
            offset_sample,
            sample_rate_hz=sample_rate_hz,
        )
        return (
            onset_tick,
            int(event["pitch"]),
            offset_tick - onset_tick,
            onset_sample,
            offset_sample,
            str(event["event_id"]),
        )

    ordered = sorted(
        notes,
        key=midi_order,
    )
    return {
        "schema_version": SCORE_INPUT_NOTES_SCHEMA,
        "session_id": session_id,
        "sample_rate_hz": sample_rate_hz,
        "notes": [
            {
                "source_index": index,
                "event_id": str(event["event_id"]),
                "pitch": int(event["pitch"]),
                "onset_sample": int(event["onset_sample"]),
                "offset_sample": int(event["offset_sample"]),
                "velocity": max(1, min(127, int(event.get("velocity") or 64))),
            }
            for index, event in enumerate(ordered)
        ],
    }


def _fraction(value: object, *, field: str) -> Fraction:
    if (
        not isinstance(value, dict)
        or set(value) != {"numerator", "denominator"}
        or not isinstance(value["numerator"], int)
        or not isinstance(value["denominator"], int)
        or value["denominator"] <= 0
    ):
        raise ValueError(f"{field} must be a rational score position")
    return Fraction(value["numerator"], value["denominator"])


def _pitched_musicxml_ids(path: Path) -> list[str]:
    try:
        root = ET.fromstring(path.read_bytes())
    except ET.ParseError as error:
        raise ValueError(f"score alignment MusicXML is not well formed: {error}") from error
    identifiers: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "note":
            continue
        children = {child.tag.rsplit("}", 1)[-1] for child in element}
        if "rest" in children:
            continue
        identifier = element.get("id")
        if not identifier:
            raise ValueError("every aligned pitched MusicXML note requires an ID")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("aligned MusicXML note IDs must be unique")
    return identifiers


def validate_score_alignment(
    document: dict[str, Any],
    *,
    source_notes_path: Path,
    musicxml_path: Path,
) -> dict[str, int]:
    """Validate one alignment against its exact source and MusicXML artifacts."""

    if document.get("schema_version") != SCORE_ALIGNMENT_SCHEMA:
        raise ValueError("score alignment schema is unsupported")
    source = document.get("source")
    musicxml = document.get("musicxml")
    if not isinstance(source, dict) or not isinstance(musicxml, dict):
        raise ValueError("score alignment provenance is missing")
    if source.get("sha256") != sha256_file(source_notes_path):
        raise ValueError("score alignment source hash differs")
    if musicxml.get("sha256") != sha256_file(musicxml_path):
        raise ValueError("score alignment MusicXML hash differs")

    source_document = json.loads(
        source_notes_path.read_text(encoding="utf-8")
    )
    if source_document.get("schema_version") != SCORE_INPUT_NOTES_SCHEMA:
        raise ValueError("score alignment input-note schema is unsupported")
    source_notes = source_document.get("notes")
    rows = document.get("rows")
    inserted_segments = document.get("inserted_score_segments")
    if (
        not isinstance(source_notes, list)
        or not isinstance(rows, list)
        or not isinstance(inserted_segments, list)
    ):
        raise ValueError("score alignment rows are missing")
    if len(rows) != len(source_notes):
        raise ValueError("score alignment must account for every source note")

    prior_score_time: Fraction | None = None
    mapped = 0
    unmatched = 0
    aligned_note_ids: list[str] = []
    for index, (source_note, row) in enumerate(zip(source_notes, rows)):
        if not isinstance(source_note, dict) or not isinstance(row, dict):
            raise ValueError("score alignment note row is invalid")
        expected = {
            "source_index": index,
            "event_id": source_note.get("event_id"),
            "pitch": source_note.get("pitch"),
            "onset_sample": source_note.get("onset_sample"),
            "offset_sample": source_note.get("offset_sample"),
        }
        actual = {field: row.get(field) for field in expected}
        if actual != expected:
            raise ValueError("score alignment source identity differs")
        status = row.get("status")
        segments = row.get("segments")
        if not isinstance(segments, list):
            raise ValueError("score alignment segments are invalid")
        if status == "unmatched":
            if segments or row.get("score_time_quarters") is not None:
                raise ValueError("unmatched score alignment row has score data")
            unmatched += 1
            continue
        if status != "mapped" or not segments:
            raise ValueError("score alignment status is invalid")
        score_time = _fraction(
            row.get("score_time_quarters"),
            field="score_time_quarters",
        )
        if prior_score_time is not None and score_time < prior_score_time:
            raise ValueError("score alignment positions are not monotonic")
        prior_score_time = score_time
        mapped += 1
        segment_times: list[Fraction] = []
        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("score alignment segment is invalid")
            identifier = segment.get("musicxml_note_id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("score alignment segment has no MusicXML ID")
            segment_time = _fraction(
                segment.get("score_time_quarters"),
                field="segment.score_time_quarters",
            )
            duration = _fraction(
                segment.get("score_duration_quarters"),
                field="segment.score_duration_quarters",
            )
            if duration < 0 or segment_time < score_time:
                raise ValueError("score alignment segment timing is invalid")
            segment_times.append(segment_time)
            aligned_note_ids.append(identifier)
        if min(segment_times) != score_time:
            raise ValueError("score alignment attack differs from its segments")

    for segment in inserted_segments:
        if not isinstance(segment, dict):
            raise ValueError("inserted score alignment segment is invalid")
        identifier = segment.get("musicxml_note_id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("inserted score segment has no MusicXML ID")
        _fraction(
            segment.get("score_time_quarters"),
            field="inserted.score_time_quarters",
        )
        duration = _fraction(
            segment.get("score_duration_quarters"),
            field="inserted.score_duration_quarters",
        )
        if duration < 0:
            raise ValueError("inserted score segment duration is invalid")
        aligned_note_ids.append(identifier)

    musicxml_note_ids = _pitched_musicxml_ids(musicxml_path)
    if sorted(aligned_note_ids) != sorted(musicxml_note_ids):
        raise ValueError("score alignment does not cover the MusicXML notes")
    summary = document.get("summary")
    expected_summary = {
        "source_notes": len(source_notes),
        "mapped_source_notes": mapped,
        "unmatched_source_notes": unmatched,
        "musicxml_note_elements": len(musicxml_note_ids),
        "inserted_score_note_elements": len(inserted_segments),
    }
    if summary != expected_summary:
        raise ValueError("score alignment summary differs")
    return {
        "source_notes": len(source_notes),
        "mapped_source_notes": mapped,
        "unmatched_source_notes": unmatched,
        "musicxml_note_elements": len(musicxml_note_ids),
        "inserted_score_note_elements": len(inserted_segments),
    }


def event_xml_id(event_id: str, segment: int) -> str:
    """Return one stable, valid, per-segment MusicXML note identifier."""

    digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:20]
    return f"atpiano-{digest}-{segment:03d}"
