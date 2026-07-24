"""Deterministic lifecycle reconciliation for overlapping model windows."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from atpiano.midi import MidiNote


@dataclass(frozen=True)
class WindowRegion:
    index: int
    source_start_sample: int
    source_end_sample: int
    left_guard_samples: int
    right_guard_samples: int
    is_first: bool
    has_future: bool


@dataclass
class NoteTrack:
    event_id: str
    note: MidiNote
    revision: int
    lifecycle: str
    first_emitted_ns: int
    committed_emitted_ns: int | None
    confidence: float
    first_window_index: int


class Reconciler:
    def __init__(
        self,
        *,
        session_id: str,
        sample_rate_hz: int,
        session_origin_ns: int,
        realtime: bool,
        onset_match_tolerance_s: float = 0.08,
    ) -> None:
        self.session_id = session_id
        self.sample_rate_hz = sample_rate_hz
        self.session_origin_ns = session_origin_ns
        self.realtime = realtime
        self.onset_match_tolerance_s = onset_match_tolerance_s
        self.tracks: list[NoteTrack] = []
        self._provisional: list[NoteTrack] = []
        self._ordinal = 0

    def _new_id(self, note: MidiNote, window_index: int) -> str:
        value = (
            f"{self.session_id}:{window_index}:{note.pitch}:"
            f"{note.onset_s:.9f}:{self._ordinal}"
        ).encode("ascii")
        self._ordinal += 1
        return hashlib.sha256(value).hexdigest()[:20]

    def _record(
        self,
        track: NoteTrack,
        *,
        emitted_ns: int,
        window_index: int,
    ) -> dict[str, Any]:
        onset_sample = round(track.note.onset_s * self.sample_rate_hz)
        offset_sample = round(track.note.offset_s * self.sample_rate_hz)
        emitted_elapsed_s = (emitted_ns - self.session_origin_ns) / 1_000_000_000.0
        source_to_emission = (
            emitted_elapsed_s - onset_sample / self.sample_rate_hz
            if self.realtime
            else None
        )
        return {
            "schema_version": "atpiano.note-event.v1",
            "session_id": self.session_id,
            "event_id": track.event_id,
            "revision": track.revision,
            "source": "acoustic",
            "lifecycle": track.lifecycle,
            "pitch": track.note.pitch,
            "onset_sample": onset_sample,
            "offset_sample": offset_sample,
            "velocity": track.note.velocity,
            "confidence": track.confidence,
            "pedal_relationship": None,
            "emitted_at_monotonic_ns": emitted_ns,
            "emitted_elapsed_s": emitted_elapsed_s,
            "source_to_emission_latency_s": source_to_emission,
            "window_index": window_index,
        }

    def _match_provisionals(
        self,
        candidates: list[tuple[MidiNote, float]],
    ) -> tuple[dict[int, int], set[int]]:
        pairs: list[tuple[float, int, int]] = []
        for track_index, track in enumerate(self._provisional):
            for candidate_index, (candidate, _) in enumerate(candidates):
                if track.note.pitch != candidate.pitch:
                    continue
                distance = abs(track.note.onset_s - candidate.onset_s)
                if distance <= self.onset_match_tolerance_s:
                    pairs.append((distance, track_index, candidate_index))
        matches: dict[int, int] = {}
        used_candidates: set[int] = set()
        for _, track_index, candidate_index in sorted(pairs):
            if track_index in matches or candidate_index in used_candidates:
                continue
            matches[track_index] = candidate_index
            used_candidates.add(candidate_index)
        return matches, used_candidates

    def process(
        self,
        candidates: list[tuple[MidiNote, float]],
        region: WindowRegion,
        *,
        emitted_ns: int,
        total_source_samples: int,
    ) -> list[dict[str, Any]]:
        filtered = [
            (note, confidence)
            for note, confidence in candidates
            if 0 <= round(note.onset_s * self.sample_rate_hz) < total_source_samples
        ]
        records: list[dict[str, Any]] = []
        matches, used_candidates = self._match_provisionals(filtered)
        previous_provisionals = self._provisional
        self._provisional = []

        for track_index, track in enumerate(previous_provisionals):
            track.revision += 1
            if track_index in matches:
                candidate, confidence = filtered[matches[track_index]]
                track.note = candidate
                track.confidence = confidence
                track.lifecycle = "committed"
                track.committed_emitted_ns = emitted_ns
            else:
                track.lifecycle = "retracted"
            records.append(
                self._record(
                    track,
                    emitted_ns=emitted_ns,
                    window_index=region.index,
                )
            )

        reliable_start = (
            region.source_start_sample
            if region.is_first
            else region.source_start_sample + region.left_guard_samples
        )
        provisional_start = region.source_end_sample - region.right_guard_samples
        for candidate_index, (note, confidence) in enumerate(filtered):
            if candidate_index in used_candidates:
                continue
            onset_sample = round(note.onset_s * self.sample_rate_hz)
            if onset_sample < reliable_start:
                continue
            lifecycle = (
                "provisional"
                if region.has_future and onset_sample >= provisional_start
                else "committed"
            )
            track = NoteTrack(
                event_id=self._new_id(note, region.index),
                note=note,
                revision=1,
                lifecycle=lifecycle,
                first_emitted_ns=emitted_ns,
                committed_emitted_ns=emitted_ns if lifecycle == "committed" else None,
                confidence=confidence,
                first_window_index=region.index,
            )
            self.tracks.append(track)
            if lifecycle == "provisional":
                self._provisional.append(track)
            records.append(
                self._record(
                    track,
                    emitted_ns=emitted_ns,
                    window_index=region.index,
                )
            )
        return records

    def final_tracks(self) -> list[NoteTrack]:
        return sorted(
            (track for track in self.tracks if track.lifecycle == "committed"),
            key=lambda track: track.note,
        )
