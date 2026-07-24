"""Inspectable performance-to-notation artifacts and oracle imports."""

from __future__ import annotations

import hashlib
import json
import math
import re
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import partitura
import pretty_midi
from lxml import etree
from partitura.musicanalysis import estimate_key, note_array_to_score
from partitura.score import PartGroup, Score
from partitura.utils import key_name_to_fifths_mode

from atpiano.midi import MidiNote
from atpiano.util import read_json, sha256_file, utc_now, write_json

NOTATION_SCHEMA = "atpiano.notation.v1"
ORACLE_SCHEMA = "atpiano.notation-oracle.v1"
MUSICXML_MAX_BYTES = 8 * 1024 * 1024
DIVISIONS_PER_QUARTER = 24
QUANTIZATION_DIVISIONS = {
    "eighth": 12,
    "eighth-triplet": 8,
    "sixteenth": 6,
    "thirty-second": 3,
}
SUPPORTED_METERS = {(2, 4), (3, 4), (4, 4), (5, 4), (6, 8), (9, 8), (12, 8)}
KEY_PATTERN = re.compile(r"[A-G](?:#|b)?m?")
MUSICXML_DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)

_PITCH_CLASS_NAMES = (
    "C",
    "C#",
    "D",
    "Eb",
    "E",
    "F",
    "F#",
    "G",
    "Ab",
    "A",
    "Bb",
    "B",
)
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
    dtype=np.float64,
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17],
    dtype=np.float64,
)


@dataclass(frozen=True)
class NotationOptions:
    tempo_bpm: float
    meter_numerator: int
    meter_denominator: int
    first_beat_s: float
    key: str
    quantization: str
    staff_split_pitch: int


def _notes_from_document(path: Path) -> list[MidiNote]:
    document = read_json(path)
    values = document.get("notes")
    if not isinstance(values, list):
        raise ValueError(f"{path} is missing a notes array")
    notes = [
        MidiNote(
            onset_s=float(value["onset_s"]),
            offset_s=float(value["offset_s"]),
            pitch=int(value["pitch"]),
            velocity=int(value["velocity"]),
        )
        for value in values
    ]
    return sorted(notes)


def _event_ids(run_directory: Path, notes: list[MidiNote]) -> list[str]:
    path = run_directory / "events.jsonl"
    if not path.is_file():
        return [f"prediction-note-{index:04d}" for index in range(len(notes))]
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    committed = [event for event in events if event.get("lifecycle") == "committed"]
    if len(committed) != len(notes):
        return [f"prediction-note-{index:04d}" for index in range(len(notes))]
    return [
        str(event.get("event_id") or f"prediction-note-{index:04d}")
        for index, event in enumerate(committed)
    ]


def _partitura_note_array(notes: list[MidiNote]) -> np.ndarray:
    return np.array(
        [
            (
                note.onset_s,
                max(0.001, note.offset_s - note.onset_s),
                note.pitch,
                note.velocity,
            )
            for note in notes
        ],
        dtype=[
            ("onset_sec", "f8"),
            ("duration_sec", "f8"),
            ("pitch", "i4"),
            ("velocity", "i4"),
        ],
    )


def _tempo_hypotheses(notes: list[MidiNote]) -> dict[str, Any]:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes = [
        pretty_midi.Note(
            velocity=note.velocity,
            pitch=note.pitch,
            start=note.onset_s,
            end=note.offset_s,
        )
        for note in notes
    ]
    midi.instruments.append(instrument)
    try:
        raw_bpm = float(midi.estimate_tempo())
    except (ValueError, ZeroDivisionError):
        raw_bpm = 120.0
    if not math.isfinite(raw_bpm) or raw_bpm <= 0:
        raw_bpm = 120.0

    comfortable_bpm = raw_bpm
    while comfortable_bpm > 140.0:
        comfortable_bpm /= 2.0
    while comfortable_bpm < 55.0:
        comfortable_bpm *= 2.0

    partitura_time: dict[str, Any] | None = None
    try:
        from partitura.musicanalysis import estimate_time

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            estimate = estimate_time(_partitura_note_array(notes))
        partitura_time = {
            "tempo_bpm": float(estimate["tempo"]),
            "meter_numerator": int(estimate["meter_numerator"]),
            "beat_count": len(estimate["beats"]),
        }
    except (KeyError, RuntimeError, TypeError, ValueError):
        pass

    candidates = sorted(
        {
            round(value, 3)
            for value in (
                comfortable_bpm,
                raw_bpm,
                raw_bpm / 2.0,
                raw_bpm * 2.0,
            )
            if 35.0 <= value <= 240.0
        },
        key=lambda value: (abs(value - comfortable_bpm), value),
    )
    return {
        "selected_bpm": round(comfortable_bpm, 3),
        "pretty_midi_raw_bpm": round(raw_bpm, 3),
        "candidates_bpm": candidates,
        "partitura": partitura_time,
        "selection_policy": "normalize pretty_midi estimate into the 55–140 BPM band",
    }


def _key_hypotheses(notes: list[MidiNote]) -> dict[str, Any]:
    weights = np.zeros(12, dtype=np.float64)
    for note in notes:
        duration = max(0.01, note.offset_s - note.onset_s)
        weights[note.pitch % 12] += duration * (0.5 + note.velocity / 127.0)

    ranked: list[dict[str, Any]] = []
    for tonic in range(12):
        for mode, profile in (("major", _MAJOR_PROFILE), ("minor", _MINOR_PROFILE)):
            rotated = np.roll(profile, tonic)
            correlation = float(np.corrcoef(weights, rotated)[0, 1])
            name = _PITCH_CLASS_NAMES[tonic] + ("m" if mode == "minor" else "")
            ranked.append(
                {
                    "key": name,
                    "mode": mode,
                    "correlation": round(correlation, 6),
                }
            )
    ranked.sort(key=lambda value: value["correlation"], reverse=True)

    try:
        partitura_key = str(estimate_key(_partitura_note_array(notes)))
    except (RuntimeError, TypeError, ValueError):
        partitura_key = ranked[0]["key"]
    return {
        "selected": partitura_key,
        "partitura": partitura_key,
        "ranked_profiles": ranked[:5],
    }


def analyze_notation(notes: list[MidiNote]) -> dict[str, Any]:
    if not notes:
        raise ValueError("notation requires at least one note")
    tempo = _tempo_hypotheses(notes)
    key = _key_hypotheses(notes)
    partitura_meter = (tempo.get("partitura") or {}).get("meter_numerator")
    meter_candidate = (
        [partitura_meter, 4]
        if isinstance(partitura_meter, int) and (partitura_meter, 4) in SUPPORTED_METERS
        else None
    )
    return {
        "tempo": tempo,
        "key": key,
        "meter": {
            "selected": [4, 4],
            "partitura_candidate": meter_candidate,
            "selection_policy": "4/4 default; meter inference is not trusted yet",
        },
        "first_beat": {
            "selected_s": round(min(note.onset_s for note in notes), 6),
            "selection_policy": "first estimated onset; pickup is not inferred",
        },
    }


def _validated_options(
    hypotheses: dict[str, Any],
    overrides: dict[str, Any] | None,
) -> NotationOptions:
    values = {
        "tempo_bpm": hypotheses["tempo"]["selected_bpm"],
        "meter_numerator": hypotheses["meter"]["selected"][0],
        "meter_denominator": hypotheses["meter"]["selected"][1],
        "first_beat_s": hypotheses["first_beat"]["selected_s"],
        "key": hypotheses["key"]["selected"],
        "quantization": "sixteenth",
        "staff_split_pitch": 60,
    }
    if overrides:
        unknown = set(overrides) - set(values)
        if unknown:
            raise ValueError(f"unsupported notation options: {', '.join(sorted(unknown))}")
        values.update(overrides)

    tempo_bpm = float(values["tempo_bpm"])
    meter = (int(values["meter_numerator"]), int(values["meter_denominator"]))
    first_beat_s = float(values["first_beat_s"])
    key = str(values["key"])
    quantization = str(values["quantization"])
    staff_split_pitch = int(values["staff_split_pitch"])
    if not 30.0 <= tempo_bpm <= 300.0:
        raise ValueError("tempo_bpm must be between 30 and 300")
    if meter not in SUPPORTED_METERS:
        raise ValueError("unsupported time signature")
    if not math.isfinite(first_beat_s) or first_beat_s < 0:
        raise ValueError("first_beat_s must be a non-negative finite value")
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("key must look like C, F#, Bb, Am, or C#m")
    try:
        key_name_to_fifths_mode(key)
    except (KeyError, ValueError) as error:
        raise ValueError(f"unsupported key signature: {key}") from error
    if quantization not in QUANTIZATION_DIVISIONS:
        raise ValueError("unsupported quantization")
    if not 36 <= staff_split_pitch <= 84:
        raise ValueError("staff_split_pitch must be between 36 and 84")
    return NotationOptions(
        tempo_bpm=round(tempo_bpm, 3),
        meter_numerator=meter[0],
        meter_denominator=meter[1],
        first_beat_s=round(first_beat_s, 6),
        key=key,
        quantization=quantization,
        staff_split_pitch=staff_split_pitch,
    )


def _arpeggio_groups(notes: list[MidiNote]) -> dict[int, dict[str, Any]]:
    groups: dict[int, dict[str, Any]] = {}
    ordered = sorted(enumerate(notes), key=lambda value: (value[1].onset_s, value[1].pitch))
    cursor = 0
    group_number = 1
    while cursor < len(ordered):
        start = cursor
        first_onset = ordered[start][1].onset_s
        while (
            cursor + 1 < len(ordered)
            and ordered[cursor + 1][1].onset_s - first_onset <= 0.18
        ):
            cursor += 1
        candidates = ordered[start : cursor + 1]
        onset_spread = candidates[-1][1].onset_s - candidates[0][1].onset_s
        pitches = [note.pitch for _, note in candidates]
        monotonic_up = all(left < right for left, right in zip(pitches, pitches[1:]))
        monotonic_down = all(left > right for left, right in zip(pitches, pitches[1:]))
        common_overlap = min(note.offset_s for _, note in candidates) - candidates[-1][1].onset_s
        if (
            len(candidates) >= 3
            and 0.035 <= onset_spread <= 0.18
            and (monotonic_up or monotonic_down)
            and common_overlap >= 0.12
        ):
            group = {
                "group": group_number,
                "direction": "up" if monotonic_up else "down",
                "onset_s": candidates[0][1].onset_s,
                "spread_s": round(onset_spread, 6),
                "members": [index for index, _ in candidates],
            }
            for index, _ in candidates:
                groups[index] = group
            group_number += 1
        cursor += 1
    return groups


def _score_part(
    entries: list[dict[str, Any]],
    *,
    part_id: str,
    part_name: str,
    options: NotationOptions,
) -> Any:
    array = np.array(
        [
            (
                entry["onset_div"],
                entry["duration_div"],
                entry["pitch"],
                entry["xml_id"],
            )
            for entry in entries
        ],
        dtype=[
            ("onset_div", "i4"),
            ("duration_div", "i4"),
            ("pitch", "i4"),
            ("id", "U256"),
        ],
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        part = note_array_to_score(
            array,
            divs=DIVISIONS_PER_QUARTER,
            key_sigs=[[0, options.key]],
            time_sigs=[[0, options.meter_numerator, options.meter_denominator]],
            name_id=part_id,
            part_name=part_name,
            assign_note_ids=False,
            sanitize=True,
            return_part=True,
        )
    part.id = part_id
    return part, [str(item.message) for item in caught]


def _musicxml_bytes(
    notes: list[MidiNote],
    event_ids: list[str],
    options: NotationOptions,
) -> tuple[bytes, list[dict[str, Any]], list[str]]:
    grid_divisions = QUANTIZATION_DIVISIONS[options.quantization]
    arpeggios = _arpeggio_groups(notes)
    mappings: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for index, (note, event_id) in enumerate(zip(notes, event_ids)):
        onset_beats = (note.onset_s - options.first_beat_s) * options.tempo_bpm / 60.0
        duration_beats = (note.offset_s - note.onset_s) * options.tempo_bpm / 60.0
        onset_div = max(
            0,
            round(onset_beats * DIVISIONS_PER_QUARTER / grid_divisions)
            * grid_divisions,
        )
        duration_div = max(
            grid_divisions,
            round(duration_beats * DIVISIONS_PER_QUARTER / grid_divisions)
            * grid_divisions,
        )
        arpeggio = arpeggios.get(index)
        if arpeggio is not None:
            onset_div = max(
                0,
                round(
                    (
                        arpeggio["onset_s"] - options.first_beat_s
                    )
                    * options.tempo_bpm
                    / 60.0
                    * DIVISIONS_PER_QUARTER
                    / grid_divisions
                )
                * grid_divisions,
            )
        xml_id = f"src-{index:04d}-{hashlib.sha256(event_id.encode()).hexdigest()[:10]}"
        entry = {
            "source_index": index,
            "source_event_id": event_id,
            "xml_id": xml_id,
            "onset_div": int(onset_div),
            "duration_div": int(duration_div),
            "pitch": note.pitch,
            "staff": 1 if note.pitch >= options.staff_split_pitch else 2,
            "arpeggio": (
                {
                    key: arpeggio[key]
                    for key in ("group", "direction", "spread_s")
                }
                if arpeggio is not None
                else None
            ),
        }
        entries.append(entry)
        mappings.append(
            entry
            | {
                "source_onset_s": note.onset_s,
                "source_offset_s": note.offset_s,
                "source_velocity": note.velocity,
                "quantized_onset_beat": onset_div / DIVISIONS_PER_QUARTER,
                "quantized_duration_beat": duration_div / DIVISIONS_PER_QUARTER,
                "quantization_residual_s": round(
                    note.onset_s
                    - (
                        options.first_beat_s
                        + onset_div / DIVISIONS_PER_QUARTER * 60.0 / options.tempo_bpm
                    ),
                    6,
                ),
            }
        )

    parts = []
    conversion_warnings: list[str] = []
    for part_id, part_name, staff in (
        ("P1", "Right hand", 1),
        ("P2", "Left hand", 2),
    ):
        part_entries = [entry for entry in entries if entry["staff"] == staff]
        if not part_entries:
            continue
        part, part_warnings = _score_part(
            part_entries,
            part_id=part_id,
            part_name=part_name,
            options=options,
        )
        parts.append(part)
        conversion_warnings.extend(part_warnings)

    if len(parts) == 1:
        part_structure: Any = parts[0]
    else:
        group = PartGroup(
            group_symbol="brace",
            group_name="Piano",
            number=1,
            id="PG1",
        )
        group.children = parts
        for part in parts:
            part.parent = group
        part_structure = group

    score = Score(
        part_structure,
        id="atpiano-score",
        title="Atpiano performance notation",
        composer="Unattributed performance",
    )
    raw = partitura.save_musicxml(score)
    if not isinstance(raw, bytes):
        raw = raw.encode("utf-8")

    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
    root = etree.fromstring(raw, parser=parser)
    root.set("version", "4.0")
    notes_by_id = {
        element.get("id"): element
        for element in root.xpath("//*[local-name()='note'][@id]")
    }
    for mapping in mappings:
        if mapping["arpeggio"] is None:
            continue
        note_element = notes_by_id.get(mapping["xml_id"])
        if note_element is None:
            continue
        notations = note_element.find("notations")
        if notations is None:
            notations = etree.SubElement(note_element, "notations")
        etree.SubElement(
            notations,
            "arpeggiate",
            number=str(mapping["arpeggio"]["group"]),
            direction=mapping["arpeggio"]["direction"],
        )
    musicxml = etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
        doctype=MUSICXML_DOCTYPE,
    )
    unique_warnings = list(dict.fromkeys(conversion_warnings))
    return musicxml, mappings, unique_warnings


def summarize_musicxml(data: bytes) -> dict[str, Any]:
    if not data or len(data) > MUSICXML_MAX_BYTES:
        raise ValueError("MusicXML must be between 1 byte and 8 MiB")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        huge_tree=False,
    )
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as error:
        raise ValueError(f"MusicXML is not well formed: {error}") from error
    root_name = etree.QName(root).localname
    if root_name not in {"score-partwise", "score-timewise"}:
        raise ValueError("MusicXML root must be score-partwise or score-timewise")

    def text_values(xpath: str) -> list[str]:
        return sorted(
            {
                str(value).strip()
                for value in root.xpath(xpath)
                if str(value).strip()
            }
        )

    parts = root.xpath("//*[local-name()='part']")
    notes = root.xpath("//*[local-name()='note'][not(*[local-name()='rest'])]")
    measures_by_part = [
        len(part.xpath("./*[local-name()='measure']"))
        for part in parts
    ]
    return {
        "root": root_name,
        "version": root.get("version"),
        "parts": len(parts),
        "measures": max(measures_by_part, default=0),
        "pitched_note_elements": len(notes),
        "rests": len(root.xpath("//*[local-name()='note']/*[local-name()='rest']")),
        "voices": text_values("//*[local-name()='voice']/text()"),
        "staves": text_values("//*[local-name()='staff']/text()"),
        "time_signatures": sorted(
            {
                f"{beats}/{beat_type}"
                for beats, beat_type in zip(
                    root.xpath("//*[local-name()='time']/*[local-name()='beats']/text()"),
                    root.xpath(
                        "//*[local-name()='time']/*[local-name()='beat-type']/text()"
                    ),
                )
            }
        ),
        "key_fifths": [
            int(value)
            for value in text_values(
                "//*[local-name()='key']/*[local-name()='fifths']/text()"
            )
        ],
        "arpeggiate_marks": len(
            root.xpath("//*[local-name()='arpeggiate']")
        ),
    }


def generate_notation_artifacts(
    run_directory: Path,
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_directory = run_directory.resolve()
    prediction_path = run_directory / "prediction.json"
    notes = _notes_from_document(prediction_path)
    hypotheses = analyze_notation(notes)
    options = _validated_options(hypotheses, overrides)
    event_ids = _event_ids(run_directory, notes)
    musicxml, mappings, conversion_warnings = _musicxml_bytes(notes, event_ids, options)

    options_json = json.dumps(asdict(options), sort_keys=True, separators=(",", ":"))
    variant_id = hashlib.sha256(options_json.encode()).hexdigest()[:16]
    notation_directory = run_directory / "notation"
    notation_directory.mkdir(parents=True, exist_ok=True)
    musicxml_path = notation_directory / f"atpiano-{variant_id}.musicxml"
    variant_manifest_path = notation_directory / f"notation-{variant_id}.json"
    musicxml_path.write_bytes(musicxml)
    manifest: dict[str, Any] = {
        "schema_version": NOTATION_SCHEMA,
        "generated_at": utc_now(),
        "variant_id": variant_id,
        "source": {
            "artifact": "prediction.json",
            "sha256": sha256_file(prediction_path),
            "note_count": len(notes),
        },
        "converter": {
            "name": "atpiano-partitura-baseline-v1",
            "partitura_version": partitura.__version__,
            "musicxml_version": "4.0",
            "part_layout": "brace-grouped right-hand and left-hand parts",
        },
        "hypotheses": hypotheses,
        "selected": asdict(options),
        "warnings": conversion_warnings,
        "artifacts": {
            "musicxml": str(musicxml_path.relative_to(run_directory)),
            "musicxml_sha256": sha256_file(musicxml_path),
            "variant_manifest": str(variant_manifest_path.relative_to(run_directory)),
        },
        "summary": summarize_musicxml(musicxml),
        "source_mapping": mappings,
    }
    write_json(variant_manifest_path, manifest)
    write_json(notation_directory / "current.json", manifest)
    return manifest


def current_notation(run_directory: Path) -> dict[str, Any]:
    path = run_directory / "notation" / "current.json"
    if path.is_file():
        return read_json(path)
    return generate_notation_artifacts(run_directory)


def oracle_status(run_directory: Path) -> dict[str, Any]:
    path = run_directory / "oracle" / "oracle.json"
    if path.is_file():
        return read_json(path)
    return {
        "schema_version": ORACLE_SCHEMA,
        "service": {
            "id": "ivory",
            "name": "Ivory",
            "url": "https://ivory-app.com/",
            "reviewed_at": "2026-07-24",
            "workflow": "manual upload and unedited MusicXML export",
        },
        "lanes": {},
    }


def import_oracle_musicxml(
    run_directory: Path,
    *,
    lane: str,
    data: bytes,
    original_filename: str,
) -> dict[str, Any]:
    if lane not in {"audio", "midi"}:
        raise ValueError("oracle lane must be audio or midi")
    summary = summarize_musicxml(data)
    run_directory = run_directory.resolve()
    oracle_directory = run_directory / "oracle"
    oracle_directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    artifact_path = oracle_directory / f"ivory-{lane}-{digest[:16]}.musicxml"
    artifact_path.write_bytes(data)
    manifest = oracle_status(run_directory)
    manifest["updated_at"] = utc_now()
    manifest["lanes"][lane] = {
        "lane": lane,
        "input_kind": "original WAV" if lane == "audio" else "atpiano prediction MIDI",
        "imported_at": utc_now(),
        "original_filename": Path(original_filename).name,
        "artifact": str(artifact_path.relative_to(run_directory)),
        "sha256": digest,
        "summary": summary,
        "editing_policy": "import the first unedited MusicXML export",
    }
    write_json(oracle_directory / "oracle.json", manifest)
    return manifest
