"""Deterministic score-readability transforms for the isolated score runtime.

The cost and spelling functions in this module intentionally have no music21
dependency so the application test environment can exercise policy decisions.
The functions that mutate a score import music21 lazily and run only in the
pinned MIDI2ScoreTransformer environment.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

SCORE_POSTPROCESSOR_SCHEMA = "atpiano.score-postprocessor.v1"
SCORE_POSTPROCESSOR_VERSION = "deterministic-engraving-v1"

TREBLE_CLEF = "treble"
BASS_CLEF = "bass"
CLEF_NAMES = (TREBLE_CLEF, BASS_CLEF)

# Diatonic positions use C0 == 0. Only relative distance matters.
_STAFF_LIMITS = {
    TREBLE_CLEF: (4 * 7 + 2, 5 * 7 + 3),  # E4 through F5
    BASS_CLEF: (2 * 7 + 4, 3 * 7 + 5),  # G2 through A3
}
_STEP_INDEX = {step: index for index, step in enumerate("CDEFGAB")}
_NATURAL_PITCH_CLASS = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}
_MAJOR_NAMES = {
    -7: "C-flat major",
    -6: "G-flat major",
    -5: "D-flat major",
    -4: "A-flat major",
    -3: "E-flat major",
    -2: "B-flat major",
    -1: "F major",
    0: "C major",
    1: "G major",
    2: "D major",
    3: "A major",
    4: "E major",
    5: "B major",
    6: "F-sharp major",
    7: "C-sharp major",
}
_MINOR_NAMES = {
    -7: "A-flat minor",
    -6: "E-flat minor",
    -5: "B-flat minor",
    -4: "F minor",
    -3: "C minor",
    -2: "G minor",
    -1: "D minor",
    0: "A minor",
    1: "E minor",
    2: "B minor",
    3: "F-sharp minor",
    4: "C-sharp minor",
    5: "G-sharp minor",
    6: "D-sharp minor",
    7: "A-sharp minor",
}
_COUNT_NAMES = {
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
}


@dataclass(frozen=True)
class ClefPolicy:
    """Versioned cost constants for the first automatic clef policy."""

    change_penalty: int = 12
    preservation_penalty: int = 1
    severe_ledger_threshold: int = 3
    severe_ledger_multiplier: int = 4
    review_ledger_threshold: int = 3

    def as_dict(self) -> dict[str, int | str]:
        return {
            "name": "automatic-measure-v1",
            "change_penalty": self.change_penalty,
            "preservation_penalty": self.preservation_penalty,
            "severe_ledger_threshold": self.severe_ledger_threshold,
            "severe_ledger_multiplier": self.severe_ledger_multiplier,
            "review_ledger_threshold": self.review_ledger_threshold,
        }


DEFAULT_CLEF_POLICY = ClefPolicy()


def diatonic_position(step: str, octave: int) -> int:
    """Return a spelling-sensitive staff position."""

    normalized = step.upper()
    if normalized not in _STEP_INDEX:
        raise ValueError(f"unsupported pitch step: {step}")
    return octave * 7 + _STEP_INDEX[normalized]


def ledger_lines(position: int, clef_name: str) -> int:
    """Return the number of ledger lines required by one notehead."""

    if clef_name not in _STAFF_LIMITS:
        raise ValueError(f"unsupported clef: {clef_name}")
    bottom, top = _STAFF_LIMITS[clef_name]
    if position < bottom:
        return (bottom - position) // 2
    if position > top:
        return (position - top) // 2
    return 0


def _ledger_penalty(lines: int, policy: ClefPolicy) -> int:
    severe = max(0, lines - policy.severe_ledger_threshold + 1)
    return lines + policy.severe_ledger_multiplier * severe * severe


def ledger_metrics(
    positions: Iterable[int],
    clef_name: str,
    *,
    policy: ClefPolicy = DEFAULT_CLEF_POLICY,
) -> dict[str, int]:
    """Summarize raw ledger burden and the weighted optimization cost."""

    values = [ledger_lines(position, clef_name) for position in positions]
    return {
        "noteheads": len(values),
        "ledger_lines": sum(values),
        "weighted_cost": sum(_ledger_penalty(value, policy) for value in values),
        "maximum_ledger_lines": max(values, default=0),
        "noteheads_at_least_two": sum(value >= 2 for value in values),
        "noteheads_at_least_three": sum(value >= 3 for value in values),
    }


def _add_metrics(
    left: dict[str, int],
    right: dict[str, int],
) -> dict[str, int]:
    return {
        "noteheads": left["noteheads"] + right["noteheads"],
        "ledger_lines": left["ledger_lines"] + right["ledger_lines"],
        "weighted_cost": left["weighted_cost"] + right["weighted_cost"],
        "maximum_ledger_lines": max(
            left["maximum_ledger_lines"],
            right["maximum_ledger_lines"],
        ),
        "noteheads_at_least_two": (
            left["noteheads_at_least_two"] + right["noteheads_at_least_two"]
        ),
        "noteheads_at_least_three": (
            left["noteheads_at_least_three"]
            + right["noteheads_at_least_three"]
        ),
    }


def sequence_ledger_metrics(
    measure_positions: Sequence[Sequence[int]],
    clefs: Sequence[str],
    *,
    policy: ClefPolicy = DEFAULT_CLEF_POLICY,
) -> dict[str, int]:
    if len(measure_positions) != len(clefs):
        raise ValueError("clef sequence length differs from measures")
    total = ledger_metrics((), TREBLE_CLEF, policy=policy)
    for positions, clef_name in zip(measure_positions, clefs):
        total = _add_metrics(
            total,
            ledger_metrics(positions, clef_name, policy=policy),
        )
    return total


def optimize_clef_sequence(
    measure_positions: Sequence[Sequence[int]],
    baseline_clefs: Sequence[str],
    *,
    blocked_boundaries: Iterable[int] = (),
    policy: ClefPolicy = DEFAULT_CLEF_POLICY,
) -> tuple[str, ...]:
    """Choose treble/bass per measure using deterministic dynamic programming.

    ``blocked_boundaries`` contains measure indices at which the clef may not
    differ from the preceding measure, for example because a tie continues at
    that boundary.
    """

    if len(measure_positions) != len(baseline_clefs):
        raise ValueError("baseline clef sequence length differs from measures")
    if any(value not in CLEF_NAMES for value in baseline_clefs):
        raise ValueError("baseline contains an unsupported clef")
    if not measure_positions:
        return ()
    blocked = set(blocked_boundaries)
    blocked.update(
        index
        for index, positions in enumerate(measure_positions)
        if index > 0 and not positions
    )
    invalid = [index for index in blocked if index <= 0 or index >= len(measure_positions)]
    if invalid:
        raise ValueError("blocked clef boundary is outside the measure sequence")

    emissions = [
        {
            clef_name: ledger_metrics(
                positions,
                clef_name,
                policy=policy,
            )["weighted_cost"]
            for clef_name in CLEF_NAMES
        }
        for positions in measure_positions
    ]
    costs: list[dict[str, tuple[int, int, int, str | None]]] = []
    first: dict[str, tuple[int, int, int, str | None]] = {}
    for clef_name in CLEF_NAMES:
        preserve = (
            policy.preservation_penalty
            if measure_positions[0] and clef_name != baseline_clefs[0]
            else 0
        )
        first[clef_name] = (
            emissions[0][clef_name] + preserve,
            0,
            preserve,
            None,
        )
    costs.append(first)

    for index in range(1, len(measure_positions)):
        row: dict[str, tuple[int, int, int, str | None]] = {}
        for clef_name in CLEF_NAMES:
            preserve = (
                policy.preservation_penalty
                if measure_positions[index]
                and clef_name != baseline_clefs[index]
                else 0
            )
            candidates: list[tuple[int, int, int, int, str]] = []
            for prior_name in CLEF_NAMES:
                if index in blocked and prior_name != clef_name:
                    continue
                prior_cost, prior_changes, prior_preserve, _ = costs[index - 1][
                    prior_name
                ]
                changed = int(prior_name != clef_name)
                candidates.append(
                    (
                        prior_cost
                        + emissions[index][clef_name]
                        + preserve
                        + changed * policy.change_penalty,
                        prior_changes + changed,
                        prior_preserve + preserve,
                        0 if prior_name == baseline_clefs[index - 1] else 1,
                        prior_name,
                    )
                )
            best = min(candidates)
            row[clef_name] = (best[0], best[1], best[2], best[4])
        costs.append(row)

    final_name = min(
        CLEF_NAMES,
        key=lambda clef_name: (
            costs[-1][clef_name][0],
            costs[-1][clef_name][1],
            costs[-1][clef_name][2],
            0 if clef_name == baseline_clefs[-1] else 1,
            CLEF_NAMES.index(clef_name),
        ),
    )
    chosen = [final_name]
    for index in range(len(measure_positions) - 1, 0, -1):
        prior = costs[index][chosen[-1]][3]
        if prior is None:
            raise RuntimeError("clef optimizer lost its predecessor")
        chosen.append(prior)
    chosen.reverse()
    return tuple(chosen)


def clef_spans(
    sequence: Sequence[str],
    measure_labels: Sequence[str],
) -> list[dict[str, str]]:
    if len(sequence) != len(measure_labels):
        raise ValueError("measure labels differ from clef sequence")
    if not sequence:
        return []
    spans: list[dict[str, str]] = []
    start = 0
    for index in range(1, len(sequence) + 1):
        if index == len(sequence) or sequence[index] != sequence[start]:
            spans.append(
                {
                    "clef": sequence[start],
                    "start_measure": measure_labels[start],
                    "end_measure": measure_labels[index - 1],
                }
            )
            start = index
    return spans


def enharmonic_fifths(fifths: int) -> int | None:
    """Return the ordinary equivalent signature within seven accidentals."""

    if not -7 <= fifths <= 7:
        return None
    for candidate in (fifths + 12, fifths - 12):
        if -7 <= candidate <= 7:
            return candidate
    return None


def key_signature_label(fifths: int) -> str:
    if fifths not in _MAJOR_NAMES:
        raise ValueError("key signature must contain at most seven accidentals")
    accidental_count = abs(fifths)
    accidental = (
        "natural"
        if fifths == 0
        else "sharp"
        if fifths > 0
        else "flat"
    )
    signature = (
        "No sharps or flats"
        if fifths == 0
        else (
            f"{_COUNT_NAMES[accidental_count]} "
            f"{accidental}{'' if accidental_count == 1 else 's'}"
        )
    )
    return f"{signature} — {_MAJOR_NAMES[fifths]} / {_MINOR_NAMES[fifths]}"


def _natural_midi(step: str, octave: int) -> int:
    return (octave + 1) * 12 + _NATURAL_PITCH_CLASS[step]


def respell_pitch(
    step: str,
    alteration: int,
    octave: int,
    *,
    source_fifths: int,
    target_fifths: int,
) -> tuple[str, int, int]:
    """Respell one pitch along the diatonic mapping between paired keys."""

    normalized = step.upper()
    if normalized not in _STEP_INDEX or not isinstance(alteration, int):
        raise ValueError("pitch spelling is unsupported")
    if enharmonic_fifths(source_fifths) != target_fifths:
        raise ValueError("target key is not the supported enharmonic signature")
    direction = -1 if target_fifths > source_fifths else 1
    source_index = _STEP_INDEX[normalized]
    target_index = source_index + direction
    target_octave = octave
    if target_index < 0:
        target_index += 7
        target_octave -= 1
    elif target_index >= 7:
        target_index -= 7
        target_octave += 1
    target_step = "CDEFGAB"[target_index]
    sounding_midi = _natural_midi(normalized, octave) + alteration
    target_alteration = sounding_midi - _natural_midi(
        target_step,
        target_octave,
    )
    if abs(target_alteration) > 2:
        raise ValueError("enharmonic spelling requires an unsupported accidental")
    return target_step, target_alteration, target_octave


def score_variant_id(
    *,
    baseline_musicxml_sha256: str,
    baseline_alignment_sha256: str,
    options: dict[str, Any],
) -> str:
    identity = {
        "baseline_alignment_sha256": baseline_alignment_sha256,
        "baseline_musicxml_sha256": baseline_musicxml_sha256,
        "options": options,
        "postprocessor_version": SCORE_POSTPROCESSOR_VERSION,
    }
    encoded = json.dumps(
        identity,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"score-variant:{hashlib.sha256(encoded).hexdigest()[:24]}"


def normalized_options(
    *,
    clef_policy: str = "automatic",
    target_key_fifths: int | None = None,
) -> dict[str, Any]:
    if clef_policy not in {"automatic", "preserve"}:
        raise ValueError("unsupported clef policy")
    if target_key_fifths is not None and not -7 <= target_key_fifths <= 7:
        raise ValueError("target key signature is outside the supported range")
    return {
        "clef_policy": clef_policy,
        "target_key_fifths": target_key_fifths,
    }


def _score_key_signature(score: object) -> dict[str, Any]:
    from music21 import key

    part_values: list[int] = []
    for part in score.parts:
        signatures = list(part.recurse().getElementsByClass(key.KeySignature))
        if len(signatures) != 1:
            return {
                "eligible": False,
                "reason": "score does not have one global key signature per part",
                "source_fifths": None,
                "alternative_fifths": None,
            }
        signature = signatures[0]
        sharps = signature.sharps
        if (
            not isinstance(sharps, int)
            or not -7 <= sharps <= 7
            or Fraction(signature.getOffsetInHierarchy(part)) != 0
        ):
            return {
                "eligible": False,
                "reason": "score key signature is local or nontraditional",
                "source_fifths": None,
                "alternative_fifths": None,
            }
        part_values.append(sharps)
    if not part_values or len(set(part_values)) != 1:
        return {
            "eligible": False,
            "reason": "score parts have conflicting key signatures",
            "source_fifths": None,
            "alternative_fifths": None,
        }
    source = part_values[0]
    alternative = enharmonic_fifths(source)
    return {
        "eligible": alternative is not None,
        "reason": (
            None
            if alternative is not None
            else "key has no ordinary enharmonic signature within seven accidentals"
        ),
        "source_fifths": source,
        "source_label": key_signature_label(source),
        "alternative_fifths": alternative,
        "alternative_label": (
            key_signature_label(alternative)
            if alternative is not None
            else None
        ),
    }


def _component_pitch_values(score: object) -> list[object]:
    from music21 import chord

    values: list[object] = []
    for item in score.recurse().notes:
        values.extend(item.notes if isinstance(item, chord.Chord) else [item])
    return values


def _fraction_pair(value: object) -> tuple[int, int]:
    result = Fraction(value).limit_denominator(10_080 * 64)
    return result.numerator, result.denominator


def semantic_inventory(score: object) -> tuple[tuple[Any, ...], ...]:
    """Capture all score semantics that the first transforms must preserve."""

    from music21 import chord, stream

    inventory: list[tuple[Any, ...]] = []
    for part_number, part in enumerate(score.parts, start=1):
        for item_index, item in enumerate(part.recurse().notes):
            measure = item.getContextByClass(stream.Measure)
            voice = item.getContextByClass(stream.Voice)
            components = item.notes if isinstance(item, chord.Chord) else [item]
            for component_index, component in enumerate(components):
                inventory.append(
                    (
                        str(component.id),
                        part_number,
                        item_index,
                        component_index,
                        str(measure.number if measure is not None else ""),
                        str(voice.id if voice is not None else ""),
                        int(component.pitch.midi),
                        _fraction_pair(item.getOffsetInHierarchy(part)),
                        _fraction_pair(component.duration.quarterLength),
                        component.tie.type if component.tie is not None else None,
                        component.stemDirection,
                    )
                )
    return tuple(inventory)


def _meter_inventory(score: object) -> tuple[tuple[int, tuple[Any, ...]], ...]:
    from music21 import meter

    return tuple(
        (
            part_number,
            tuple(
                (
                    _fraction_pair(value.getOffsetInHierarchy(part)),
                    value.ratioString,
                )
                for value in part.recurse().getElementsByClass(
                    meter.TimeSignature
                )
            ),
        )
        for part_number, part in enumerate(score.parts, start=1)
    )


def assert_semantic_invariants(
    baseline_inventory: tuple[tuple[Any, ...], ...],
    baseline_meter_inventory: tuple[tuple[int, tuple[Any, ...]], ...],
    score: object,
) -> None:
    if semantic_inventory(score) != baseline_inventory:
        raise RuntimeError("score post-processing changed protected note semantics")
    if _meter_inventory(score) != baseline_meter_inventory:
        raise RuntimeError("score post-processing changed meter")


def apply_enharmonic_key(
    score: object,
    target_fifths: int,
) -> dict[str, Any]:
    from music21 import pitch

    key_state = _score_key_signature(score)
    source_fifths = key_state["source_fifths"]
    if not key_state["eligible"] or source_fifths is None:
        raise ValueError(str(key_state["reason"]))
    if key_state["alternative_fifths"] != target_fifths:
        raise ValueError("requested key is not the score's enharmonic alternative")

    before = [int(component.pitch.midi) for component in _component_pitch_values(score)]
    transformed = []
    for component in _component_pitch_values(score):
        accidental = component.pitch.accidental
        alteration = 0 if accidental is None else accidental.alter
        if int(alteration) != alteration or component.pitch.octave is None:
            raise ValueError("microtonal or octave-less pitch is unsupported")
        new_step, new_alteration, new_octave = respell_pitch(
            component.pitch.step,
            int(alteration),
            int(component.pitch.octave),
            source_fifths=source_fifths,
            target_fifths=target_fifths,
        )
        replacement = pitch.Pitch()
        replacement.step = new_step
        replacement.octave = new_octave
        replacement.accidental = (
            pitch.Accidental(new_alteration)
            if new_alteration
            else None
        )
        component.pitch = replacement
        transformed.append(
            {
                "step": new_step,
                "alter": new_alteration,
                "octave": new_octave,
            }
        )

    for part in score.parts:
        for signature in part.recurse().getElementsByClass("KeySignature"):
            signature.sharps = target_fifths
        for component in _component_pitch_values(part):
            if component.pitch.accidental is not None:
                component.pitch.accidental.displayStatus = None
        part.makeAccidentals(inPlace=True)

    after = [int(component.pitch.midi) for component in _component_pitch_values(score)]
    if before != after:
        raise RuntimeError("enharmonic transform changed sounding pitch")
    return {
        **key_state,
        "target_fifths": target_fifths,
        "target_label": key_signature_label(target_fifths),
        "respell_count": len(transformed),
    }


def _clef_name(value: object) -> str | None:
    from music21 import clef

    if isinstance(value, clef.TrebleClef):
        return TREBLE_CLEF
    if isinstance(value, clef.BassClef):
        return BASS_CLEF
    return None


def apply_automatic_clefs(
    score: object,
    *,
    policy: ClefPolicy = DEFAULT_CLEF_POLICY,
) -> dict[str, Any]:
    from music21 import chord, clef, stream

    part_reports: list[dict[str, Any]] = []
    total_before = ledger_metrics((), TREBLE_CLEF, policy=policy)
    total_after = ledger_metrics((), TREBLE_CLEF, policy=policy)
    warnings: list[str] = []
    for part_number, part in enumerate(score.parts, start=1):
        measures = list(part.getElementsByClass(stream.Measure))
        if not measures:
            continue
        active: str | None = None
        baseline: list[str] = []
        unsupported = False
        for measure in measures:
            local = list(measure.getElementsByClass(clef.Clef))
            if len(local) > 1 or any(Fraction(value.offset) != 0 for value in local):
                unsupported = True
                break
            if local:
                active = _clef_name(local[0])
                if active is None:
                    unsupported = True
                    break
            if active is None:
                best = _clef_name(clef.bestClef(part))
                active = best or (TREBLE_CLEF if part_number == 1 else BASS_CLEF)
            baseline.append(active)
        if unsupported:
            warning = f"part {part_number} has an unsupported clef layout"
            warnings.append(warning)
            part_reports.append(
                {
                    "part": part_number,
                    "status": "preserved",
                    "warning": warning,
                }
            )
            continue

        positions: list[list[int]] = []
        blocked: set[int] = set()
        for measure_index, measure in enumerate(measures):
            measure_positions: list[int] = []
            for item in measure.recurse().notes:
                components = item.notes if isinstance(item, chord.Chord) else [item]
                for component in components:
                    pitch_value = component.pitch
                    if pitch_value.octave is None:
                        raise ValueError("octave-less pitch is unsupported")
                    measure_positions.append(
                        diatonic_position(pitch_value.step, int(pitch_value.octave))
                    )
                    if (
                        measure_index > 0
                        and Fraction(item.getOffsetInHierarchy(measure)) == 0
                        and component.tie is not None
                        and component.tie.type in {"stop", "continue"}
                    ):
                        blocked.add(measure_index)
            positions.append(measure_positions)

        selected = optimize_clef_sequence(
            positions,
            baseline,
            blocked_boundaries=blocked,
            policy=policy,
        )
        before = sequence_ledger_metrics(positions, baseline, policy=policy)
        after = sequence_ledger_metrics(positions, selected, policy=policy)
        if after["weighted_cost"] > before["weighted_cost"]:
            raise RuntimeError("automatic clef policy increased ledger-line cost")

        for measure in measures:
            for value in list(measure.getElementsByClass(clef.Clef)):
                measure.remove(value)
        prior: str | None = None
        changes = 0
        for measure, clef_name in zip(measures, selected):
            if clef_name == prior:
                continue
            measure.insert(
                0,
                clef.TrebleClef()
                if clef_name == TREBLE_CLEF
                else clef.BassClef(),
            )
            if prior is not None:
                changes += 1
            prior = clef_name

        total_before = _add_metrics(total_before, before)
        total_after = _add_metrics(total_after, after)
        labels = [str(measure.number) for measure in measures]
        part_reports.append(
            {
                "part": part_number,
                "status": "optimized",
                "before": before,
                "after": after,
                "baseline_spans": clef_spans(baseline, labels),
                "selected_spans": clef_spans(selected, labels),
                "inserted_clef_changes": changes,
                "blocked_tie_boundaries": sorted(blocked),
            }
        )

    needs_review = (
        total_after["maximum_ledger_lines"] >= policy.review_ledger_threshold
        or total_after["noteheads_at_least_three"] > 0
        or bool(warnings)
    )
    return {
        "policy": policy.as_dict(),
        "before": total_before,
        "after": total_after,
        "parts": part_reports,
        "warnings": warnings,
        "needs_review": needs_review,
    }


def process_score(
    score: object,
    *,
    clef_policy: str = "automatic",
    target_key_fifths: int | None = None,
) -> dict[str, Any]:
    options = normalized_options(
        clef_policy=clef_policy,
        target_key_fifths=target_key_fifths,
    )
    baseline_notes = semantic_inventory(score)
    baseline_meter = _meter_inventory(score)
    key_state = _score_key_signature(score)
    key_report = key_state
    if target_key_fifths is not None:
        key_report = apply_enharmonic_key(score, target_key_fifths)
    clef_report = (
        apply_automatic_clefs(score)
        if clef_policy == "automatic"
        else {
            "policy": {"name": "preserve"},
            "warnings": [],
            "needs_review": False,
        }
    )
    assert_semantic_invariants(baseline_notes, baseline_meter, score)
    return {
        "schema_version": SCORE_POSTPROCESSOR_SCHEMA,
        "version": SCORE_POSTPROCESSOR_VERSION,
        "options": options,
        "key_signature": key_report,
        "clefs": clef_report,
        "needs_review": bool(clef_report["needs_review"]),
    }


def restore_note_ids(score: object, alignment: dict[str, Any]) -> None:
    """Restore MusicXML IDs that music21's importer does not retain."""

    from music21 import chord

    expected: dict[tuple[Any, ...], deque[str]] = defaultdict(deque)
    for row in alignment.get("rows", []):
        for segment in row.get("segments", []):
            key_value = (
                int(segment["part"]),
                int(segment["pitch"]),
                (
                    int(segment["score_time_quarters"]["numerator"]),
                    int(segment["score_time_quarters"]["denominator"]),
                ),
                (
                    int(segment["score_duration_quarters"]["numerator"]),
                    int(segment["score_duration_quarters"]["denominator"]),
                ),
                segment.get("tie"),
            )
            expected[key_value].append(str(segment["musicxml_note_id"]))
    for segment in alignment.get("inserted_score_segments", []):
        key_value = (
            int(segment["part"]),
            int(segment["pitch"]),
            (
                int(segment["score_time_quarters"]["numerator"]),
                int(segment["score_time_quarters"]["denominator"]),
            ),
            (
                int(segment["score_duration_quarters"]["numerator"]),
                int(segment["score_duration_quarters"]["denominator"]),
            ),
            segment.get("tie"),
        )
        expected[key_value].append(str(segment["musicxml_note_id"]))

    actual_count = 0
    for part_number, part in enumerate(score.parts, start=1):
        for item in part.recurse().notes:
            components = item.notes if isinstance(item, chord.Chord) else [item]
            for component in components:
                key_value = (
                    part_number,
                    int(component.pitch.midi),
                    _fraction_pair(item.getOffsetInHierarchy(part)),
                    _fraction_pair(component.duration.quarterLength),
                    component.tie.type if component.tie is not None else None,
                )
                identifiers = expected.get(key_value)
                if not identifiers:
                    raise RuntimeError(
                        "baseline MusicXML no longer matches score alignment"
                    )
                component.id = identifiers.popleft()
                actual_count += 1
    remaining = sum(len(values) for values in expected.values())
    if remaining or actual_count == 0:
        raise RuntimeError("score alignment note identities were not restored")
