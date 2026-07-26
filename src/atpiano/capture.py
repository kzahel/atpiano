"""Sample-clocked microphone capture artifacts."""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile

from atpiano.fixture import INPUT_SCHEMA
from atpiano.util import sha256_file, utc_now, write_json, write_jsonl

BROWSER_CAPTURE_SCHEMA = "atpiano.browser-capture.v1"


def _sounddevice() -> Any:
    try:
        import sounddevice
    except ImportError as error:
        raise RuntimeError(
            "microphone capture requires: uv sync --extra capture"
        ) from error
    except OSError as error:
        raise RuntimeError(
            "microphone capture requires the PortAudio shared library "
            "(Debian/Ubuntu: install libportaudio2)"
        ) from error
    return sounddevice


def _target_paths(output_directory: Path) -> tuple[Path, Path, Path]:
    return (
        output_directory / "recording.wav",
        output_directory / "capture-timing.jsonl",
        output_directory / "input.json",
    )


def ensure_capture_target(output_directory: Path, *, force: bool = False) -> None:
    existing = [path for path in _target_paths(output_directory) if path.exists()]
    if existing and not force:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(f"refusing to overwrite capture files: {names}")


def write_capture_artifacts(
    output_directory: Path,
    audio: np.ndarray,
    *,
    sample_rate_hz: int,
    block_records: list[dict[str, Any]],
    device: dict[str, Any],
    requested_duration_s: float,
    block_samples: int,
    force: bool = False,
) -> dict[str, Any]:
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    ensure_capture_target(output_directory, force=force)
    audio_path, timing_path, manifest_path = _target_paths(output_directory)
    mono = np.asarray(audio, dtype=np.float32).reshape(-1)
    soundfile.write(
        audio_path,
        mono,
        sample_rate_hz,
        subtype="PCM_16",
        format="WAV",
    )
    write_jsonl(timing_path, block_records)
    audio_hash = sha256_file(audio_path)
    timing_hash = sha256_file(timing_path)
    manifest = {
        "schema_version": INPUT_SCHEMA,
        "input_id": f"microphone-{audio_hash[:16]}",
        "created_at": utc_now(),
        "license": "user-provided local recording; rights not asserted by atpiano",
        "audio": {
            "path": audio_path.name,
            "sha256": audio_hash,
            "format": "wav-pcm-s16le",
            "sample_rate_hz": sample_rate_hz,
            "channels": 1,
            "first_sample_index": 0,
            "frame_count": int(mono.shape[0]),
            "duration_s": mono.shape[0] / sample_rate_hz,
        },
        "reference": None,
        "capture": {
            "adapter": "sounddevice-fixed-duration-v1",
            "requested_duration_s": requested_duration_s,
            "block_samples": block_samples,
            "timing_path": timing_path.name,
            "timing_sha256": timing_hash,
            "device": device,
            "source_timeline": "audio sample index",
            "receipt_clock": "time.perf_counter_ns",
            "block_count": len(block_records),
            "status_blocks": sum(bool(record.get("status")) for record in block_records),
        },
    }
    write_json(manifest_path, manifest)
    return manifest


def write_browser_capture_artifacts(
    output_directory: Path,
    source_wav: Path,
    *,
    client_metadata: dict[str, Any],
    adapter: str = "web-audio-worklet-file-v1",
    transport: str = "same-origin HTTP PCM WAV upload",
    capture_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a browser-produced PCM WAV and write an unaligned input manifest."""
    if client_metadata.get("schema_version") != BROWSER_CAPTURE_SCHEMA:
        raise ValueError("unsupported browser capture metadata schema")
    display_settings = _browser_display_settings(
        client_metadata.get("display_settings")
    )
    output_directory = output_directory.resolve()
    source_wav = source_wav.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    ensure_capture_target(output_directory)

    info = soundfile.info(source_wav)
    if info.format != "WAV" or info.subtype != "PCM_16":
        raise ValueError("browser upload must be a 16-bit PCM WAV")
    if info.channels != 1:
        raise ValueError("browser upload must contain exactly one channel")
    if info.samplerate <= 0 or info.frames <= 0:
        raise ValueError("browser upload must contain audio samples")

    expected_sample_rate = client_metadata.get("sample_rate_hz")
    expected_frames = client_metadata.get("frame_count")
    chunk_count = client_metadata.get("chunk_count")
    capture_elapsed_s = client_metadata.get("capture_elapsed_s")
    if expected_sample_rate != info.samplerate:
        raise ValueError("browser metadata sample rate does not match WAV")
    if expected_frames != info.frames:
        raise ValueError("browser metadata frame count does not match WAV")
    if not isinstance(chunk_count, int) or isinstance(chunk_count, bool) or chunk_count <= 0:
        raise ValueError("browser metadata chunk count must be a positive integer")
    if (
        not isinstance(capture_elapsed_s, (int, float))
        or isinstance(capture_elapsed_s, bool)
        or capture_elapsed_s <= 0
    ):
        raise ValueError("browser metadata capture duration must be positive")

    audio_path = output_directory / "recording.wav"
    metadata_path = output_directory / "browser-capture.json"
    shutil.copyfile(source_wav, audio_path)
    capture_document = {
        "schema_version": BROWSER_CAPTURE_SCHEMA,
        "sample_rate_hz": info.samplerate,
        "frame_count": info.frames,
        "chunk_count": chunk_count,
        "capture_elapsed_s": float(capture_elapsed_s),
        "started_at": client_metadata.get("started_at"),
        "requested_constraints": client_metadata.get("requested_constraints"),
        "actual_track_settings": client_metadata.get("actual_track_settings"),
        "display_settings": display_settings,
        "source_timeline": "AudioWorklet sample index",
        "transport": transport,
        "received_at": utc_now(),
    }
    write_json(metadata_path, capture_document)

    audio_hash = sha256_file(audio_path)
    manifest = {
        "schema_version": INPUT_SCHEMA,
        "input_id": f"browser-microphone-{audio_hash[:16]}",
        "created_at": utc_now(),
        "license": "user-provided local recording; rights not asserted by atpiano",
        "audio": {
            "path": audio_path.name,
            "sha256": audio_hash,
            "format": "wav-pcm-s16le",
            "sample_rate_hz": info.samplerate,
            "channels": 1,
            "first_sample_index": 0,
            "frame_count": info.frames,
            "duration_s": info.frames / info.samplerate,
        },
        "reference": None,
        "capture": {
            "adapter": adapter,
            "metadata_path": metadata_path.name,
            "metadata_sha256": sha256_file(metadata_path),
            "source_timeline": "audio sample index",
            "host_clock_mapping": None,
            "latency_claim": None,
        }
        | (capture_details or {}),
    }
    write_json(output_directory / "input.json", manifest)
    return manifest


def _browser_display_settings(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("unsupported live display settings")
    schema_version = value.get("schema_version")
    if schema_version not in {
        "atpiano.live-display-settings.v1",
        "atpiano.live-display-settings.v2",
    }:
        raise ValueError("unsupported live display settings")
    mode = value.get("mode")
    group_window_ms = value.get("groupWindowMs")
    show_confidence = value.get("showConfidence")
    if mode not in {"grouped", "raw"}:
        raise ValueError("live display mode must be grouped or raw")
    if (
        not isinstance(group_window_ms, int)
        or isinstance(group_window_ms, bool)
        or not 0 <= group_window_ms <= 250
    ):
        raise ValueError("live display group window must be 0 through 250 ms")
    if not isinstance(show_confidence, bool):
        raise ValueError("live display confidence setting must be boolean")
    settings = {
        "schema_version": schema_version,
        "mode": mode,
        "groupWindowMs": group_window_ms,
        "showConfidence": show_confidence,
    }
    if schema_version == "atpiano.live-display-settings.v1":
        return settings
    timing_mode = value.get("timingMode")
    rhythm_bpm = value.get("rhythmBpm")
    if timing_mode not in {"off", "relative", "absolute", "both"}:
        raise ValueError("live display timing mode is invalid")
    if (
        not isinstance(rhythm_bpm, int)
        or isinstance(rhythm_bpm, bool)
        or rhythm_bpm not in {0, 60, 80, 100, 120, 140, 160}
    ):
        raise ValueError("live display rhythm tempo is not a supported preset")
    return settings | {
        "timingMode": timing_mode,
        "rhythmBpm": rhythm_bpm,
    }


def list_input_devices() -> str:
    sounddevice = _sounddevice()
    return str(sounddevice.query_devices())


def record_microphone(
    output_directory: Path,
    *,
    duration_s: float,
    sample_rate_hz: int = 22_050,
    block_samples: int = 1024,
    device: int | str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if duration_s <= 0:
        raise ValueError("duration must be positive")
    if sample_rate_hz <= 0 or block_samples <= 0:
        raise ValueError("sample rate and block size must be positive")
    output_directory = output_directory.resolve()
    ensure_capture_target(output_directory, force=force)
    sounddevice = _sounddevice()
    sounddevice.check_input_settings(
        device=device,
        channels=1,
        dtype="float32",
        samplerate=sample_rate_hz,
    )
    queried = sounddevice.query_devices(device, "input")
    device_info = {
        "requested": device,
        "name": str(queried["name"]),
        "hostapi": int(queried["hostapi"]),
        "max_input_channels": int(queried["max_input_channels"]),
        "default_samplerate": float(queried["default_samplerate"]),
    }
    target_frames = round(duration_s * sample_rate_hz)
    received: list[np.ndarray] = []
    block_records: list[dict[str, Any]] = []
    finished = threading.Event()
    source_cursor = 0

    def callback(
        input_data: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        nonlocal source_cursor
        remaining = target_frames - source_cursor
        accepted = min(frames, remaining)
        if accepted > 0:
            received.append(input_data[:accepted, 0].copy())
            block_records.append(
                {
                    "schema_version": "atpiano.capture-block.v1",
                    "source_first_sample": source_cursor,
                    "source_frame_count": accepted,
                    "callback_monotonic_ns": time.perf_counter_ns(),
                    "input_adc_time_s": float(time_info.inputBufferAdcTime),
                    "status": str(status) if status else "",
                }
            )
            source_cursor += accepted
        if source_cursor >= target_frames:
            finished.set()
            raise sounddevice.CallbackStop

    timeout_s = duration_s + 5.0
    with sounddevice.InputStream(
        samplerate=sample_rate_hz,
        blocksize=block_samples,
        device=device,
        channels=1,
        dtype="float32",
        callback=callback,
    ):
        if not finished.wait(timeout_s):
            raise TimeoutError(
                f"microphone capture did not produce {target_frames} samples "
                f"within {timeout_s:.1f} seconds"
            )
    if source_cursor != target_frames:
        raise RuntimeError(
            f"capture ended with {source_cursor} of {target_frames} requested samples"
        )
    audio = np.concatenate(received) if received else np.zeros(0, dtype=np.float32)
    return write_capture_artifacts(
        output_directory,
        audio,
        sample_rate_hz=sample_rate_hz,
        block_records=block_records,
        device=device_info,
        requested_duration_s=duration_s,
        block_samples=block_samples,
        force=force,
    )
