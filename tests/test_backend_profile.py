from __future__ import annotations

from datetime import datetime, timezone

from atpiano.backend_profile import (
    BackendFixtureIdentity,
    BackendHostIdentity,
    BackendSchedulerIdentity,
    build_profile,
    recommend_mode,
    select_profile_mode,
)
from atpiano.contracts.schemas import CorrectionMode

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
