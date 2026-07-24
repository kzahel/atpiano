"""Transcription-quality scoring."""

from __future__ import annotations

from typing import Any

import mir_eval.transcription
import numpy as np

from atpiano.midi import MidiNote, midi_to_hz


def _arrays(notes: list[MidiNote]) -> tuple[np.ndarray, np.ndarray]:
    intervals = np.asarray(
        [(note.onset_s, note.offset_s) for note in notes],
        dtype=np.float64,
    ).reshape((-1, 2))
    pitches = np.asarray([midi_to_hz(note.pitch) for note in notes], dtype=np.float64)
    return intervals, pitches


def match_note_indices(
    reference: list[MidiNote],
    estimate: list[MidiNote],
    *,
    onset_tolerance_s: float = 0.05,
    offset_ratio: float | None = None,
) -> list[tuple[int, int]]:
    reference_intervals, reference_pitches = _arrays(reference)
    estimate_intervals, estimate_pitches = _arrays(estimate)
    return mir_eval.transcription.match_notes(
        reference_intervals,
        reference_pitches,
        estimate_intervals,
        estimate_pitches,
        onset_tolerance=onset_tolerance_s,
        offset_ratio=offset_ratio,
    )


def _prf(reference_count: int, estimate_count: int, match_count: int) -> dict[str, Any]:
    precision = match_count / estimate_count if estimate_count else 0.0
    recall = match_count / reference_count if reference_count else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "matches": match_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _frame_scores(
    reference: list[MidiNote],
    estimate: list[MidiNote],
    *,
    frame_hz: int = 100,
) -> dict[str, Any]:
    duration_s = max(
        [0.0]
        + [note.offset_s for note in reference]
        + [note.offset_s for note in estimate]
    )
    frame_count = max(1, int(np.ceil(duration_s * frame_hz)))
    reference_roll = np.zeros((frame_count, 88), dtype=np.bool_)
    estimate_roll = np.zeros((frame_count, 88), dtype=np.bool_)
    for roll, notes in ((reference_roll, reference), (estimate_roll, estimate)):
        for note in notes:
            if not 21 <= note.pitch <= 108:
                continue
            start = max(0, int(np.floor(note.onset_s * frame_hz)))
            end = min(frame_count, max(start + 1, int(np.ceil(note.offset_s * frame_hz))))
            roll[start:end, note.pitch - 21] = True
    true_positive = int(np.count_nonzero(reference_roll & estimate_roll))
    false_positive = int(np.count_nonzero(~reference_roll & estimate_roll))
    false_negative = int(np.count_nonzero(reference_roll & ~estimate_roll))
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "frame_hz": frame_hz,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive_frames": true_positive,
        "false_positive_frames": false_positive,
        "false_negative_frames": false_negative,
    }


def score_notes(reference: list[MidiNote], estimate: list[MidiNote]) -> dict[str, Any]:
    reference_intervals, reference_pitches = _arrays(reference)
    estimate_intervals, estimate_pitches = _arrays(estimate)
    onset_metrics: dict[str, Any] = {}
    matches_at_50_ms: list[tuple[int, int]] = []
    for tolerance_s, label in ((0.05, "50_ms"), (0.025, "25_ms")):
        matches = match_note_indices(
            reference,
            estimate,
            onset_tolerance_s=tolerance_s,
        )
        onset_metrics[label] = _prf(len(reference), len(estimate), len(matches))
        if tolerance_s == 0.05:
            matches_at_50_ms = matches

    offset_matches = match_note_indices(
        reference,
        estimate,
        onset_tolerance_s=0.05,
        offset_ratio=0.2,
    )
    velocity_errors = [
        abs(reference[reference_index].velocity - estimate[estimate_index].velocity)
        for reference_index, estimate_index in matches_at_50_ms
    ]
    onset_errors_ms = [
        1000.0
        * abs(reference[reference_index].onset_s - estimate[estimate_index].onset_s)
        for reference_index, estimate_index in matches_at_50_ms
    ]
    return {
        "schema_version": "atpiano.scores.v1",
        "quality_available": True,
        "reference_note_count": len(reference),
        "estimated_note_count": len(estimate),
        "onset": onset_metrics,
        "note_with_offset": _prf(len(reference), len(estimate), len(offset_matches)),
        "frame": _frame_scores(reference, estimate),
        "matched_onset_error_ms": {
            "mean": float(np.mean(onset_errors_ms)) if onset_errors_ms else None,
            "max": float(np.max(onset_errors_ms)) if onset_errors_ms else None,
        },
        "matched_velocity_mae": (
            float(np.mean(velocity_errors)) if velocity_errors else None
        ),
        "pedal": {
            "supported_by_model": False,
            "metrics": None,
        },
    }


def unscored_notes(estimate: list[MidiNote]) -> dict[str, Any]:
    unavailable = {
        "matches": None,
        "precision": None,
        "recall": None,
        "f1": None,
    }
    return {
        "schema_version": "atpiano.scores.v1",
        "quality_available": False,
        "quality_unavailable_reason": "input has no aligned reference MIDI",
        "reference_note_count": None,
        "estimated_note_count": len(estimate),
        "onset": {
            "50_ms": dict(unavailable),
            "25_ms": dict(unavailable),
        },
        "note_with_offset": dict(unavailable),
        "frame": {
            "frame_hz": 100,
            "precision": None,
            "recall": None,
            "f1": None,
            "true_positive_frames": None,
            "false_positive_frames": None,
            "false_negative_frames": None,
        },
        "matched_onset_error_ms": {
            "mean": None,
            "max": None,
        },
        "matched_velocity_mae": None,
        "pedal": {
            "supported_by_model": False,
            "metrics": None,
        },
    }
