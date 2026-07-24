"""Sample-indexed live browser transport and capture artifacts."""

from __future__ import annotations

import json
import struct
import time
import wave
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
            absolute_candidates = [
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
        }

    def finalize(self) -> dict[str, Any]:
        write_jsonl(self.artifact_directory / "events.jsonl", self._events)
        write_jsonl(self.artifact_directory / "timing.jsonl", self._timing_rows)
        write_jsonl(self.artifact_directory / "raw" / "windows.jsonl", self._raw_rows)
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
            "first_visible_latency_s": _latency_summary(latencies),
            "artifacts": {
                "events": "events.jsonl",
                "timing": "timing.jsonl",
                "raw_index": "raw/windows.jsonl",
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
    }
    reconciliation_path = run_directory / "live" / "reconciliation.json"
    write_json(reconciliation_path, result)
    run = read_json(run_directory / "run.json")
    run["live"] = {
        "recognition": "live/recognition/recognition.json",
        "events": "live/recognition/events.jsonl",
        "reconciliation": "live/reconciliation.json",
    }
    run.setdefault("artifacts", {})["live_recognition"] = run["live"]["recognition"]
    run["artifacts"]["live_events"] = run["live"]["events"]
    run["artifacts"]["live_reconciliation"] = run["live"]["reconciliation"]
    write_json(run_directory / "run.json", run)
    scores_path = run_directory / "scores.json"
    scores = read_json(scores_path)
    scores["live_reconciliation"] = result
    write_json(scores_path, scores)
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
        self.block_timing_path = self.input_directory / "live-blocks.jsonl"
        self._pcm = self.pcm_path.open("wb")
        self._block_rows: list[dict[str, Any]] = []
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
        if block.first_sample + block.frame_count > self.sample_rate_hz * MAX_LIVE_SECONDS:
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
                "block_timing_path": self.block_timing_path.name,
                "block_timing_sha256": sha256_file(self.block_timing_path),
                "block_count": self.next_sequence,
                "continuity": "exact; gaps, duplicates, and reordering rejected",
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
