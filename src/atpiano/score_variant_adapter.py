"""Isolated music21 entry point for deterministic score variants.

This adapter parses an immutable baseline MusicXML file and never imports or
invokes MIDI2ScoreTransformer. Keep imports from the atpiano package out of
this module so it can run in the pinned external score environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCORE_ALIGNMENT_SCHEMA = "atpiano.score-alignment.v2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-musicxml", type=Path, required=True)
    parser.add_argument("--input-alignment", type=Path, required=True)
    parser.add_argument("--output-musicxml", type=Path, required=True)
    parser.add_argument("--output-alignment", type=Path, required=True)
    parser.add_argument(
        "--clef-policy",
        choices=("automatic", "preserve"),
        default="automatic",
    )
    parser.add_argument("--target-key-fifths", type=int)
    args = parser.parse_args()

    for path in (args.input_musicxml, args.input_alignment):
        if not path.resolve().is_file():
            raise FileNotFoundError(path)
    alignment = json.loads(
        args.input_alignment.resolve().read_text(encoding="utf-8")
    )
    if alignment.get("schema_version") != SCORE_ALIGNMENT_SCHEMA:
        raise ValueError("score alignment schema is unsupported")
    if alignment.get("musicxml", {}).get("sha256") != _sha256(
        args.input_musicxml.resolve()
    ):
        raise ValueError("baseline alignment names different MusicXML")

    from music21 import converter
    from score_postprocess import process_score, restore_note_ids

    score = converter.parse(str(args.input_musicxml.resolve()))
    restore_note_ids(score, alignment)
    report = process_score(
        score,
        clef_policy=args.clef_policy,
        target_key_fifths=args.target_key_fifths,
    )

    output_musicxml = args.output_musicxml.resolve()
    output_musicxml.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(output_musicxml))
    if not output_musicxml.is_file() or output_musicxml.stat().st_size == 0:
        raise RuntimeError("score postprocessor produced empty MusicXML")

    derived_alignment = dict(alignment)
    derived_alignment["musicxml"] = {"sha256": _sha256(output_musicxml)}
    output_alignment = args.output_alignment.resolve()
    output_alignment.parent.mkdir(parents=True, exist_ok=True)
    output_alignment.write_text(
        json.dumps(derived_alignment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": "atpiano.score-variant-adapter.v1",
                "musicxml_bytes": output_musicxml.stat().st_size,
                "musicxml_sha256": _sha256(output_musicxml),
                "alignment_bytes": output_alignment.stat().st_size,
                "alignment_sha256": _sha256(output_alignment),
                "postprocess": report,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
