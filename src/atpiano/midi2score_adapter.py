"""Isolated MIDI2ScoreTransformer inference entry point.

This file is executed by the ignored Python 3.11 score runtime. Keep imports
from atpiano out of this module so the external environment only needs the
upstream model stack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

SCORE_INPUT_NOTES_SCHEMA = "atpiano.score-input-notes.v1"
SCORE_ALIGNMENT_SCHEMA = "atpiano.score-alignment.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _rational(value: object) -> dict[str, int]:
    fraction = Fraction(value).limit_denominator(10_080 * 64)
    return {
        "numerator": fraction.numerator,
        "denominator": fraction.denominator,
    }


def _event_xml_id(event_id: str, segment: int) -> str:
    digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:20]
    return f"atpiano-{digest}-{segment:03d}"


def _read_source_notes(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != SCORE_INPUT_NOTES_SCHEMA:
        raise ValueError("score input-note schema is unsupported")
    sample_rate_hz = document.get("sample_rate_hz")
    notes = document.get("notes")
    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("score input-note sample rate is invalid")
    if not isinstance(notes, list) or not notes:
        raise ValueError("score input-note list is empty")
    for index, item in enumerate(notes):
        if (
            not isinstance(item, dict)
            or item.get("source_index") != index
            or not isinstance(item.get("event_id"), str)
            or not isinstance(item.get("pitch"), int)
            or not isinstance(item.get("onset_sample"), int)
            or not isinstance(item.get("offset_sample"), int)
        ):
            raise ValueError("score input-note row is invalid")
    return document


def _verify_midi_order(source: dict, midi_sequence: list) -> None:
    notes = source["notes"]
    if len(notes) != len(midi_sequence):
        raise ValueError("score input-note count differs from MIDI")
    sample_rate_hz = source["sample_rate_hz"]
    tolerance_s = 0.002
    for item, midi_note in zip(notes, midi_sequence):
        onset_s = item["onset_sample"] / sample_rate_hz
        offset_s = item["offset_sample"] / sample_rate_hz
        if (
            item["pitch"] != midi_note.pitch
            or abs(onset_s - midi_note.start) > tolerance_s
            or abs(offset_s - midi_note.end) > tolerance_s
        ):
            raise ValueError("score input-note order differs from MIDI")


def _tag_transformer_notes(
    tokenizer_module,
    token_output: dict,
    *,
    source_count: int,
) -> object:
    from tokenizer import one_hot_unbucketing

    mask = token_output["pad"].reshape(-1) > 0.5
    retained_output_indices = [
        index for index, keep in enumerate(mask.tolist()) if keep
    ]
    hands = one_hot_unbucketing(
        token_output["hand"][mask][:, :2],
        0,
        2,
        3,
    ).numpy().astype(int)
    creation_order = [
        retained_output_indices[index]
        for part in range(2)
        for index, hand in enumerate(hands)
        if hand == part
    ]
    original_note = tokenizer_module.note.Note
    created: list[int] = []

    def aligned_note(*args, **kwargs):
        if len(created) >= len(creation_order):
            raise RuntimeError("score detokenizer created an unexpected note")
        value = original_note(*args, **kwargs)
        output_index = creation_order[len(created)]
        value.id = (
            f"atpiano-token-{output_index:06d}"
            if output_index < source_count
            else f"atpiano-inserted-{output_index:06d}"
        )
        created.append(output_index)
        return value

    tokenizer_module.note.Note = aligned_note
    try:
        score = tokenizer_module.MultistreamTokenizer.detokenize_mxl(token_output)
    finally:
        tokenizer_module.note.Note = original_note
    if created != creation_order:
        raise RuntimeError("score detokenizer note identity order differs")
    return score


def _alignment_rows(
    score,
    source: dict,
) -> tuple[list[dict], list[dict]]:
    from music21 import chord

    segments_by_source: dict[int, list[dict]] = defaultdict(list)
    segment_counts: dict[int, int] = defaultdict(int)
    inserted_segments: list[dict] = []
    inserted_segment_counts: dict[int, int] = defaultdict(int)
    for part_number, part in enumerate(score.parts, start=1):
        for value in part.recurse().notes:
            score_time = value.getOffsetInHierarchy(part)
            components = value.notes if isinstance(value, chord.Chord) else [value]
            for component in components:
                identifier = str(component.id)
                source_prefix = "atpiano-token-"
                inserted_prefix = "atpiano-inserted-"
                if identifier.startswith(inserted_prefix):
                    output_index = int(identifier[len(inserted_prefix) :])
                    segment = inserted_segment_counts[output_index]
                    inserted_segment_counts[output_index] += 1
                    xml_id = (
                        f"atpiano-inserted-{output_index:06d}-{segment:03d}"
                    )
                    component.id = xml_id
                    inserted_segments.append(
                        {
                            "output_index": output_index,
                            "musicxml_note_id": xml_id,
                            "part": part_number,
                            "pitch": int(component.pitch.midi),
                            "score_time_quarters": _rational(score_time),
                            "score_duration_quarters": _rational(
                                component.duration.quarterLength
                            ),
                            "tie": (
                                component.tie.type
                                if component.tie is not None
                                else None
                            ),
                        }
                    )
                    continue
                if not identifier.startswith(source_prefix):
                    raise RuntimeError("post-processed score note lost source identity")
                source_index = int(identifier[len(source_prefix) :])
                segment = segment_counts[source_index]
                segment_counts[source_index] += 1
                xml_id = _event_xml_id(
                    source["notes"][source_index]["event_id"],
                    segment,
                )
                component.id = xml_id
                segments_by_source[source_index].append(
                    {
                        "musicxml_note_id": xml_id,
                        "part": part_number,
                        "pitch": int(component.pitch.midi),
                        "score_time_quarters": _rational(score_time),
                        "score_duration_quarters": _rational(
                            component.duration.quarterLength
                        ),
                        "tie": (
                            component.tie.type
                            if component.tie is not None
                            else None
                        ),
                    }
                )

    rows = []
    for item in source["notes"]:
        source_index = item["source_index"]
        segments = sorted(
            segments_by_source.get(source_index, []),
            key=lambda segment: (
                Fraction(
                    segment["score_time_quarters"]["numerator"],
                    segment["score_time_quarters"]["denominator"],
                ),
                segment["part"],
                segment["musicxml_note_id"],
            ),
        )
        base = {
            "source_index": source_index,
            "event_id": item["event_id"],
            "pitch": item["pitch"],
            "onset_sample": item["onset_sample"],
            "offset_sample": item["offset_sample"],
        }
        if segments:
            rows.append(
                base
                | {
                    "status": "mapped",
                    "score_time_quarters": segments[0][
                        "score_time_quarters"
                    ],
                    "segments": segments,
                }
            )
        else:
            rows.append(
                base
                | {
                    "status": "unmatched",
                    "score_time_quarters": None,
                    "segments": [],
                }
            )
    inserted_segments.sort(
        key=lambda segment: (
            Fraction(
                segment["score_time_quarters"]["numerator"],
                segment["score_time_quarters"]["denominator"],
            ),
            segment["output_index"],
            segment["musicxml_note_id"],
        )
    )
    return rows, inserted_segments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input-midi", type=Path, required=True)
    parser.add_argument("--input-notes", type=Path, required=True)
    parser.add_argument("--output-musicxml", type=Path, required=True)
    parser.add_argument("--output-alignment", type=Path, required=True)
    args = parser.parse_args()

    module_root = args.repository.resolve() / "midi2scoretransformer"
    if not module_root.is_dir():
        raise FileNotFoundError(f"MIDI2ScoreTransformer module directory is missing: {module_root}")
    for path in (args.checkpoint, args.input_midi, args.input_notes):
        if not path.resolve().is_file():
            raise FileNotFoundError(path)
    sys.path.insert(0, str(module_root))

    import tokenizer
    import torch
    from config import MyModelConfig
    from models.roformer import Roformer
    from music21 import defaults, metadata
    from score_utils import postprocess_score
    from tokenizer import MultistreamTokenizer
    from utils import infer

    started = time.perf_counter()
    source = _read_source_notes(args.input_notes.resolve())
    midi_sequence = MultistreamTokenizer.midi_to_list(
        str(args.input_midi.resolve())
    )
    _verify_midi_order(source, midi_sequence)
    torch.serialization.add_safe_globals([MyModelConfig])
    model = Roformer.load_from_checkpoint(
        str(args.checkpoint.resolve()),
        map_location="cpu",
        weights_only=False,
    )
    model.to("cpu")
    model.eval()
    token_input = MultistreamTokenizer.tokenize_midi(
        str(args.input_midi.resolve())
    )
    token_output = infer(
        token_input,
        model,
        overlap=64,
        chunk=512,
        kv_cache=True,
        verbose=False,
    )
    score = _tag_transformer_notes(
        tokenizer,
        token_output,
        source_count=len(source["notes"]),
    )
    score = postprocess_score(score)
    rows, inserted_score_segments = _alignment_rows(score, source)
    score.metadata = metadata.Metadata()
    score.metadata.title = "Performance"
    defaults.author = ""
    output_path = args.output_musicxml.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(output_path))
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("MIDI2ScoreTransformer produced empty MusicXML")
    mapped = sum(row["status"] == "mapped" for row in rows)
    unmatched = len(rows) - mapped
    note_elements = sum(len(row["segments"]) for row in rows)
    note_elements += len(inserted_score_segments)
    alignment = {
        "schema_version": SCORE_ALIGNMENT_SCHEMA,
        "session_id": source["session_id"],
        "sample_rate_hz": source["sample_rate_hz"],
        "source": {
            "schema_version": SCORE_INPUT_NOTES_SCHEMA,
            "sha256": _sha256(args.input_notes.resolve()),
        },
        "musicxml": {
            "sha256": _sha256(output_path),
        },
        "summary": {
            "source_notes": len(rows),
            "mapped_source_notes": mapped,
            "unmatched_source_notes": unmatched,
            "musicxml_note_elements": note_elements,
            "inserted_score_note_elements": len(inserted_score_segments),
        },
        "rows": rows,
        "inserted_score_segments": inserted_score_segments,
    }
    alignment_path = args.output_alignment.resolve()
    alignment_path.parent.mkdir(parents=True, exist_ok=True)
    alignment_path.write_text(
        json.dumps(alignment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": "atpiano.midi2score-adapter.v1",
                "device": "cpu",
                "elapsed_s": time.perf_counter() - started,
                "musicxml_bytes": output_path.stat().st_size,
                "musicxml_sha256": _sha256(output_path),
                "alignment_bytes": alignment_path.stat().st_size,
                "alignment_sha256": _sha256(alignment_path),
                "mapped_source_notes": mapped,
                "unmatched_source_notes": unmatched,
                "inserted_score_note_elements": len(
                    inserted_score_segments
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
