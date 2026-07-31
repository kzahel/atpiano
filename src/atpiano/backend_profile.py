"""Versioned local backend capability profiles and conservative selection."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
import wave
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from atpiano.contracts.schemas import CorrectionMode
from atpiano.util import read_json, sha256_file, write_json

BACKEND_PROFILE_SCHEMA = "atpiano.backend-profile.v1"


class _ProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BackendAcceleratorIdentity(_ProfileModel):
    kind: str
    runtime_version: str | None = None
    device_index: int | None = Field(default=None, ge=0)
    device_name: str | None = None
    compute_capability: str | None = None
    compiled_architectures: tuple[str, ...] = ()
    total_memory_bytes: int | None = Field(default=None, gt=0)
    float32_matmul_precision: str | None = None
    matmul_allow_tf32: bool | None = None
    cudnn_allow_tf32: bool | None = None


class BackendModelIdentity(_ProfileModel):
    name: str
    version: str | None = None
    adapter: str | None = None
    device: str | None = None
    checkpoint_sha256: str | None = None
    config_sha256: str | None = None
    thread_limit: int | None = Field(default=None, ge=1)
    torch_version: str | None = None
    precision: str | None = None
    accelerator: BackendAcceleratorIdentity | None = None


class BackendSchedulerIdentity(_ProfileModel):
    buffer_s: Annotated[float, Field(gt=0)]
    base_hop_s: Annotated[float, Field(gt=0)]
    maximum_hop_s: Annotated[float, Field(gt=0)]
    guard_s: Annotated[float, Field(gt=0)]
    minimum_context_s: Annotated[float, Field(gt=0)]


class BackendHostIdentity(_ProfileModel):
    system: str
    machine: str
    processor: str
    logical_cpu_count: Annotated[int, Field(ge=1)]


class BackendFixtureIdentity(_ProfileModel):
    input_id: str
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    audio_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    sample_rate_hz: Annotated[int, Field(gt=0)]
    source_frame_count: Annotated[int, Field(gt=0)]
    repeat: Annotated[int, Field(ge=1)]
    silence_s: Annotated[float, Field(ge=0)]
    warmup_s: Annotated[float, Field(gt=0)]


class BackendTimingSummary(_ProfileModel):
    source_duration_s: Annotated[float, Field(gt=0)]
    decode_count: Annotated[int, Field(ge=1)]
    decode_wall_s: tuple[Annotated[float, Field(ge=0)], ...]
    decode_total_s: Annotated[float, Field(ge=0)]
    decode_mean_s: Annotated[float, Field(ge=0)]
    decode_p95_s: Annotated[float, Field(ge=0)]
    decode_maximum_s: Annotated[float, Field(ge=0)]
    service_ratio: Annotated[float, Field(ge=0)]
    maximum_hop_ratio: Annotated[float, Field(ge=0)]


class BackendProfile(_ProfileModel):
    schema_version: Literal[
        "atpiano.backend-profile.v1"
    ] = BACKEND_PROFILE_SCHEMA
    profile_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    created_at: AwareDatetime
    model: BackendModelIdentity
    scheduler: BackendSchedulerIdentity
    host: BackendHostIdentity
    fixture: BackendFixtureIdentity
    timing: BackendTimingSummary
    recommendation: CorrectionMode
    reason: Annotated[str, Field(min_length=1, max_length=500)]


def model_identity(
    provenance: dict[str, Any],
    *,
    thread_limit: int | None,
) -> BackendModelIdentity:
    execution = provenance.get("execution")
    execution_threads = (
        execution.get("thread_limit")
        if isinstance(execution, dict)
        else None
    )
    accelerator = provenance.get("accelerator")
    return BackendModelIdentity(
        name=str(provenance.get("name", "unknown")),
        version=(
            str(provenance["version"])
            if provenance.get("version") is not None
            else None
        ),
        adapter=(
            str(provenance["adapter"])
            if provenance.get("adapter") is not None
            else None
        ),
        device=(
            str(provenance["device"])
            if provenance.get("device") is not None
            else None
        ),
        checkpoint_sha256=(
            str(provenance["checkpoint_sha256"])
            if provenance.get("checkpoint_sha256") is not None
            else None
        ),
        config_sha256=(
            str(provenance["config_sha256"])
            if provenance.get("config_sha256") is not None
            else None
        ),
        thread_limit=(
            thread_limit
            if thread_limit is not None
            else (
                int(execution_threads)
                if execution_threads is not None
                else None
            )
        ),
        torch_version=(
            str(provenance["torch_version"])
            if provenance.get("torch_version") is not None
            else None
        ),
        precision=(
            str(provenance["precision"])
            if provenance.get("precision") is not None
            else None
        ),
        accelerator=(
            BackendAcceleratorIdentity.model_validate(accelerator)
            if isinstance(accelerator, dict)
            else None
        ),
    )


def host_identity() -> BackendHostIdentity:
    return BackendHostIdentity(
        system=platform.system() or "unknown",
        machine=platform.machine() or "unknown",
        processor=platform.processor() or "unknown",
        logical_cpu_count=os.cpu_count() or 1,
    )


def _p95(values: tuple[float, ...]) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def recommend_mode(
    decode_wall_s: tuple[float, ...],
    *,
    source_duration_s: float,
    base_hop_s: float,
) -> tuple[CorrectionMode, str, BackendTimingSummary]:
    if not decode_wall_s:
        raise ValueError("backend profile requires decode timing samples")
    if source_duration_s <= 0 or base_hop_s <= 0:
        raise ValueError("backend profile timing boundaries must be positive")
    total = sum(decode_wall_s)
    maximum = max(decode_wall_s)
    service_ratio = total / source_duration_s
    maximum_hop_ratio = maximum / base_hop_s
    timing = BackendTimingSummary(
        source_duration_s=source_duration_s,
        decode_count=len(decode_wall_s),
        decode_wall_s=decode_wall_s,
        decode_total_s=total,
        decode_mean_s=total / len(decode_wall_s),
        decode_p95_s=_p95(decode_wall_s),
        decode_maximum_s=maximum,
        service_ratio=service_ratio,
        maximum_hop_ratio=maximum_hop_ratio,
    )
    if service_ratio <= 0.75 and maximum_hop_ratio <= 0.85:
        return (
            CorrectionMode.LIVE,
            "sustained decode service and maximum hop time retain headroom",
            timing,
        )
    if service_ratio < 1.0:
        return (
            CorrectionMode.DELAYED,
            "decode service is sustainable but lacks live-correction headroom",
            timing,
        )
    return (
        CorrectionMode.AFTER_STOP,
        "decode service cannot keep up with continuous source audio",
        timing,
    )


def build_profile(
    *,
    provenance: dict[str, Any],
    thread_limit: int | None,
    scheduler: BackendSchedulerIdentity,
    fixture: BackendFixtureIdentity,
    source_duration_s: float,
    decode_wall_s: tuple[float, ...],
    host: BackendHostIdentity | None = None,
    created_at: datetime | None = None,
) -> BackendProfile:
    recommendation, reason, timing = recommend_mode(
        decode_wall_s,
        source_duration_s=source_duration_s,
        base_hop_s=scheduler.base_hop_s,
    )
    created = created_at or datetime.now(timezone.utc)
    body = {
        "schema_version": BACKEND_PROFILE_SCHEMA,
        "created_at": created.isoformat(),
        "model": model_identity(
            provenance,
            thread_limit=thread_limit,
        ).model_dump(mode="json"),
        "scheduler": scheduler.model_dump(mode="json"),
        "host": (host or host_identity()).model_dump(mode="json"),
        "fixture": fixture.model_dump(mode="json"),
        "timing": timing.model_dump(mode="json"),
        "recommendation": recommendation.value,
        "reason": reason,
    }
    profile_id = hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return BackendProfile(profile_id=profile_id, **body)


def write_backend_profile(path: Path, profile: BackendProfile) -> None:
    write_json(path, profile.model_dump(mode="json"))


def read_backend_profile(path: Path) -> BackendProfile:
    return BackendProfile.model_validate(read_json(path))


def select_profile_mode(
    profile: BackendProfile,
    *,
    provenance: dict[str, Any],
    thread_limit: int | None,
    scheduler: BackendSchedulerIdentity,
    host: BackendHostIdentity | None = None,
) -> tuple[CorrectionMode, str]:
    current_model = model_identity(
        provenance,
        thread_limit=thread_limit,
    )
    if profile.model != current_model:
        return (
            CorrectionMode.AFTER_STOP,
            "backend profile model or execution identity is stale",
        )
    if profile.scheduler != scheduler:
        return (
            CorrectionMode.AFTER_STOP,
            "backend profile scheduler identity is stale",
        )
    if profile.host != (host or host_identity()):
        return (
            CorrectionMode.AFTER_STOP,
            "backend profile host identity is stale",
        )
    return (
        profile.recommendation,
        f"selected by backend profile {profile.profile_id[:12]}: "
        f"{profile.reason}",
    )


def _load_fixture_identity(
    input_manifest_path: Path,
    *,
    repeat: int,
    silence_s: float,
    warmup_s: float,
) -> tuple[BackendFixtureIdentity, Path]:
    if repeat <= 0:
        raise ValueError("backend profile repetition count must be positive")
    if silence_s < 0:
        raise ValueError("backend profile silence cannot be negative")
    if warmup_s <= 0:
        raise ValueError("backend profile warm-up must be positive")
    input_manifest_path = input_manifest_path.resolve()
    manifest = read_json(input_manifest_path)
    audio = manifest.get("audio")
    if not isinstance(audio, dict):
        raise ValueError("backend profile input manifest is missing audio")
    audio_path = (input_manifest_path.parent / str(audio.get("path", ""))).resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"backend profile audio does not exist: {audio_path}")
    audio_sha256 = str(audio.get("sha256", ""))
    if sha256_file(audio_path) != audio_sha256:
        raise ValueError("backend profile audio hash does not match manifest")
    sample_rate_hz = int(audio["sample_rate_hz"])
    source_frame_count = int(audio["frame_count"])
    with wave.open(str(audio_path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != sample_rate_hz
            or source.getnframes() != source_frame_count
        ):
            raise ValueError("backend profile requires the declared mono PCM16 WAV")
    return (
        BackendFixtureIdentity(
            input_id=str(manifest.get("input_id", input_manifest_path.stem)),
            manifest_sha256=sha256_file(input_manifest_path),
            audio_sha256=audio_sha256,
            sample_rate_hz=sample_rate_hz,
            source_frame_count=source_frame_count,
            repeat=repeat,
            silence_s=silence_s,
            warmup_s=warmup_s,
        ),
        audio_path,
    )


def profile_backend(
    input_manifest_path: Path,
    output_directory: Path,
    *,
    device: str = "cpu",
    thread_limit: int | None = 2,
    repeat: int = 2,
    silence_s: float = 0.0,
    warmup_s: float = 16.0,
    minimum_free_bytes: int = 2 * 1024**3,
) -> BackendProfile:
    """Measure one isolated Transkun worker and retain replay evidence."""
    from atpiano.corrected import run_corrected_replay
    from atpiano.corrected_commit import (
        DEFAULT_COMMIT_BUFFER_S,
        DEFAULT_COMMIT_GUARD_S,
        DEFAULT_COMMIT_HOP_S,
        DEFAULT_COMMIT_MAX_HOP_S,
        DEFAULT_COMMIT_MIN_CONTEXT_S,
        TranskunCommitModel,
    )
    from atpiano.model_worker import CommitModelWorker

    fixture, audio_path = _load_fixture_identity(
        input_manifest_path,
        repeat=repeat,
        silence_s=silence_s,
        warmup_s=warmup_s,
    )
    output_directory = output_directory.resolve()
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(
            f"backend profile output directory is not empty: {output_directory}"
        )
    output_directory.mkdir(parents=True, exist_ok=True)
    worker = CommitModelWorker(
        partial(
            TranskunCommitModel,
            device=device,
            thread_limit=thread_limit,
        ),
        thread_limit=thread_limit,
    )
    try:
        warmup_frames = min(
            fixture.source_frame_count,
            round(warmup_s * fixture.sample_rate_hz),
        )
        with wave.open(str(audio_path), "rb") as source:
            warmup_pcm = source.readframes(warmup_frames)
        warmup_started_ns = time.perf_counter_ns()
        worker.transcribe(
            warmup_pcm,
            source_sample_rate_hz=fixture.sample_rate_hz,
        )
        warmup_wall_s = (
            time.perf_counter_ns() - warmup_started_ns
        ) / 1_000_000_000
        session_directory = output_directory / "session"
        result = run_corrected_replay(
            input_manifest_path,
            session_directory,
            repeat=repeat,
            silence_s=silence_s,
            realtime=False,
            minimum_free_bytes=minimum_free_bytes,
            commit_model=worker,
        )
        decode_path = session_directory / "diagnostics" / "lane-b" / "decodes.jsonl"
        decode_rows = tuple(
            json.loads(line)
            for line in decode_path.read_text(encoding="utf-8").splitlines()
            if line
        )
        decode_wall_s = tuple(float(row["decode_wall_s"]) for row in decode_rows)
        scheduler = BackendSchedulerIdentity(
            buffer_s=DEFAULT_COMMIT_BUFFER_S,
            base_hop_s=DEFAULT_COMMIT_HOP_S,
            maximum_hop_s=DEFAULT_COMMIT_MAX_HOP_S,
            guard_s=DEFAULT_COMMIT_GUARD_S,
            minimum_context_s=DEFAULT_COMMIT_MIN_CONTEXT_S,
        )
        source_duration_s = (
            int(result["source_frame_count"]) / fixture.sample_rate_hz
        )
        profile = build_profile(
            provenance=worker.provenance(),
            thread_limit=thread_limit,
            scheduler=scheduler,
            fixture=fixture,
            source_duration_s=source_duration_s,
            decode_wall_s=decode_wall_s,
        )
        write_backend_profile(output_directory / "backend-profile.json", profile)
        write_json(
            output_directory / "measurement.json",
            {
                "schema_version": "atpiano.backend-measurement.v1",
                "profile_id": profile.profile_id,
                "warmup_wall_s": warmup_wall_s,
                "worker": worker.status(),
                "session": "session/session.json",
                "decode_evidence": "session/diagnostics/lane-b/decodes.jsonl",
            },
        )
        return profile
    finally:
        worker.close()
