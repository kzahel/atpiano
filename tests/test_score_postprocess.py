from __future__ import annotations

import numpy as np
import pytest

from atpiano.score_postprocess import (
    BASS_CLEF,
    TREBLE_CLEF,
    clef_spans,
    diatonic_position,
    enharmonic_fifths,
    key_signature_label,
    ledger_lines,
    ledger_metrics,
    normalized_options,
    optimize_clef_sequence,
    respell_pitch,
    score_variant_id,
    sequence_ledger_metrics,
    traditional_fifths,
)


def _positions(*names: tuple[str, int]) -> list[int]:
    return [diatonic_position(step, octave) for step, octave in names]


def test_ledger_lines_follow_spelled_staff_position() -> None:
    assert ledger_lines(diatonic_position("E", 4), TREBLE_CLEF) == 0
    assert ledger_lines(diatonic_position("C", 4), TREBLE_CLEF) == 1
    assert ledger_lines(diatonic_position("B", 4), BASS_CLEF) == 4
    assert ledger_lines(diatonic_position("E", 2), BASS_CLEF) == 1

    sharp = diatonic_position("F", 4)
    flat = diatonic_position("G", 4)
    assert ledger_lines(sharp, BASS_CLEF) == 2
    assert ledger_lines(flat, BASS_CLEF) == 3


def test_clef_optimizer_changes_sustained_ranges_without_flicker() -> None:
    high = _positions(("E", 4), ("G", 4), ("B", 4), ("D", 5))
    low = _positions(("C", 3), ("E", 3), ("G", 3), ("B", 3))
    positions = [high] * 5 + [[]] + [low] * 5
    baseline = [BASS_CLEF] * len(positions)

    selected = optimize_clef_sequence(positions, baseline)

    assert selected[:6] == (TREBLE_CLEF,) * 6
    assert selected[6:] == (BASS_CLEF,) * 5
    assert clef_spans(selected, [str(index + 1) for index in range(11)]) == [
        {"clef": "treble", "start_measure": "1", "end_measure": "6"},
        {"clef": "bass", "start_measure": "7", "end_measure": "11"},
    ]
    before = sequence_ledger_metrics(positions, baseline)
    after = sequence_ledger_metrics(positions, selected)
    assert after["weighted_cost"] < before["weighted_cost"]


def test_clef_optimizer_preserves_tied_boundary_and_small_excursion() -> None:
    low = _positions(("C", 3), ("E", 3), ("G", 3))
    high = _positions(("G", 4))
    positions = [low, high, low]
    baseline = [BASS_CLEF] * 3

    assert optimize_clef_sequence(positions, baseline) == (BASS_CLEF,) * 3
    assert optimize_clef_sequence(
        [high, high, low],
        baseline,
        blocked_boundaries={1},
    )[:2] in {
        (TREBLE_CLEF, TREBLE_CLEF),
        (BASS_CLEF, BASS_CLEF),
    }


def test_chord_noteheads_each_contribute_to_readability_cost() -> None:
    positions = _positions(("C", 4), ("E", 4), ("G", 4), ("B", 4))
    metrics = ledger_metrics(positions, BASS_CLEF)

    assert metrics["noteheads"] == 4
    assert metrics["noteheads_at_least_two"] == 3
    assert metrics["noteheads_at_least_three"] == 2
    assert metrics["maximum_ledger_lines"] == 4


@pytest.mark.parametrize(
    ("source", "target"),
    [(-7, 5), (-6, 6), (-5, 7), (5, -7), (6, -6), (7, -5)],
)
def test_enharmonic_signature_pairs(source: int, target: int) -> None:
    assert enharmonic_fifths(source) == target
    assert enharmonic_fifths(target) == source


def test_traditional_fifths_normalizes_model_numpy_integers() -> None:
    assert traditional_fifths(np.int64(-6)) == -6
    assert traditional_fifths(-7) == -7
    assert traditional_fifths(7) == 7
    assert traditional_fifths(True) is None
    assert traditional_fifths(-6.0) is None
    assert traditional_fifths(8) is None


def test_enharmonic_respelling_preserves_pitch_and_diatonic_mapping() -> None:
    assert respell_pitch(
        "E",
        -1,
        4,
        source_fifths=-6,
        target_fifths=6,
    ) == ("D", 1, 4)
    assert respell_pitch(
        "C",
        -1,
        5,
        source_fifths=-6,
        target_fifths=6,
    ) == ("B", 0, 4)
    assert respell_pitch(
        "B",
        0,
        4,
        source_fifths=-6,
        target_fifths=6,
    ) == ("A", 2, 4)
    assert respell_pitch(
        "D",
        1,
        4,
        source_fifths=6,
        target_fifths=-6,
    ) == ("E", -1, 4)

    with pytest.raises(ValueError, match="not the supported enharmonic"):
        respell_pitch(
            "C",
            0,
            4,
            source_fifths=-6,
            target_fifths=5,
        )


def test_variant_identity_is_canonical_and_policy_versioned() -> None:
    options = normalized_options(clef_policy="automatic", target_key_fifths=6)
    first = score_variant_id(
        baseline_musicxml_sha256="a" * 64,
        baseline_alignment_sha256="b" * 64,
        options=options,
    )
    second = score_variant_id(
        baseline_musicxml_sha256="a" * 64,
        baseline_alignment_sha256="b" * 64,
        options={"target_key_fifths": 6, "clef_policy": "automatic"},
    )

    assert first == second
    assert first.startswith("score-variant:")
    assert "Six sharps" in key_signature_label(6)
    assert "D-sharp minor" in key_signature_label(6)
