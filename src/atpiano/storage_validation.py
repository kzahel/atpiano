"""Reproducible accelerated validation for Phase 4 storage behavior."""

from __future__ import annotations

import math
import resource
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from atpiano.corrected_commit import CommitModelOutput
from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.live import LiveModelOutput
from atpiano.util import read_json, utc_now, write_json

STORAGE_VALIDATION_SCHEMA = "atpiano.storage-validation.v1"


class StorageValidationPreviewModel:
    """Deterministic bounded model used to isolate storage behavior."""

    sample_rate_hz = 8_000
    window_samples = 100
    fft_hop_samples = 1
    overlapping_frames = 0
    left_guard_samples = 0
    right_guard_samples = 0

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        del audio
        return LiveModelOutput(
            candidates=[],
            raw={"onset": np.zeros((1, 88), dtype=np.float32)},
            inference_s=0.0,
            decode_s=0.0,
        )

    def provenance(self) -> dict[str, object]:
        return {
            "name": "phase4-storage-validation-preview",
            "purpose": "storage isolation; not transcription quality",
        }


class StorageValidationCommitModel:
    """Deterministic full-horizon commit lane for retirement gating."""

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        frame_count = len(pcm_s16le) // 2
        return CommitModelOutput(
            events=(),
            inference_s=0.0,
            source_frame_count=frame_count,
            model_frame_count=frame_count,
        )

    def provenance(self) -> dict[str, object]:
        return {
            "name": "phase4-storage-validation-commit",
            "purpose": "storage isolation; not transcription quality",
        }


def _rss_high_water_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(
        value
        if sys.platform == "darwin"
        else value * 1024
    )


def _open_file_count() -> int | None:
    for directory in (Path("/dev/fd"), Path("/proc/self/fd")):
        if directory.is_dir():
            try:
                return len(list(directory.iterdir()))
            except OSError:
                continue
    return None


def _verify_repeat_alignment(
    input_manifest: Path,
    recording_path: Path,
    *,
    repeat: int,
    sample_rate_hz: int,
) -> dict[str, Any]:
    manifest = read_json(input_manifest)
    audio = manifest["audio"]
    input_path = (
        input_manifest.parent / str(audio["path"])
    ).resolve()
    with wave.open(str(input_path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != sample_rate_hz
        ):
            raise ValueError(
                "storage alignment validation requires mono PCM16 WAV"
            )
        source_samples = np.frombuffer(
            source.readframes(source.getnframes()),
            dtype="<i2",
        ).astype(np.float64)
    probe_frames = min(
        max(1, round(0.2 * sample_rate_hz)),
        source_samples.shape[0],
    )
    candidates = range(
        0,
        source_samples.shape[0] - probe_frames + 1,
        probe_frames,
    )
    probe_start = max(
        candidates,
        key=lambda start: float(
            np.linalg.norm(
                source_samples[start : start + probe_frames]
                - np.mean(
                    source_samples[
                        start : start + probe_frames
                    ]
                )
            )
        ),
    )
    expected = source_samples[
        probe_start : probe_start + probe_frames
    ]
    expected = expected - np.mean(expected)
    expected_norm = float(np.linalg.norm(expected))
    if expected_norm == 0:
        raise ValueError("storage alignment probe is silent")
    correlations: list[float] = []
    for repetition in range(repeat):
        first_sample = (
            repetition * source_samples.shape[0] + probe_start
        )
        seek_s = first_sample / sample_rate_hz
        decoded = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{seek_s:.9f}",
                "-i",
                str(recording_path),
                "-t",
                f"{probe_frames / sample_rate_hz:.9f}",
                "-ac",
                "1",
                "-ar",
                str(sample_rate_hz),
                "-f",
                "s16le",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout
        observed = np.frombuffer(decoded, dtype="<i2").astype(
            np.float64
        )
        if observed.shape[0] != probe_frames:
            raise ValueError(
                "compact recording seek returned the wrong frame count"
            )
        observed = observed - np.mean(observed)
        observed_norm = float(np.linalg.norm(observed))
        correlation = (
            float(np.dot(observed, expected))
            / observed_norm
            / expected_norm
            if observed_norm
            else 0.0
        )
        correlations.append(correlation)
    threshold = 0.9
    minimum = min(correlations)
    if minimum < threshold:
        raise ValueError(
            "compact recording seek is not aligned to repetition "
            f"boundaries: {minimum:.3f} < {threshold:.3f}"
        )
    worst_repetition = correlations.index(minimum)
    return {
        "method": (
            "decode a non-silent 200 ms source-clock range after every "
            "repetition boundary and compare it with the input WAV"
        ),
        "boundary_count": repeat,
        "probe_offset_samples": probe_start,
        "probe_frame_count": probe_frames,
        "correlation_threshold": threshold,
        "minimum_correlation": minimum,
        "mean_correlation": sum(correlations) / len(correlations),
        "maximum_correlation": max(correlations),
        "worst_repetition": worst_repetition,
        "first_repetition_correlation": correlations[0],
        "last_repetition_correlation": correlations[-1],
    }


def run_storage_validation(
    input_manifest: Path,
    workspace_directory: Path,
    *,
    minimum_hours: float = 1.0,
    minimum_free_bytes: int = 2 * 1024**3,
    timeout_s: float = 900.0,
) -> tuple[Path, dict[str, Any]]:
    """Run accelerated compact storage through the application boundary."""

    if minimum_hours <= 0:
        raise ValueError("storage validation duration must be positive")
    if minimum_free_bytes < 0:
        raise ValueError("minimum free bytes cannot be negative")
    if timeout_s <= 0:
        raise ValueError("storage validation timeout must be positive")
    input_manifest = input_manifest.resolve()
    workspace_directory = workspace_directory.resolve()
    if workspace_directory.exists() and any(
        workspace_directory.iterdir()
    ):
        raise FileExistsError(
            "storage validation workspace must be empty"
        )
    evidence_path = workspace_directory.with_name(
        f"{workspace_directory.name}-evidence.json"
    )
    if evidence_path.exists():
        raise FileExistsError(
            f"storage validation evidence exists: {evidence_path}"
        )
    source = read_json(input_manifest)
    audio = source.get("audio")
    if not isinstance(audio, dict):
        raise ValueError("storage validation input has no audio")
    input_frames = int(audio["frame_count"])
    sample_rate_hz = int(audio["sample_rate_hz"])
    input_duration_s = input_frames / sample_rate_hz
    target_duration_s = minimum_hours * 3600
    repeat = max(1, math.ceil(target_duration_s / input_duration_s))

    rss_before = _rss_high_water_bytes()
    open_files_before = _open_file_count()
    maximum_open_files = open_files_before
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    server = create_corrected_workbench_server(
        workspace_directory,
        port=0,
        preview_model_factory=StorageValidationPreviewModel,
        commit_model_factory=StorageValidationCommitModel,
        isolate_models=False,
        correction_mode="after-stop",
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=input_manifest,
        replay_repeat=repeat,
        replay_realtime=False,
        compact_recordings=True,
    )
    try:
        server.start_replay()
        deadline = time.monotonic() + timeout_s
        while True:
            state = server.public_state()
            open_files = _open_file_count()
            if open_files is not None:
                maximum_open_files = max(
                    maximum_open_files or 0,
                    open_files,
                )
            if state["status"] in {"complete", "failed"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("storage validation timed out")
            time.sleep(0.01)
        if state["status"] != "complete":
            raise RuntimeError(
                f"storage validation failed: {state.get('error')}"
            )
        session_directory = server.current_directory()
        if session_directory is None:
            raise RuntimeError(
                "storage validation produced no session directory"
            )
        recording = read_json(session_directory / "recording.json")
        pipeline = read_json(
            session_directory / "pipeline-status.json"
        )
        if (
            recording.get("state") != "complete"
            or list((session_directory / "audio").glob("*.wav"))
            or (session_directory / "diagnostics").exists()
        ):
            raise RuntimeError(
                "storage validation retained unexpected raw or debug data"
            )
        duration_s = (
            int(recording["source"]["frame_count"])
            / int(recording["source"]["sample_rate_hz"])
        )
        accounting = server.application.storage.accounting(
            session_id=state["session_id"],
            duration_s=duration_s,
            minimum_free_bytes=minimum_free_bytes,
        )
        recording_bytes = int(
            recording["recording"]["byte_count"]
        )
        alignment = _verify_repeat_alignment(
            input_manifest,
            session_directory / str(
                recording["recording"]["path"]
            ),
            repeat=repeat,
            sample_rate_hz=sample_rate_hz,
        )
        evidence = {
            "schema_version": STORAGE_VALIDATION_SCHEMA,
            "recorded_at": utc_now(),
            "input": {
                "manifest": str(input_manifest),
                "input_frame_count": input_frames,
                "sample_rate_hz": sample_rate_hz,
                "input_duration_s": input_duration_s,
                "repeat": repeat,
            },
            "source": {
                "frame_count": int(
                    recording["source"]["frame_count"]
                ),
                "sample_rate_hz": int(
                    recording["source"]["sample_rate_hz"]
                ),
                "duration_s": duration_s,
            },
            "runtime": {
                "wall_s": time.perf_counter() - started_wall,
                "cpu_s": time.process_time() - started_cpu,
                "rss_before_bytes": rss_before,
                "rss_high_water_bytes": _rss_high_water_bytes(),
                "open_files_before": open_files_before,
                "open_files_maximum_observed": maximum_open_files,
                "open_files_after_settlement": _open_file_count(),
            },
            "recording": recording,
            "alignment": alignment,
            "pipeline": pipeline,
            "storage": accounting,
            "measured_recording_bytes_per_hour": (
                recording_bytes * 3600 / duration_s
            ),
            "assertions": {
                "minimum_duration_met": (
                    duration_s >= target_duration_s
                ),
                "compact_recording_verified": True,
                "raw_wav_segments_retained": 0,
                "ordinary_debug_files_retained": 0,
                "every_repetition_boundary_aligned": (
                    alignment["boundary_count"] == repeat
                ),
                "category_total_reconciles": (
                    accounting["workspace"]["total_bytes"]
                    == sum(
                        accounting["workspace"]["bytes"].values()
                    )
                ),
            },
        }
        write_json(evidence_path, evidence)
        return evidence_path, evidence
    finally:
        server.server_close()
