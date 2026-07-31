from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from atpiano.adapters.local_models import LocalModelPool
from atpiano.backend_profile import (
    BackendFixtureIdentity,
    BackendHostIdentity,
    BackendSchedulerIdentity,
    build_profile,
    recommend_mode,
    select_profile_mode,
    write_backend_profile,
)
from atpiano.contracts.schemas import (
    CorrectionMode,
    CorrectionProfileStatus,
)

SCHEDULER = BackendSchedulerIdentity(
    buffer_s=28.0,
    base_hop_s=4.0,
    maximum_hop_s=8.0,
    guard_s=4.0,
    minimum_context_s=16.0,
)
PROVENANCE = {
    "name": "transkun",
    "version": "2.0.1",
    "adapter": "atpiano-transkun-trailing-v1",
    "device": "cpu",
    "checkpoint_sha256": "a" * 64,
    "config_sha256": "b" * 64,
    "torch_version": "2.13.0+cu132",
    "precision": "float32",
    "accelerator": {
        "kind": "cuda",
        "runtime_version": "13.2",
        "device_index": 0,
        "device_name": "NVIDIA GeForce RTX 4090",
        "compute_capability": "8.9",
        "compiled_architectures": ["sm_86", "sm_90"],
        "total_memory_bytes": 25_756_696_576,
        "float32_matmul_precision": "highest",
        "matmul_allow_tf32": False,
        "cudnn_allow_tf32": False,
    },
    "execution": {"thread_limit": 2},
}
HOST = BackendHostIdentity(
    system="Linux",
    machine="x86_64",
    processor="test-cpu",
    logical_cpu_count=20,
)
FIXTURE = BackendFixtureIdentity(
    input_id="musical-loop",
    manifest_sha256="c" * 64,
    audio_sha256="d" * 64,
    sample_rate_hz=48_000,
    source_frame_count=2_016_000,
    repeat=2,
    silence_s=0.0,
    warmup_s=16.0,
)


def test_backend_recommendation_requires_live_headroom() -> None:
    live, _, _ = recommend_mode(
        (2.5, 2.8, 3.0),
        source_duration_s=42.0,
        base_hop_s=4.0,
    )
    delayed, _, _ = recommend_mode(
        (3.6,) * 10,
        source_duration_s=42.0,
        base_hop_s=4.0,
    )
    after_stop, _, timing = recommend_mode(
        (11.0,) * 5,
        source_duration_s=42.0,
        base_hop_s=8.0,
    )

    assert live is CorrectionMode.LIVE
    assert delayed is CorrectionMode.DELAYED
    assert after_stop is CorrectionMode.AFTER_STOP
    assert timing.service_ratio > 1


def test_backend_profile_rejects_stale_execution_identity() -> None:
    profile = build_profile(
        provenance=PROVENANCE,
        thread_limit=2,
        scheduler=SCHEDULER,
        fixture=FIXTURE,
        source_duration_s=42.0,
        decode_wall_s=(2.5, 2.8, 3.0),
        host=HOST,
        created_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )

    selected, reason = select_profile_mode(
        profile,
        provenance=PROVENANCE,
        thread_limit=2,
        scheduler=SCHEDULER,
        host=HOST,
    )
    stale, stale_reason = select_profile_mode(
        profile,
        provenance=PROVENANCE,
        thread_limit=4,
        scheduler=SCHEDULER,
        host=HOST,
    )

    assert selected is CorrectionMode.LIVE
    assert profile.profile_id[:12] in reason
    assert stale is CorrectionMode.AFTER_STOP
    assert "stale" in stale_reason


def test_backend_profile_rejects_stale_accelerator_runtime() -> None:
    profile = build_profile(
        provenance=PROVENANCE,
        thread_limit=2,
        scheduler=SCHEDULER,
        fixture=FIXTURE,
        source_duration_s=42.0,
        decode_wall_s=(2.5, 2.8, 3.0),
        host=HOST,
    )
    changed = {
        **PROVENANCE,
        "accelerator": {
            **PROVENANCE["accelerator"],
            "runtime_version": "13.0",
        },
    }

    selected, reason = select_profile_mode(
        profile,
        provenance=changed,
        thread_limit=2,
        scheduler=SCHEDULER,
        host=HOST,
    )

    assert profile.model.accelerator is not None
    assert profile.model.accelerator.compute_capability == "8.9"
    assert selected is CorrectionMode.AFTER_STOP
    assert "stale" in reason


def test_backend_profile_rejects_stale_host_identity() -> None:
    profile = build_profile(
        provenance=PROVENANCE,
        thread_limit=2,
        scheduler=SCHEDULER,
        fixture=FIXTURE,
        source_duration_s=42.0,
        decode_wall_s=(2.5, 2.8, 3.0),
        host=HOST,
    )

    selected, reason = select_profile_mode(
        profile,
        provenance=PROVENANCE,
        thread_limit=2,
        scheduler=SCHEDULER,
        host=HOST.model_copy(update={"logical_cpu_count": 10}),
    )

    assert selected is CorrectionMode.AFTER_STOP
    assert "host identity is stale" in reason


def _model_pool(profile_path: Path | None) -> LocalModelPool:
    return LocalModelPool(
        preview_model_factory=lambda: None,
        commit_model_factory=lambda: None,
        isolate_models=False,
        commit_threads=2,
        correction_mode="auto",
        backend_profile_path=profile_path,
    )


def test_correction_capability_reports_missing_automatic_profile(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "missing-profile.json"

    capability = _model_pool(profile_path).correction_capability()

    assert capability.configured_mode == "auto"
    assert capability.default_mode is CorrectionMode.AFTER_STOP
    assert (
        capability.backend_profile_status
        is CorrectionProfileStatus.MISSING
    )
    assert capability.backend_profile_path == str(profile_path.resolve())
    assert capability.backend_profile_id is None


def test_correction_capability_reports_measured_recommendation(
    tmp_path: Path,
) -> None:
    profile = build_profile(
        provenance=PROVENANCE,
        thread_limit=2,
        scheduler=SCHEDULER,
        fixture=FIXTURE,
        source_duration_s=42.0,
        decode_wall_s=(3.6,) * 10,
        host=HOST,
    )
    profile_path = tmp_path / "backend-profile.json"
    write_backend_profile(profile_path, profile)

    capability = _model_pool(profile_path).correction_capability()

    assert capability.configured_mode == "auto"
    assert capability.default_mode is CorrectionMode.DELAYED
    assert (
        capability.backend_profile_status
        is CorrectionProfileStatus.AVAILABLE
    )
    assert capability.backend_profile_id == profile.profile_id
    assert capability.backend_profile_recommendation is CorrectionMode.DELAYED
