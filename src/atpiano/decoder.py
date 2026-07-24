"""Explicit, versioned decoding policies for retained Basic Pitch output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.signal import argrelmax

from atpiano.midi import MidiNote


@dataclass(frozen=True)
class BasicPitchDecoderPolicy:
    """Parameters that determine how native Basic Pitch arrays become notes."""

    name: str
    onset_threshold: float
    frame_threshold: float = 0.3
    minimum_note_length_ms: float = 127.7
    infer_onsets: bool = True
    melodia_trick: bool = True

    def provenance(self) -> dict[str, Any]:
        return {
            "schema_version": "atpiano.basic-pitch-decoder-policy.v1",
            **asdict(self),
        }


@dataclass(frozen=True)
class DecodedNote:
    """A decoded note plus the native evidence for its start."""

    note: MidiNote
    start_frame: int
    end_frame: int
    frame_confidence: float
    onset_confidence: float
    decoder_confidence: float
    source: str

    @property
    def explicit_onset(self) -> bool:
        return self.source == "explicit_onset"


STOCK_DECODER_POLICY = BasicPitchDecoderPolicy(
    name="stock",
    onset_threshold=0.5,
    infer_onsets=True,
    melodia_trick=True,
)

NO_MELODIA_DECODER_POLICY = BasicPitchDecoderPolicy(
    name="no-melodia",
    onset_threshold=0.5,
    infer_onsets=True,
    melodia_trick=False,
)

STRICT_ONSET_DECODER_POLICY = BasicPitchDecoderPolicy(
    name="strict-onset-0.6",
    onset_threshold=0.6,
    infer_onsets=False,
    melodia_trick=False,
)


def strict_onset_policy(onset_threshold: float) -> BasicPitchDecoderPolicy:
    return BasicPitchDecoderPolicy(
        name=f"strict-onset-{onset_threshold:g}",
        onset_threshold=onset_threshold,
        infer_onsets=False,
        melodia_trick=False,
    )


def decode_basic_pitch_output(
    output: dict[str, np.ndarray],
    policy: BasicPitchDecoderPolicy,
) -> list[DecodedNote]:
    """Decode retained native arrays while preserving onset-origin evidence."""
    from basic_pitch.constants import AUDIO_SAMPLE_RATE, FFT_HOP
    from basic_pitch.note_creation import (
        get_infered_onsets,
        model_frames_to_time,
        output_to_notes_polyphonic,
    )

    frames = np.asarray(output["note"]).copy()
    raw_onsets = np.asarray(output["onset"]).copy()
    contours = np.asarray(output["contour"])
    minimum_note_frames = round(
        policy.minimum_note_length_ms / 1000 * (AUDIO_SAMPLE_RATE / FFT_HOP)
    )
    decoded_frames = output_to_notes_polyphonic(
        frames.copy(),
        raw_onsets.copy(),
        onset_thresh=policy.onset_threshold,
        frame_thresh=policy.frame_threshold,
        infer_onsets=policy.infer_onsets,
        min_note_len=minimum_note_frames,
        min_freq=None,
        max_freq=None,
        melodia_trick=policy.melodia_trick,
    )

    decoder_onsets = (
        get_infered_onsets(raw_onsets.copy(), frames.copy())
        if policy.infer_onsets
        else raw_onsets
    )
    explicit_peaks = _peak_values(raw_onsets)
    decoder_peaks = _peak_values(decoder_onsets)
    times_s = model_frames_to_time(contours.shape[0])
    result: list[DecodedNote] = []
    for start_frame, end_frame, pitch, frame_confidence in decoded_frames:
        frequency_index = pitch - 21
        onset_confidence = float(raw_onsets[start_frame, frequency_index])
        decoder_confidence = float(decoder_onsets[start_frame, frequency_index])
        if explicit_peaks[start_frame, frequency_index] >= policy.onset_threshold:
            source = "explicit_onset"
        elif decoder_peaks[start_frame, frequency_index] >= policy.onset_threshold:
            source = "inferred_onset"
        else:
            source = "melodia_fallback"
        result.append(
            DecodedNote(
                note=MidiNote(
                    onset_s=float(times_s[start_frame]),
                    offset_s=float(times_s[end_frame]),
                    pitch=int(pitch),
                    velocity=max(
                        1,
                        min(127, round(float(frame_confidence) * 127)),
                    ),
                ),
                start_frame=int(start_frame),
                end_frame=int(end_frame),
                frame_confidence=float(frame_confidence),
                onset_confidence=onset_confidence,
                decoder_confidence=decoder_confidence,
                source=source,
            )
        )
    return sorted(result, key=lambda decoded: decoded.note)


def _peak_values(values: np.ndarray) -> np.ndarray:
    peaks = np.zeros(values.shape, dtype=values.dtype)
    indices = argrelmax(values, axis=0)
    peaks[indices] = values[indices]
    return peaks
