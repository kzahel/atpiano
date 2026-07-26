"""Bounded Basic Pitch provisional lane for corrected sessions."""

from __future__ import annotations

import json
import time
from collections import deque
from math import gcd
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import resample_poly

from atpiano.corrected import (
    CORRECTED_EVENT_SCHEMA,
    CorrectedSession,
    LaneUpdate,
)
from atpiano.live import (
    DEFAULT_COMMIT_HORIZON_S,
    DEFAULT_LIVE_HOP_S,
    LiveWindowModel,
    OnsetEnergyGate,
    PcmBlock,
)
from atpiano.midi import MidiNote
from atpiano.reconcile import StreamingReconciler, WindowRegion
from atpiano.util import sha256_file, utc_now, write_json

PREVIEW_LANE_SCHEMA = "atpiano.corrected-preview-lane.v1"
DEFAULT_NATIVE_RETENTION_WINDOWS = 32
DEFAULT_IDENTITY_RETENTION_S = 40.0


def _append_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False))
            handle.write("\n")
        handle.flush()


class CorrectedPreviewLane:
    """Apply the measured v1 Basic Pitch algorithm with bounded v2 retention."""

    name = "preview"

    def __init__(
        self,
        session: CorrectedSession,
        *,
        model: LiveWindowModel,
        hop_s: float = DEFAULT_LIVE_HOP_S,
        internal_commit_horizon_s: float = DEFAULT_COMMIT_HORIZON_S,
        native_retention_windows: int = DEFAULT_NATIVE_RETENTION_WINDOWS,
        identity_retention_s: float = DEFAULT_IDENTITY_RETENTION_S,
    ) -> None:
        if hop_s <= 0:
            raise ValueError("preview hop must be positive")
        if native_retention_windows <= 0:
            raise ValueError("preview native retention must be positive")
        if identity_retention_s <= 0:
            raise ValueError("preview identity retention must be positive")
        self.session_id = session.session_id
        self.source_sample_rate_hz = session.sample_rate_hz
        self.model = model
        self.hop_s = hop_s
        self.internal_commit_horizon_s = internal_commit_horizon_s
        self.native_retention_windows = native_retention_windows
        self.identity_retention_frames = round(
            identity_retention_s * session.sample_rate_hz
        )
        self.window_duration_s = model.window_samples / model.sample_rate_hz
        self.left_pad_s = (
            model.overlapping_frames * model.fft_hop_samples / 2 / model.sample_rate_hz
        )
        self.left_guard_s = model.left_guard_samples / model.sample_rate_hz
        self.right_guard_s = model.right_guard_samples / model.sample_rate_hz
        self._next_window_start_s = -self.left_pad_s
        self._window_index = 0
        self._native_paths: deque[Path] = deque()
        self._emission_count = 0
        self._eviction_count = 0
        self._max_track_count = 0
        self._calibration_pcm = bytearray()
        self._last_provisional_sample = 0
        self.diagnostics_directory = (
            session.directory / "diagnostics" / "lane-a"
        )
        self.raw_directory = self.diagnostics_directory / "windows"
        self.raw_directory.mkdir(parents=True, exist_ok=True)
        self.raw_index_path = self.diagnostics_directory / "windows.jsonl"
        self.timing_path = self.diagnostics_directory / "timing.jsonl"
        self.gate_path = self.diagnostics_directory / "gate.jsonl"
        self.noise_gate = OnsetEnergyGate(session.sample_rate_hz)
        self.reconciler = StreamingReconciler(
            session_id=session.session_id,
            sample_rate_hz=session.sample_rate_hz,
            session_origin_ns=time.perf_counter_ns(),
            commit_horizon_s=internal_commit_horizon_s,
        )

    def _source_window_bounds(self) -> tuple[int, int]:
        start = round(self._next_window_start_s * self.source_sample_rate_hz)
        frame_count = round(self.window_duration_s * self.source_sample_rate_hz)
        return start, start + frame_count

    def _prepare_window(
        self,
        session: CorrectedSession,
        source_start: int,
        source_end: int,
    ) -> np.ndarray:
        source_frames = source_end - source_start
        audio = np.zeros(source_frames, dtype=np.float32)
        copy_start = max(source_start, 0)
        copy_end = min(session.horizons.audio_head_sample, source_end)
        if copy_end > copy_start:
            values = np.frombuffer(
                session.read_pcm(copy_start, copy_end),
                dtype="<i2",
            ).astype(np.float32)
            destination_start = copy_start - source_start
            audio[
                destination_start : destination_start + values.shape[0]
            ] = values / 32768.0
        if self.source_sample_rate_hz != self.model.sample_rate_hz:
            divisor = gcd(self.source_sample_rate_hz, self.model.sample_rate_hz)
            audio = resample_poly(
                audio,
                self.model.sample_rate_hz // divisor,
                self.source_sample_rate_hz // divisor,
            ).astype(np.float32)
        if audio.shape[0] < self.model.window_samples:
            audio = np.pad(audio, (0, self.model.window_samples - audio.shape[0]))
        return audio[: self.model.window_samples]

    def _retain_calibration(self, session: CorrectedSession) -> None:
        retained_frames = len(self._calibration_pcm) // 2
        available_frames = min(
            self.noise_gate.calibration_samples,
            session.horizons.audio_head_sample,
        )
        if available_frames > retained_frames:
            self._calibration_pcm.extend(
                session.read_pcm(retained_frames, available_frames)
            )
        self.noise_gate.calibrate(self._calibration_pcm)

    def _gate_candidate(
        self,
        session: CorrectedSession,
        note: MidiNote,
    ) -> tuple[bool, float | None, str]:
        onset_sample = round(note.onset_s * self.source_sample_rate_hz)
        start = max(
            0,
            onset_sample
            - round(self.noise_gate.lookbehind_s * self.source_sample_rate_hz),
        )
        end = min(
            session.horizons.audio_head_sample,
            onset_sample
            + round(self.noise_gate.lookahead_s * self.source_sample_rate_hz),
        )
        pcm = session.read_pcm(start, end) if end > start else b""
        return self.noise_gate.evaluate(note, pcm, first_sample=start)

    def _persist_native(
        self,
        output_raw: dict[str, np.ndarray],
        *,
        source_start: int,
        source_end: int,
    ) -> None:
        path = self.raw_directory / f"{self._window_index:08d}.npz"
        np.savez_compressed(path, **output_raw)
        self._native_paths.append(path)
        _append_jsonl(
            self.raw_index_path,
            [
                {
                    "schema_version": "atpiano.corrected-preview-window.v1",
                    "action": "retained",
                    "window_index": self._window_index,
                    "path": str(path.relative_to(self.diagnostics_directory)),
                    "sha256": sha256_file(path),
                    "source_start_sample": source_start,
                    "source_end_sample": source_end,
                    "arrays": {
                        name: {
                            "shape": list(values.shape),
                            "dtype": str(values.dtype),
                        }
                        for name, values in output_raw.items()
                    },
                }
            ],
        )
        while len(self._native_paths) > self.native_retention_windows:
            evicted = self._native_paths.popleft()
            evicted.unlink()
            self._eviction_count += 1
            _append_jsonl(
                self.raw_index_path,
                [
                    {
                        "schema_version": "atpiano.corrected-preview-window.v1",
                        "action": "evicted",
                        "window_index": int(evicted.stem),
                        "path": str(
                            evicted.relative_to(self.diagnostics_directory)
                        ),
                    }
                ],
            )

    @staticmethod
    def _translate_event(
        session: CorrectedSession,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        lifecycle = (
            "retracted" if event["lifecycle"] == "retracted" else "provisional"
        )
        return {
            "schema_version": CORRECTED_EVENT_SCHEMA,
            "session_id": event["session_id"],
            "event_id": event["event_id"],
            "revision": event["revision"],
            "lane": "preview",
            "lifecycle": lifecycle,
            "pitch": event["pitch"],
            "controller": None,
            "onset_sample": event["onset_sample"],
            "offset_sample": event["offset_sample"],
            "offset_state": "closed",
            "velocity": event["velocity"],
            "confidence": event["confidence"],
            "emitted_at_monotonic_ns": event["emitted_at_monotonic_ns"],
            "emitted_elapsed_s": event["emitted_elapsed_s"],
            "source_to_emission_latency_s": (
                event["source_to_emission_latency_s"]
                if session.realtime
                else None
            ),
            "window_index": event["window_index"],
            "observation_count": event["observation_count"],
            "preview_internal_lifecycle": event["lifecycle"],
            "commit_band": None,
            "decode_index": None,
        }

    def _prune_identities(self, session: CorrectedSession) -> None:
        retention_cutoff = max(
            session.horizons.commit_sample,
            session.horizons.audio_head_sample - self.identity_retention_frames,
        )
        self.reconciler.tracks = [
            track
            for track in self.reconciler.tracks
            if round(track.note.onset_s * self.source_sample_rate_hz)
            >= retention_cutoff
        ]
        self._max_track_count = max(
            self._max_track_count,
            len(self.reconciler.tracks),
        )

    def has_pending_work(self, session: CorrectedSession) -> bool:
        _, source_end = self._source_window_bounds()
        return max(0, source_end) <= session.horizons.audio_head_sample

    def process_available(
        self,
        session: CorrectedSession,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> LaneUpdate:
        self._retain_calibration(session)
        events: list[dict[str, Any]] = []
        timing_rows: list[dict[str, Any]] = []
        gate_rows: list[dict[str, Any]] = []
        processed = 0
        while True:
            source_start, source_end = self._source_window_bounds()
            if max(0, source_end) > session.horizons.audio_head_sample:
                break
            if max_work_items is not None and processed >= max_work_items:
                break
            prepare_start_ns = time.perf_counter_ns()
            model_audio = self._prepare_window(session, source_start, source_end)
            prepare_end_ns = time.perf_counter_ns()
            output = self.model.predict(model_audio)
            emitted_ns = time.perf_counter_ns()
            native_candidates: list[
                tuple[MidiNote, float, dict[str, Any] | None]
            ] = []
            for index, (note, confidence) in enumerate(output.candidates):
                native_candidates.append(
                    (
                        MidiNote(
                            onset_s=note.onset_s
                            + source_start / self.source_sample_rate_hz,
                            offset_s=note.offset_s
                            + source_start / self.source_sample_rate_hz,
                            pitch=note.pitch,
                            velocity=note.velocity,
                        ),
                        confidence,
                        (
                            output.candidate_evidence[index]
                            if output.candidate_evidence is not None
                            else None
                        ),
                    )
                )
            accepted: list[tuple[MidiNote, float]] = []
            for note, confidence, evidence in native_candidates:
                is_accepted, level_dbfs, reason = self._gate_candidate(session, note)
                gate_rows.append(
                    {
                        "schema_version": "atpiano.corrected-preview-gate.v1",
                        "window_index": self._window_index,
                        "pitch": note.pitch,
                        "onset_s": note.onset_s,
                        "model_confidence": confidence,
                        "model_evidence": evidence,
                        "onset_level_dbfs": level_dbfs,
                        "threshold_dbfs": self.noise_gate.threshold_dbfs,
                        "accepted": is_accepted,
                        "reason": reason,
                    }
                )
                if is_accepted:
                    accepted.append((note, confidence))
            region = WindowRegion(
                index=self._window_index,
                source_start_sample=source_start,
                source_end_sample=source_end,
                left_guard_samples=round(
                    self.left_guard_s * self.source_sample_rate_hz
                ),
                right_guard_samples=round(
                    self.right_guard_s * self.source_sample_rate_hz
                ),
                is_first=self._window_index == 0,
                has_future=True,
            )
            records = self.reconciler.process(
                accepted,
                region,
                emitted_ns=emitted_ns,
                audio_head_sample=session.horizons.audio_head_sample,
                total_source_samples=session.horizons.audio_head_sample,
            )
            events.extend(
                self._translate_event(session, record) for record in records
            )
            self._persist_native(
                output.raw,
                source_start=source_start,
                source_end=source_end,
            )
            timing_rows.append(
                {
                    "schema_version": "atpiano.corrected-preview-timing.v1",
                    "window_index": self._window_index,
                    "source_start_sample": source_start,
                    "source_end_sample": source_end,
                    "audio_head_sample": session.horizons.audio_head_sample,
                    "block_received_monotonic_ns": received_ns,
                    "prepare_s": (
                        prepare_end_ns - prepare_start_ns
                    )
                    / 1_000_000_000,
                    "inference_s": output.inference_s,
                    "decode_s": output.decode_s,
                    "native_candidate_count": len(native_candidates),
                    "accepted_candidate_count": len(accepted),
                    "emitted_monotonic_ns": emitted_ns,
                    "event_count": len(records),
                }
            )
            reliable_end = source_end - region.right_guard_samples
            internally_settled = (
                session.horizons.audio_head_sample
                - round(
                    self.internal_commit_horizon_s
                    * self.source_sample_rate_hz
                )
            )
            self._last_provisional_sample = max(
                self._last_provisional_sample,
                min(
                    session.horizons.audio_head_sample,
                    reliable_end,
                    max(0, internally_settled),
                ),
            )
            self._window_index += 1
            self._next_window_start_s += self.hop_s
            processed += 1
        self._emission_count += len(events)
        _append_jsonl(self.timing_path, timing_rows)
        _append_jsonl(self.gate_path, gate_rows)
        self._prune_identities(session)
        return LaneUpdate(
            events=tuple(events),
            provisional_sample=self._last_provisional_sample,
        )

    def accept_block(
        self,
        session: CorrectedSession,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> LaneUpdate:
        del block
        return self.process_available(
            session,
            received_ns=received_ns,
            max_work_items=None,
        )

    def finalize(self, session: CorrectedSession) -> LaneUpdate:
        self._prune_identities(session)
        write_json(self.diagnostics_directory / "preview.json", self.status())
        return LaneUpdate(provisional_sample=self._last_provisional_sample)

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": PREVIEW_LANE_SCHEMA,
            "name": self.name,
            "model": self.model.provenance(),
            "window": {
                "duration_s": self.window_duration_s,
                "hop_s": self.hop_s,
                "left_guard_s": self.left_guard_s,
                "right_guard_s": self.right_guard_s,
                "processed": self._window_index,
            },
            "retention": {
                "native_window_limit": self.native_retention_windows,
                "native_windows_retained": len(self._native_paths),
                "native_windows_evicted": self._eviction_count,
                "identity_retention_frames": self.identity_retention_frames,
                "active_identity_count": len(self.reconciler.tracks),
                "active_identity_high_water": self._max_track_count,
            },
            "event_emission_count": self._emission_count,
            "provisional_sample": self._last_provisional_sample,
            "noise_gate": self.noise_gate.status(),
            "recorded_at": utc_now(),
        }
