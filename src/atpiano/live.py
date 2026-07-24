"""Sample-indexed live browser transport and capture artifacts."""

from __future__ import annotations

import io
import json
import struct
import time
import wave
from contextlib import redirect_stdout
from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from scipy.signal import resample_poly

from atpiano.capture import BROWSER_CAPTURE_SCHEMA, write_browser_capture_artifacts
from atpiano.midi import MidiNote
from atpiano.quality import match_note_indices
from atpiano.reconcile import StreamingReconciler, WindowRegion
from atpiano.util import (
    read_json,
    sha256_file,
    sha256_path,
    utc_now,
    write_json,
    write_jsonl,
)

LIVE_STREAM_SCHEMA = "atpiano.live-stream.v1"
LIVE_SESSION_SCHEMA = "atpiano.live-session.v1"
PCM_BLOCK_MAGIC = b"ATPB"
PCM_BLOCK_VERSION = 1
PCM_BLOCK_KIND_AUDIO = 1
PCM_BLOCK_HEADER = struct.Struct("<4sBBHIIQII2d")
PCM_BLOCK_HEADER_BYTES = PCM_BLOCK_HEADER.size
MAX_PCM_BLOCK_FRAMES = 16_384
MAX_LIVE_SECONDS = 120
DEFAULT_LIVE_HOP_S = 0.25
DEFAULT_COMMIT_HORIZON_S = 1.0
DEFAULT_NOISE_CALIBRATION_S = 1.0
DEFAULT_NOISE_FRAME_S = 0.05
DEFAULT_NOISE_MARGIN_DB = 8.0
DEFAULT_NOISE_GATE_MIN_DBFS = -48.0
DEFAULT_NOISE_GATE_MAX_DBFS = -34.0
DEFAULT_ONSET_LOOKBEHIND_S = 0.02
DEFAULT_ONSET_LOOKAHEAD_S = 0.12


@dataclass(frozen=True)
class PcmBlock:
    sequence: int
    first_sample: int
    frame_count: int
    sample_rate_hz: int
    page_sent_ms: float
    worklet_time_s: float
    pcm_s16le: bytes


@dataclass(frozen=True)
class LiveModelOutput:
    candidates: list[tuple[MidiNote, float]]
    raw: dict[str, np.ndarray]
    inference_s: float
    decode_s: float


class LiveWindowModel(Protocol):
    sample_rate_hz: int
    window_samples: int
    fft_hop_samples: int
    overlapping_frames: int
    left_guard_samples: int
    right_guard_samples: int

    def predict(self, audio: np.ndarray) -> LiveModelOutput: ...

    def provenance(self) -> dict[str, Any]: ...


class OnsetEnergyGate:
    """Calibrate a room floor and reject candidates without an audible attack."""

    def __init__(
        self,
        sample_rate_hz: int,
        *,
        calibration_s: float = DEFAULT_NOISE_CALIBRATION_S,
        frame_s: float = DEFAULT_NOISE_FRAME_S,
        margin_db: float = DEFAULT_NOISE_MARGIN_DB,
        minimum_dbfs: float = DEFAULT_NOISE_GATE_MIN_DBFS,
        maximum_dbfs: float = DEFAULT_NOISE_GATE_MAX_DBFS,
        lookbehind_s: float = DEFAULT_ONSET_LOOKBEHIND_S,
        lookahead_s: float = DEFAULT_ONSET_LOOKAHEAD_S,
    ) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.calibration_s = calibration_s
        self.frame_s = frame_s
        self.margin_db = margin_db
        self.minimum_dbfs = minimum_dbfs
        self.maximum_dbfs = maximum_dbfs
        self.lookbehind_s = lookbehind_s
        self.lookahead_s = lookahead_s
        self.noise_floor_dbfs: float | None = None
        self.threshold_dbfs: float | None = None
        self.native_candidate_count = 0
        self.accepted_candidate_count = 0
        self.rejected_calibration_count = 0
        self.rejected_level_count = 0

    @property
    def calibration_samples(self) -> int:
        return round(self.calibration_s * self.sample_rate_hz)

    def calibrate(self, pcm_s16le: bytes | bytearray) -> bool:
        if self.threshold_dbfs is not None:
            return True
        if len(pcm_s16le) // 2 < self.calibration_samples:
            return False
        samples = np.frombuffer(
            bytes(pcm_s16le[: self.calibration_samples * 2]),
            dtype="<i2",
        ).astype(np.float64)
        frame_samples = max(1, round(self.frame_s * self.sample_rate_hz))
        levels = [
            _rms_dbfs(samples[start : start + frame_samples] / 32768.0)
            for start in range(0, samples.shape[0], frame_samples)
        ]
        self.noise_floor_dbfs = float(np.median(levels))
        self.threshold_dbfs = float(
            np.clip(
                self.noise_floor_dbfs + self.margin_db,
                self.minimum_dbfs,
                self.maximum_dbfs,
            )
        )
        return True

    def evaluate(
        self,
        note: MidiNote,
        pcm_s16le: bytes | bytearray,
    ) -> tuple[bool, float | None, str]:
        self.native_candidate_count += 1
        if note.onset_s < self.calibration_s:
            self.rejected_calibration_count += 1
            return False, None, "calibration"
        if not self.calibrate(pcm_s16le):
            self.rejected_calibration_count += 1
            return False, None, "uncalibrated"
        onset_sample = round(note.onset_s * self.sample_rate_hz)
        start = max(0, onset_sample - round(self.lookbehind_s * self.sample_rate_hz))
        end = min(
            len(pcm_s16le) // 2,
            onset_sample + round(self.lookahead_s * self.sample_rate_hz),
        )
        samples = np.frombuffer(
            bytes(pcm_s16le[start * 2 : end * 2]),
            dtype="<i2",
        ).astype(np.float64)
        level_dbfs = _rms_dbfs(samples / 32768.0)
        if level_dbfs < (self.threshold_dbfs or self.maximum_dbfs):
            self.rejected_level_count += 1
            return False, level_dbfs, "below_threshold"
        self.accepted_candidate_count += 1
        return True, level_dbfs, "accepted"

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "atpiano.onset-energy-gate.v1",
            "calibrated": self.threshold_dbfs is not None,
            "calibration_s": self.calibration_s,
            "frame_s": self.frame_s,
            "noise_floor_dbfs": self.noise_floor_dbfs,
            "margin_db": self.margin_db,
            "threshold_dbfs": self.threshold_dbfs,
            "threshold_clamp_dbfs": [self.minimum_dbfs, self.maximum_dbfs],
            "onset_window_s": [-self.lookbehind_s, self.lookahead_s],
            "native_candidate_count": self.native_candidate_count,
            "accepted_candidate_count": self.accepted_candidate_count,
            "rejected_calibration_count": self.rejected_calibration_count,
            "rejected_level_count": self.rejected_level_count,
        }


class BasicPitchLiveModel:
    """One cached stock Basic Pitch model used on explicit rolling windows."""

    def __init__(self) -> None:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.constants import AUDIO_N_SAMPLES, AUDIO_SAMPLE_RATE, FFT_HOP
        from basic_pitch.inference import Model

        self.sample_rate_hz = AUDIO_SAMPLE_RATE
        self.window_samples = AUDIO_N_SAMPLES
        self.fft_hop_samples = FFT_HOP
        self.overlapping_frames = 30
        self.left_guard_samples = 10 * FFT_HOP
        self.right_guard_samples = 20 * FFT_HOP
        self.model_path = Path(ICASSP_2022_MODEL_PATH).resolve()
        self.model = Model(self.model_path)

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        from basic_pitch.constants import AUDIO_SAMPLE_RATE, FFT_HOP
        from basic_pitch.note_creation import model_output_to_notes

        inference_start_ns = time.perf_counter_ns()
        with redirect_stdout(io.StringIO()):
            output = self.model.predict(audio.reshape((1, audio.shape[0], 1)))
        inference_end_ns = time.perf_counter_ns()
        decode_start_ns = time.perf_counter_ns()
        _, note_events = model_output_to_notes(
            {name: values[0].copy() for name, values in output.items()},
            onset_thresh=0.5,
            frame_thresh=0.3,
            min_note_len=round(127.7 / 1000 * (AUDIO_SAMPLE_RATE / FFT_HOP)),
            min_freq=None,
            max_freq=None,
            multiple_pitch_bends=False,
            melodia_trick=True,
            midi_tempo=120,
        )
        candidates = [
            (
                MidiNote(
                    onset_s=float(start_s),
                    offset_s=float(end_s),
                    pitch=int(pitch),
                    velocity=max(1, min(127, round(float(amplitude) * 127))),
                ),
                float(amplitude),
            )
            for start_s, end_s, pitch, amplitude, _ in note_events
        ]
        decode_end_ns = time.perf_counter_ns()
        return LiveModelOutput(
            candidates=candidates,
            raw={name: values[0].copy() for name, values in output.items()},
            inference_s=(inference_end_ns - inference_start_ns) / 1_000_000_000,
            decode_s=(decode_end_ns - decode_start_ns) / 1_000_000_000,
        )

    def provenance(self) -> dict[str, Any]:
        return {
            "name": "spotify-basic-pitch",
            "adapter": "atpiano-basic-pitch-live-window-v1",
            "artifact": str(self.model_path),
            "artifact_sha256": sha256_path(self.model_path),
            "sample_rate_hz": self.sample_rate_hz,
            "window_samples": self.window_samples,
        }


class LiveRecognitionProcessor:
    """Run overlapping model windows as contiguous browser samples arrive."""

    def __init__(
        self,
        artifact_directory: Path,
        *,
        session_id: str,
        source_sample_rate_hz: int,
        session_origin_ns: int,
        model: LiveWindowModel,
        hop_s: float = DEFAULT_LIVE_HOP_S,
        commit_horizon_s: float = DEFAULT_COMMIT_HORIZON_S,
    ) -> None:
        if hop_s <= 0:
            raise ValueError("live model hop must be positive")
        self.artifact_directory = artifact_directory.resolve()
        self.raw_directory = self.artifact_directory / "raw" / "windows"
        self.raw_directory.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.source_sample_rate_hz = source_sample_rate_hz
        self.session_origin_ns = session_origin_ns
        self.model = model
        self.hop_s = hop_s
        self.commit_horizon_s = commit_horizon_s
        self.window_duration_s = model.window_samples / model.sample_rate_hz
        self.left_pad_s = (
            model.overlapping_frames * model.fft_hop_samples / 2 / model.sample_rate_hz
        )
        self.left_guard_s = model.left_guard_samples / model.sample_rate_hz
        self.right_guard_s = model.right_guard_samples / model.sample_rate_hz
        self._pcm = bytearray()
        self._next_window_start_s = -self.left_pad_s
        self._window_index = 0
        self._events: list[dict[str, Any]] = []
        self._timing_rows: list[dict[str, Any]] = []
        self._raw_rows: list[dict[str, Any]] = []
        self._gate_rows: list[dict[str, Any]] = []
        self.noise_gate = OnsetEnergyGate(source_sample_rate_hz)
        self.reconciler = StreamingReconciler(
            session_id=session_id,
            sample_rate_hz=source_sample_rate_hz,
            session_origin_ns=session_origin_ns,
            commit_horizon_s=commit_horizon_s,
        )

    @property
    def available_source_samples(self) -> int:
        return len(self._pcm) // 2

    def _source_window_bounds(self) -> tuple[int, int]:
        start = round(self._next_window_start_s * self.source_sample_rate_hz)
        frame_count = round(self.window_duration_s * self.source_sample_rate_hz)
        return start, start + frame_count

    def _prepare_window(self, source_start: int, source_end: int) -> np.ndarray:
        source_frames = source_end - source_start
        audio = np.zeros(source_frames, dtype=np.float32)
        copy_start = max(0, source_start)
        copy_end = min(self.available_source_samples, source_end)
        if copy_end > copy_start:
            raw = bytes(self._pcm[copy_start * 2 : copy_end * 2])
            values = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            destination_start = copy_start - source_start
            audio[destination_start : destination_start + values.shape[0]] = values
        if self.source_sample_rate_hz == self.model.sample_rate_hz:
            result = audio
        else:
            divisor = gcd(self.source_sample_rate_hz, self.model.sample_rate_hz)
            result = resample_poly(
                audio,
                self.model.sample_rate_hz // divisor,
                self.source_sample_rate_hz // divisor,
            ).astype(np.float32)
        if result.shape[0] < self.model.window_samples:
            result = np.pad(result, (0, self.model.window_samples - result.shape[0]))
        return result[: self.model.window_samples]

    def accept_block(
        self,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> dict[str, Any]:
        if block.first_sample != self.available_source_samples:
            raise ValueError("recognition PCM position does not match capture position")
        self._pcm.extend(block.pcm_s16le)
        self.noise_gate.calibrate(self._pcm)
        batch_events: list[dict[str, Any]] = []
        processed = 0
        while True:
            source_start, source_end = self._source_window_bounds()
            required_source_end = max(0, source_end)
            if required_source_end > self.available_source_samples:
                break
            prepare_start_ns = time.perf_counter_ns()
            model_audio = self._prepare_window(source_start, source_end)
            prepare_end_ns = time.perf_counter_ns()
            output = self.model.predict(model_audio)
            emitted_ns = time.perf_counter_ns()
            native_candidates = [
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
                )
                for note, confidence in output.candidates
            ]
            absolute_candidates: list[tuple[MidiNote, float]] = []
            gate_start = len(self._gate_rows)
            for note, confidence in native_candidates:
                accepted, onset_level_dbfs, reason = self.noise_gate.evaluate(
                    note,
                    self._pcm,
                )
                self._gate_rows.append(
                    {
                        "schema_version": "atpiano.onset-energy-decision.v1",
                        "window_index": self._window_index,
                        "pitch": note.pitch,
                        "onset_s": note.onset_s,
                        "onset_level_dbfs": onset_level_dbfs,
                        "threshold_dbfs": self.noise_gate.threshold_dbfs,
                        "accepted": accepted,
                        "reason": reason,
                    }
                )
                if accepted:
                    absolute_candidates.append((note, confidence))
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
                absolute_candidates,
                region,
                emitted_ns=emitted_ns,
                audio_head_sample=self.available_source_samples,
                total_source_samples=self.available_source_samples,
            )
            batch_events.extend(records)
            self._events.extend(records)
            raw_path = self.raw_directory / f"{self._window_index:05d}.npz"
            np.savez_compressed(raw_path, **output.raw)
            self._raw_rows.append(
                {
                    "schema_version": "atpiano.raw-window.v1",
                    "window_index": self._window_index,
                    "path": str(raw_path.relative_to(self.artifact_directory)),
                    "sha256": sha256_file(raw_path),
                    "source_start_sample": source_start,
                    "source_end_sample": source_end,
                    "required_source_end_sample": required_source_end,
                    "arrays": {
                        name: {
                            "shape": list(values.shape),
                            "dtype": str(values.dtype),
                        }
                        for name, values in output.raw.items()
                    },
                }
            )
            self._timing_rows.append(
                {
                    "schema_version": "atpiano.live-window-timing.v1",
                    "window_index": self._window_index,
                    "source_start_sample": source_start,
                    "source_end_sample": source_end,
                    "audio_head_sample": self.available_source_samples,
                    "block_received_monotonic_ns": received_ns,
                    "prepare_s": (prepare_end_ns - prepare_start_ns) / 1_000_000_000,
                    "inference_s": output.inference_s,
                    "decode_s": output.decode_s,
                    "native_candidate_count": len(native_candidates),
                    "gate_accepted_count": len(absolute_candidates),
                    "gate_rejected_count": len(self._gate_rows) - gate_start
                    - len(absolute_candidates),
                    "emitted_monotonic_ns": emitted_ns,
                    "event_count": len(records),
                }
            )
            self._window_index += 1
            self._next_window_start_s += self.hop_s
            processed += 1
        return {
            "events": batch_events,
            "windows_processed": processed,
            "window_count": self._window_index,
            "audio_head_sample": self.available_source_samples,
            "noise_gate": self.noise_gate.status(),
        }

    def finalize(self) -> dict[str, Any]:
        write_jsonl(self.artifact_directory / "events.jsonl", self._events)
        write_jsonl(self.artifact_directory / "timing.jsonl", self._timing_rows)
        write_jsonl(self.artifact_directory / "raw" / "windows.jsonl", self._raw_rows)
        write_jsonl(self.artifact_directory / "gate.jsonl", self._gate_rows)
        latencies = [
            event["source_to_emission_latency_s"]
            for event in self._events
            if event["revision"] == 1
            and event["source_to_emission_latency_s"] is not None
        ]
        manifest = {
            "schema_version": "atpiano.live-recognition.v1",
            "session_id": self.session_id,
            "source_sample_rate_hz": self.source_sample_rate_hz,
            "source_frame_count": self.available_source_samples,
            "session_origin_ns": self.session_origin_ns,
            "session_origin_policy": (
                "first block receipt minus its source end; browser clock "
                "observations retained for delivery analysis"
            ),
            "model": self.model.provenance(),
            "window": {
                "duration_s": self.window_duration_s,
                "hop_s": self.hop_s,
                "left_guard_s": self.left_guard_s,
                "right_guard_s": self.right_guard_s,
                "window_count": self._window_index,
                "commit_horizon_s": self.commit_horizon_s,
            },
            "events": {
                "emission_count": len(self._events),
                "track_count": len(self.reconciler.tracks),
                "committed_tracks": len(self.reconciler.final_tracks()),
                "lifecycle": {
                    lifecycle: sum(
                        event["lifecycle"] == lifecycle for event in self._events
                    )
                    for lifecycle in ("provisional", "committed", "retracted")
                },
            },
            "noise_gate": self.noise_gate.status(),
            "first_visible_latency_s": _latency_summary(latencies),
            "artifacts": {
                "events": "events.jsonl",
                "timing": "timing.jsonl",
                "raw_index": "raw/windows.jsonl",
                "gate_decisions": "gate.jsonl",
            },
        }
        write_json(self.artifact_directory / "recognition.json", manifest)
        return manifest


def _latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "p50": None, "p95": None, "max": None}
    return {
        "count": len(values),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "max": max(values),
    }


def _rms_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    return 20.0 * float(np.log10(max(rms, 1e-6)))


def finalize_live_run(run_directory: Path) -> dict[str, Any] | None:
    """Compare rolling committed notes with the exact full-file prediction."""
    run_directory = run_directory.resolve()
    recognition_path = run_directory / "live" / "recognition" / "recognition.json"
    events_path = run_directory / "live" / "recognition" / "events.jsonl"
    prediction_path = run_directory / "prediction.json"
    if not recognition_path.is_file() or not events_path.is_file():
        return None
    recognition = read_json(recognition_path)
    prediction = read_json(prediction_path)
    input_manifest_path = run_directory / "input.json"
    input_manifest = read_json(input_manifest_path)
    capture = input_manifest.get("capture")
    if isinstance(capture, dict) and capture.get("adapter") == (
        "web-audio-worklet-live-v1"
    ):
        for field in (
            "block_timing_path",
            "clock_observations_path",
            "browser_paint_path",
        ):
            relative_path = capture.get(field)
            if isinstance(relative_path, str):
                capture[field] = f"live/{Path(relative_path).name}"
        write_json(input_manifest_path, input_manifest)
    sample_rate_hz = int(recognition["source_sample_rate_hz"])
    latest: dict[str, dict[str, Any]] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line:
            event = json.loads(line)
            latest[event["event_id"]] = event
    live_events = sorted(
        (event for event in latest.values() if event["lifecycle"] == "committed"),
        key=lambda event: (event["onset_sample"], event["pitch"]),
    )
    live_notes = [
        MidiNote(
            onset_s=event["onset_sample"] / sample_rate_hz,
            offset_s=event["offset_sample"] / sample_rate_hz,
            pitch=int(event["pitch"]),
            velocity=int(event["velocity"]),
        )
        for event in live_events
    ]
    final_notes = [
        MidiNote(
            onset_s=float(note["onset_s"]),
            offset_s=float(note["offset_s"]),
            pitch=int(note["pitch"]),
            velocity=int(note["velocity"]),
        )
        for note in prediction["notes"]
    ]
    matches = match_note_indices(
        final_notes,
        live_notes,
        onset_tolerance_s=0.08,
    )
    onset_changes = [
        abs(final_notes[final_index].onset_s - live_notes[live_index].onset_s)
        for final_index, live_index in matches
    ]
    offset_changes = [
        abs(final_notes[final_index].offset_s - live_notes[live_index].offset_s)
        for final_index, live_index in matches
    ]
    delivery = _browser_delivery_summary(
        run_directory / "live",
        recognition=recognition,
        events_path=events_path,
    )
    result = {
        "schema_version": "atpiano.live-reconciliation.v1",
        "live_committed_note_count": len(live_notes),
        "final_note_count": len(final_notes),
        "matched_note_count": len(matches),
        "final_additions": len(final_notes) - len(matches),
        "live_removals": len(live_notes) - len(matches),
        "onset_change_s": _latency_summary(onset_changes),
        "offset_change_s": _latency_summary(offset_changes),
        "match_policy": "same pitch and onset within 80 ms; offsets ignored",
        "source": {
            "live": "live/recognition/events.jsonl",
            "final": "prediction.json",
        },
        "browser_delivery": delivery,
    }
    reconciliation_path = run_directory / "live" / "reconciliation.json"
    write_json(reconciliation_path, result)
    run = read_json(run_directory / "run.json")
    run["live"] = {
        "recognition": "live/recognition/recognition.json",
        "events": "live/recognition/events.jsonl",
        "reconciliation": "live/reconciliation.json",
        "delivery": "live/delivery.json" if delivery is not None else None,
    }
    run.setdefault("artifacts", {})["live_recognition"] = run["live"]["recognition"]
    run["artifacts"]["live_events"] = run["live"]["events"]
    run["artifacts"]["live_reconciliation"] = run["live"]["reconciliation"]
    if run["live"]["delivery"] is not None:
        run["artifacts"]["live_delivery"] = run["live"]["delivery"]
    write_json(run_directory / "run.json", run)
    scores_path = run_directory / "scores.json"
    scores = read_json(scores_path)
    scores["live_reconciliation"] = result
    write_json(scores_path, scores)
    return result


def _browser_delivery_summary(
    live_directory: Path,
    *,
    recognition: dict[str, Any],
    events_path: Path,
) -> dict[str, Any] | None:
    clock_path = live_directory / "clock.jsonl"
    paint_path = live_directory / "paint.jsonl"
    if not clock_path.is_file() or not paint_path.is_file():
        return None
    clocks = [
        json.loads(line)
        for line in clock_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    paints = [
        json.loads(line)
        for line in paint_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not clocks:
        return None
    page_mid_ms = np.asarray(
        [
            (row["page_send_ms"] + row["page_receive_ms"]) / 2
            for row in clocks
        ],
        dtype=np.float64,
    )
    host_mid_ns = np.asarray(
        [
            (row["host_receive_ns"] + row["host_send_ns"]) / 2
            for row in clocks
        ],
        dtype=np.float64,
    )
    if len(clocks) >= 2 and float(np.ptp(page_mid_ms)) > 0:
        slope, intercept = np.polyfit(page_mid_ms, host_mid_ns, 1)
        policy = "least-squares page-performance-ms to host-monotonic-ns"
    else:
        slope = 1_000_000.0
        intercept = float(host_mid_ns[0] - slope * page_mid_ms[0])
        policy = "single-observation offset with fixed monotonic clock rate"
    residual_ns = host_mid_ns - (page_mid_ms * slope + intercept)
    round_trip_ms = [
        (row["page_receive_ms"] - row["page_send_ms"])
        - (row["host_send_ns"] - row["host_receive_ns"]) / 1_000_000
        for row in clocks
    ]
    first_events: dict[str, dict[str, Any]] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        event = json.loads(line)
        if event["revision"] == 1:
            first_events[event["event_id"]] = event
    session_origin_ns = int(recognition["session_origin_ns"])
    sample_rate_hz = int(recognition["source_sample_rate_hz"])
    painted_latencies: list[float] = []
    painted_event_ids: set[str] = set()
    for paint in paints:
        paint_host_ns = paint["page_paint_ms"] * slope + intercept
        for event_id in paint["first_event_ids"]:
            if event_id in painted_event_ids or event_id not in first_events:
                continue
            event = first_events[event_id]
            onset_s = event["onset_sample"] / sample_rate_hz
            paint_elapsed_s = (paint_host_ns - session_origin_ns) / 1_000_000_000
            painted_latencies.append(float(paint_elapsed_s - onset_s))
            painted_event_ids.add(event_id)
    result = {
        "schema_version": "atpiano.live-browser-delivery.v1",
        "clock_mapping": {
            "policy": policy,
            "observation_count": len(clocks),
            "slope_ns_per_page_ms": float(slope),
            "intercept_ns": float(intercept),
            "residual_s": _latency_summary(
                [abs(float(value)) / 1_000_000_000 for value in residual_ns]
            ),
            "round_trip_s": _latency_summary(
                [max(0.0, float(value)) / 1000 for value in round_trip_ms]
            ),
        },
        "paint_acknowledgement_count": len(paints),
        "first_visible_event_count": len(painted_event_ids),
        "source_onset_to_browser_paint_s": _latency_summary(painted_latencies),
    }
    write_json(live_directory / "delivery.json", result)
    return result


def parse_pcm_block(data: bytes) -> PcmBlock:
    """Parse and validate one versioned mono PCM16 browser block."""
    if len(data) < PCM_BLOCK_HEADER_BYTES:
        raise ValueError("live PCM block is shorter than its header")
    (
        magic,
        version,
        kind,
        header_bytes,
        sequence,
        flags,
        first_sample,
        frame_count,
        sample_rate_hz,
        page_sent_ms,
        worklet_time_s,
    ) = PCM_BLOCK_HEADER.unpack_from(data)
    if magic != PCM_BLOCK_MAGIC:
        raise ValueError("live PCM block has invalid magic")
    if version != PCM_BLOCK_VERSION or kind != PCM_BLOCK_KIND_AUDIO:
        raise ValueError("live PCM block has an unsupported version or kind")
    if header_bytes != PCM_BLOCK_HEADER_BYTES or flags != 0:
        raise ValueError("live PCM block has unsupported header fields")
    if not 0 < frame_count <= MAX_PCM_BLOCK_FRAMES:
        raise ValueError("live PCM block frame count is out of bounds")
    if not 8_000 <= sample_rate_hz <= 192_000:
        raise ValueError("live PCM block sample rate is out of bounds")
    expected_bytes = PCM_BLOCK_HEADER_BYTES + frame_count * 2
    if len(data) != expected_bytes:
        raise ValueError("live PCM block payload length does not match its frame count")
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=frame_count,
        sample_rate_hz=sample_rate_hz,
        page_sent_ms=page_sent_ms,
        worklet_time_s=worklet_time_s,
        pcm_s16le=data[PCM_BLOCK_HEADER_BYTES:],
    )


def pack_pcm_block(block: PcmBlock) -> bytes:
    """Serialize one block for deterministic replay and protocol tests."""
    if len(block.pcm_s16le) != block.frame_count * 2:
        raise ValueError("PCM payload length does not match frame count")
    return PCM_BLOCK_HEADER.pack(
        PCM_BLOCK_MAGIC,
        PCM_BLOCK_VERSION,
        PCM_BLOCK_KIND_AUDIO,
        PCM_BLOCK_HEADER_BYTES,
        block.sequence,
        0,
        block.first_sample,
        block.frame_count,
        block.sample_rate_hz,
        block.page_sent_ms,
        block.worklet_time_s,
    ) + block.pcm_s16le


class LiveCaptureSession:
    """Persist one continuous Web Audio PCM stream without silent repair."""

    def __init__(
        self,
        job_root: Path,
        *,
        job_id: str,
        sample_rate_hz: int,
        client_metadata: dict[str, Any],
    ) -> None:
        if client_metadata.get("schema_version") != BROWSER_CAPTURE_SCHEMA:
            raise ValueError("unsupported browser capture metadata schema")
        if not 8_000 <= sample_rate_hz <= 192_000:
            raise ValueError("live sample rate is out of bounds")
        self.job_root = job_root.resolve()
        self.job_id = job_id
        self.sample_rate_hz = sample_rate_hz
        self.client_metadata = dict(client_metadata)
        self.input_directory = self.job_root / "input"
        self.live_directory = self.job_root / "live"
        self.input_directory.mkdir(parents=True)
        self.live_directory.mkdir()
        self.pcm_path = self.live_directory / ".capture.pcm"
        self.block_timing_path = self.live_directory / "blocks.jsonl"
        self._pcm = self.pcm_path.open("wb")
        self._block_rows: list[dict[str, Any]] = []
        self._clock_rows: list[dict[str, Any]] = []
        self._paint_rows: list[dict[str, Any]] = []
        self.next_sequence = 0
        self.next_sample = 0
        self.closed = False
        self.started_at = utc_now()

    def accept_block(self, block: PcmBlock, *, received_ns: int) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("live capture is already closed")
        if block.sample_rate_hz != self.sample_rate_hz:
            raise ValueError("live PCM block sample rate changed during capture")
        if block.sequence != self.next_sequence:
            raise ValueError(
                f"live PCM sequence gap: expected {self.next_sequence}, "
                f"received {block.sequence}"
            )
        if block.first_sample != self.next_sample:
            raise ValueError(
                f"live source sample gap: expected {self.next_sample}, "
                f"received {block.first_sample}"
            )
        maximum_frames = (
            self.sample_rate_hz * MAX_LIVE_SECONDS + MAX_PCM_BLOCK_FRAMES
        )
        if block.first_sample + block.frame_count > maximum_frames:
            raise ValueError(f"live capture exceeds {MAX_LIVE_SECONDS} seconds")
        self._pcm.write(block.pcm_s16le)
        row = {
            "schema_version": "atpiano.live-block.v1",
            "sequence": block.sequence,
            "source_first_sample": block.first_sample,
            "source_frame_count": block.frame_count,
            "sample_rate_hz": block.sample_rate_hz,
            "page_sent_ms": block.page_sent_ms,
            "worklet_time_s": block.worklet_time_s,
            "host_received_monotonic_ns": received_ns,
        }
        self._block_rows.append(row)
        self.next_sequence += 1
        self.next_sample += block.frame_count
        return row

    def record_clock_observation(
        self,
        message: dict[str, Any],
        *,
        received_ns: int,
    ) -> None:
        values = {
            name: message.get(name)
            for name in (
                "page_send_ms",
                "page_receive_ms",
                "host_receive_ns",
                "host_send_ns",
            )
        }
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in values.values()
        ):
            raise ValueError("live clock observation is invalid")
        self._clock_rows.append(
            {
                "schema_version": "atpiano.live-clock-observation.v1",
                **values,
                "observation_received_monotonic_ns": received_ns,
            }
        )

    def record_paint(self, message: dict[str, Any], *, received_ns: int) -> None:
        batch_id = message.get("batch_id")
        page_paint_ms = message.get("page_paint_ms")
        first_event_ids = message.get("first_event_ids")
        if (
            not isinstance(batch_id, str)
            or not isinstance(page_paint_ms, (int, float))
            or isinstance(page_paint_ms, bool)
            or not isinstance(first_event_ids, list)
            or not all(isinstance(event_id, str) for event_id in first_event_ids)
        ):
            raise ValueError("live browser paint acknowledgement is invalid")
        self._paint_rows.append(
            {
                "schema_version": "atpiano.live-browser-paint.v1",
                "batch_id": batch_id,
                "page_paint_ms": float(page_paint_ms),
                "first_event_ids": first_event_ids,
                "acknowledgement_received_monotonic_ns": received_ns,
            }
        )

    def finalize(
        self,
        *,
        expected_frame_count: int,
        expected_block_count: int,
        capture_elapsed_s: float,
    ) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("live capture is already closed")
        if expected_frame_count != self.next_sample:
            raise ValueError(
                f"live Stop frame count {expected_frame_count} does not match "
                f"received {self.next_sample}"
            )
        if expected_block_count != self.next_sequence:
            raise ValueError(
                f"live Stop block count {expected_block_count} does not match "
                f"received {self.next_sequence}"
            )
        if expected_frame_count <= 0:
            raise ValueError("live capture contains no audio samples")
        self._pcm.close()
        self.closed = True
        write_jsonl(self.block_timing_path, self._block_rows)
        clock_path = self.live_directory / "clock.jsonl"
        paint_path = self.live_directory / "paint.jsonl"
        write_jsonl(clock_path, self._clock_rows)
        write_jsonl(paint_path, self._paint_rows)
        wav_path = self.input_directory / ".live.wav"
        with wave.open(str(wav_path), "wb") as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(self.sample_rate_hz)
            recording.writeframes(self.pcm_path.read_bytes())
        metadata = self.client_metadata | {
            "sample_rate_hz": self.sample_rate_hz,
            "frame_count": self.next_sample,
            "chunk_count": self.next_sequence,
            "capture_elapsed_s": capture_elapsed_s,
        }
        manifest = write_browser_capture_artifacts(
            self.input_directory,
            wav_path,
            client_metadata=metadata,
            adapter="web-audio-worklet-live-v1",
            transport="same-origin loopback WebSocket PCM16 blocks",
            capture_details={
                "block_timing_path": f"../live/{self.block_timing_path.name}",
                "block_timing_sha256": sha256_file(self.block_timing_path),
                "block_count": self.next_sequence,
                "continuity": "exact; gaps, duplicates, and reordering rejected",
                "clock_observations_path": f"../live/{clock_path.name}",
                "clock_observations_sha256": sha256_file(clock_path),
                "browser_paint_path": f"../live/{paint_path.name}",
                "browser_paint_sha256": sha256_file(paint_path),
            },
        )
        wav_path.unlink()
        session = {
            "schema_version": LIVE_SESSION_SCHEMA,
            "job_id": self.job_id,
            "status": "captured",
            "started_at": self.started_at,
            "completed_at": utc_now(),
            "sample_rate_hz": self.sample_rate_hz,
            "source_frame_count": self.next_sample,
            "block_count": self.next_sequence,
            "clock_observation_count": len(self._clock_rows),
            "paint_acknowledgement_count": len(self._paint_rows),
            "pcm_sha256": sha256_file(self.pcm_path),
            "audio_sha256": manifest["audio"]["sha256"],
            "input_manifest": str(self.input_directory / "input.json"),
            "transport": "same-origin loopback WebSocket PCM16 blocks",
        }
        write_json(self.live_directory / "session.json", session)
        self.pcm_path.unlink()
        return manifest

    def abort(self, error: str) -> None:
        if not self.closed:
            self._pcm.close()
            self.closed = True
        write_jsonl(self.block_timing_path, self._block_rows)
        write_json(
            self.live_directory / "session.json",
            {
                "schema_version": LIVE_SESSION_SCHEMA,
                "job_id": self.job_id,
                "status": "failed",
                "started_at": self.started_at,
                "completed_at": utc_now(),
                "sample_rate_hz": self.sample_rate_hz,
                "source_frame_count": self.next_sample,
                "block_count": self.next_sequence,
                "error": error,
            },
        )


def decode_live_message(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("live control message is not valid JSON") from error
    if not isinstance(value, dict) or value.get("schema_version") != LIVE_STREAM_SCHEMA:
        raise ValueError("live control message has an unsupported schema")
    if not isinstance(value.get("type"), str):
        raise ValueError("live control message is missing its type")
    return value
