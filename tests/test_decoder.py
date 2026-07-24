from __future__ import annotations

import numpy as np

from atpiano.decoder import (
    STOCK_DECODER_POLICY,
    BasicPitchDecoderPolicy,
    decode_basic_pitch_output,
)


def _output() -> dict[str, np.ndarray]:
    note = np.zeros((50, 88), dtype=np.float32)
    onset = np.zeros((50, 88), dtype=np.float32)
    contour = np.zeros((50, 264), dtype=np.float32)
    note[5:30, 39] = 0.8
    onset[5, 39] = 0.55
    return {"note": note, "onset": onset, "contour": contour}


def test_decoder_records_explicit_onset_evidence() -> None:
    decoded = decode_basic_pitch_output(_output(), STOCK_DECODER_POLICY)

    assert len(decoded) == 1
    assert decoded[0].note.pitch == 60
    assert decoded[0].source == "explicit_onset"
    assert decoded[0].onset_confidence == pytest_approx(0.55)
    assert decoded[0].frame_confidence == pytest_approx(0.8)


def test_strict_decoder_obeys_explicit_onset_threshold() -> None:
    policy = BasicPitchDecoderPolicy(
        name="strict-test",
        onset_threshold=0.6,
        infer_onsets=False,
        melodia_trick=False,
    )

    assert decode_basic_pitch_output(_output(), policy) == []
    assert policy.provenance()["infer_onsets"] is False


def test_decoder_marks_frame_derived_onset() -> None:
    output = _output()
    output["onset"][:] = 0
    output["onset"][2, 10] = 0.8

    decoded = decode_basic_pitch_output(output, STOCK_DECODER_POLICY)

    assert len(decoded) == 1
    assert decoded[0].source == "inferred_onset"
    assert decoded[0].onset_confidence == 0.0


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value, abs=1e-6)
