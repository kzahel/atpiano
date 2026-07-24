"""Re-decode retained Basic Pitch arrays without rerunning inference."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from atpiano.decoder import (
    NO_MELODIA_DECODER_POLICY,
    STOCK_DECODER_POLICY,
    STRICT_ONSET_DECODER_POLICY,
    BasicPitchDecoderPolicy,
    DecodedNote,
    decode_basic_pitch_output,
    strict_onset_policy,
)
from atpiano.midi import MidiNote
from atpiano.quality import score_notes
from atpiano.util import read_json, runtime_provenance, sha256_file, utc_now, write_json

DECODER_STUDY_SCHEMA = "atpiano.basic-pitch-decoder-study.v1"
STRICT_THRESHOLDS = (0.4, 0.5, 0.6, 0.7, 0.8)


def run_decoder_study(
    output_directory: Path,
    cases: list[tuple[str, Path]],
) -> dict[str, Any]:
    """Compare declared policies over retained full-file native arrays."""
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    policies = [
        STOCK_DECODER_POLICY,
        NO_MELODIA_DECODER_POLICY,
        *(strict_onset_policy(threshold) for threshold in STRICT_THRESHOLDS),
    ]
    case_results = [_analyze_case(label, path.resolve(), policies) for label, path in cases]
    result = {
        "schema_version": DECODER_STUDY_SCHEMA,
        "created_at": utc_now(),
        "runtime": runtime_provenance(),
        "policies": [policy.provenance() for policy in policies],
        "cases": case_results,
        "selection": {
            "live_decoder": STRICT_ONSET_DECODER_POLICY.provenance(),
            "reattack_policy": None,
            "basis": (
                "The selected policy is the lowest tested strict threshold with "
                "perfect 25/50 ms onset precision and recall on the aligned "
                "19-note fixture. No same-pitch refractory or source-attack "
                "gate is selected because the retained acoustic examples do "
                "not provide aligned held-versus-reattack ground truth."
            ),
        },
        "limitations": [
            (
                "Unaligned acoustic note-count reductions are evidence of a "
                "less busy decoder, not proof that every removed note was false."
            ),
            (
                "The deterministic fixture protects known repeated strikes and "
                "polyphony but is not acoustic-piano ground truth."
            ),
        ],
    }
    write_json(output_directory / "decoder-study.json", result)
    (output_directory / "report.md").write_text(
        _report(result),
        encoding="utf-8",
    )
    return result


def _analyze_case(
    label: str,
    run_directory: Path,
    policies: list[BasicPitchDecoderPolicy],
) -> dict[str, Any]:
    raw_path = run_directory / "raw" / "basic_pitch.npz"
    audio_path = run_directory / "input.wav"
    if not raw_path.is_file():
        raise FileNotFoundError(f"missing retained output: {raw_path}")
    if not audio_path.is_file():
        raise FileNotFoundError(f"missing source audio: {audio_path}")
    with np.load(raw_path) as loaded:
        output = {name: loaded[name].copy() for name in loaded.files}
    audio, sample_rate_hz = sf.read(
        audio_path,
        dtype="float32",
        always_2d=True,
    )
    mono = np.mean(audio, axis=1, dtype=np.float32)
    duration_s = mono.shape[0] / sample_rate_hz
    reference = _reference_notes(run_directory)
    return {
        "label": label,
        "run_directory": str(run_directory),
        "source": {
            "audio_path": str(audio_path),
            "audio_sha256": sha256_file(audio_path),
            "raw_output_path": str(raw_path),
            "raw_output_sha256": sha256_file(raw_path),
            "sample_rate_hz": sample_rate_hz,
            "frame_count": mono.shape[0],
            "duration_s": duration_s,
            "reference_note_count": None if reference is None else len(reference),
        },
        "variants": [
            _analyze_variant(
                output,
                policy,
                audio=mono,
                sample_rate_hz=sample_rate_hz,
                duration_s=duration_s,
                reference=reference,
            )
            for policy in policies
        ],
    }


def _reference_notes(run_directory: Path) -> list[MidiNote] | None:
    path = run_directory / "reference.json"
    if not path.is_file():
        return None
    scores_path = run_directory / "scores.json"
    if scores_path.is_file() and not read_json(scores_path).get(
        "quality_available",
        False,
    ):
        return None
    document = read_json(path)
    return [
        MidiNote(
            onset_s=float(note["onset_s"]),
            offset_s=float(note["offset_s"]),
            pitch=int(note["pitch"]),
            velocity=int(note["velocity"]),
        )
        for note in document["notes"]
    ]


def _analyze_variant(
    output: dict[str, np.ndarray],
    policy: BasicPitchDecoderPolicy,
    *,
    audio: np.ndarray,
    sample_rate_hz: int,
    duration_s: float,
    reference: list[MidiNote] | None,
) -> dict[str, Any]:
    decoded = decode_basic_pitch_output(output, policy)
    notes = [item.note for item in decoded]
    evidence = [
        _candidate_evidence(item, audio=audio, sample_rate_hz=sample_rate_hz)
        for item in decoded
    ]
    novelty_values = [row["attack_novelty_db"] for row in evidence]
    result: dict[str, Any] = {
        "policy": policy.provenance(),
        "note_count": len(notes),
        "notes_per_second": len(notes) / duration_s if duration_s else 0.0,
        "same_pitch_restarts": _same_pitch_restarts(notes),
        "pitch_histogram": {
            str(pitch): count
            for pitch, count in sorted(Counter(note.pitch for note in notes).items())
        },
        "onset_source_counts": dict(
            sorted(Counter(item.source for item in decoded).items())
        ),
        "onset_confidence": _summary(
            [item.onset_confidence for item in decoded]
        ),
        "frame_confidence": _summary(
            [item.frame_confidence for item in decoded]
        ),
        "attack_novelty_db": {
            **_summary(novelty_values),
            "retained_at_or_above": {
                str(threshold): sum(value >= threshold for value in novelty_values)
                for threshold in (0.0, 3.0, 6.0)
            },
            "window_s": {
                "pre": [-0.18, -0.03],
                "post": [-0.02, 0.10],
            },
        },
        "candidates": evidence,
        "scores": None if reference is None else score_notes(reference, notes),
    }
    return result


def _candidate_evidence(
    decoded: DecodedNote,
    *,
    audio: np.ndarray,
    sample_rate_hz: int,
) -> dict[str, Any]:
    onset_sample = round(decoded.note.onset_s * sample_rate_hz)
    pre = _audio_slice(
        audio,
        onset_sample + round(-0.18 * sample_rate_hz),
        onset_sample + round(-0.03 * sample_rate_hz),
    )
    post = _audio_slice(
        audio,
        onset_sample + round(-0.02 * sample_rate_hz),
        onset_sample + round(0.10 * sample_rate_hz),
    )
    pre_dbfs = _rms_dbfs(pre)
    post_dbfs = _rms_dbfs(post)
    return {
        **asdict(decoded.note),
        "start_frame": decoded.start_frame,
        "end_frame": decoded.end_frame,
        "frame_confidence": decoded.frame_confidence,
        "onset_confidence": decoded.onset_confidence,
        "decoder_confidence": decoded.decoder_confidence,
        "onset_source": decoded.source,
        "pre_attack_dbfs": pre_dbfs,
        "post_attack_dbfs": post_dbfs,
        "attack_novelty_db": post_dbfs - pre_dbfs,
    }


def _audio_slice(audio: np.ndarray, start: int, end: int) -> np.ndarray:
    return audio[max(0, start) : min(audio.shape[0], end)]


def _rms_dbfs(audio: np.ndarray) -> float:
    if audio.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    return 20 * float(np.log10(max(rms, 1e-6)))


def _same_pitch_restarts(notes: list[MidiNote]) -> dict[str, int]:
    by_pitch: defaultdict[int, list[float]] = defaultdict(list)
    for note in notes:
        by_pitch[note.pitch].append(note.onset_s)
    gaps = [
        current - previous
        for onsets in by_pitch.values()
        for previous, current in zip(sorted(onsets), sorted(onsets)[1:])
    ]
    return {
        "under_250_ms": sum(gap < 0.25 for gap in gaps),
        "under_500_ms": sum(gap < 0.5 for gap in gaps),
        "under_1000_ms": sum(gap < 1.0 for gap in gaps),
    }


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "p50": None,
            "p95": None,
            "maximum": None,
        }
    return {
        "count": len(values),
        "minimum": min(values),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "maximum": max(values),
    }


def _report(result: dict[str, Any]) -> str:
    lines = [
        "# Basic Pitch Decoder Study",
        "",
        "| Case | Policy | Notes | Restarts <1s | Onset F1 @25ms |",
        "|---|---|---:|---:|---:|",
    ]
    for case in result["cases"]:
        for variant in case["variants"]:
            scores = variant["scores"]
            f1 = (
                "—"
                if scores is None
                else f"{scores['onset']['25_ms']['f1']:.3f}"
            )
            lines.append(
                f"| {case['label']} | {variant['policy']['name']} | "
                f"{variant['note_count']} | "
                f"{variant['same_pitch_restarts']['under_1000_ms']} | {f1} |"
            )
    lines.extend(
        [
            "",
            "Selected live decoder: "
            f"`{result['selection']['live_decoder']['name']}`.",
            "",
            result["selection"]["basis"],
            "",
        ]
    )
    return "\n".join(lines)
