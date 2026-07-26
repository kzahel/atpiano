from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from atpiano.contracts.schemas import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    ArtifactKind,
    EventKind,
    EventLifecycle,
    EventRevision,
    Horizon,
    OffsetState,
    PcmEnvelope,
    Provenance,
    Session,
    SessionStatus,
    SourceKind,
    Workspace,
    WorkspaceMode,
)

NOW = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
SHA256 = "a" * 64


def _provenance() -> Provenance:
    return Provenance(
        application_version="0.1.0",
        schema_versions={"contract": CONTRACT_SCHEMA_VERSION},
        adapter="test-adapter",
        execution_backend="cpu",
        source_artifact_sha256=(SHA256,),
    )


def test_representative_contract_objects_round_trip_strictly() -> None:
    workspace = Workspace(
        workspace_id="local",
        name="On this device",
        mode=WorkspaceMode.LOCAL,
        created_at=NOW,
    )
    session = Session(
        workspace_id=workspace.workspace_id,
        session_id="20260726T100000-abcdef123456",
        status=SessionStatus.COMPLETE,
        source=SourceKind.REPLAY,
        sample_rate_hz=48_000,
        source_frame_count=2_016_000,
        started_at=NOW,
        completed_at=NOW,
        current_transcription_run_id="run-1",
        available_artifact_kinds=(ArtifactKind.AUDIO, ArtifactKind.MIDI),
    )
    artifact = Artifact(
        workspace_id=workspace.workspace_id,
        session_id=session.session_id,
        artifact_id="artifact-midi-1",
        kind=ArtifactKind.MIDI,
        media_type="audio/midi",
        filename="session.mid",
        sha256=SHA256,
        byte_count=1234,
        source_horizon_sample=session.source_frame_count,
        created_at=NOW,
        transcription_run_id="run-1",
        provenance=_provenance(),
    )

    assert Workspace.model_validate_json(workspace.model_dump_json()) == workspace
    assert Session.model_validate_json(session.model_dump_json()) == session
    assert Artifact.model_validate_json(artifact.model_dump_json()) == artifact
    assert artifact.provenance.source_artifact_sha256 == (SHA256,)


def test_schema_version_and_unknown_fields_fail_explicitly() -> None:
    valid = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "workspace_id": "local",
        "name": "On this device",
        "mode": "local",
        "created_at": NOW.isoformat(),
    }

    with pytest.raises(ValidationError, match="atpiano.contract.v1"):
        Workspace.model_validate(valid | {"schema_version": "atpiano.contract.v2"})
    with pytest.raises(ValidationError, match="Extra inputs"):
        Workspace.model_validate(valid | {"platform": "tauri"})


def test_session_lifecycle_requires_consistent_completion() -> None:
    with pytest.raises(ValidationError, match="requires completed_at"):
        Session(
            workspace_id="local",
            session_id="session-1",
            status=SessionStatus.COMPLETE,
            source=SourceKind.REPLAY,
            sample_rate_hz=48_000,
            source_frame_count=1,
            started_at=NOW,
        )


def test_note_revision_and_horizons_preserve_source_samples() -> None:
    event = EventRevision(
        workspace_id="local",
        session_id="session-1",
        transcription_run_id="run-1",
        event_id="note-c4",
        revision=2,
        supersedes_revision=1,
        lane="commit",
        kind=EventKind.NOTE,
        lifecycle=EventLifecycle.COMMITTED,
        onset_sample=48_000,
        offset_sample=72_000,
        offset_state=OffsetState.CLOSED,
        pitch=60,
        velocity=80,
        confidence=0.9,
    )
    horizon = Horizon(
        workspace_id="local",
        session_id="session-1",
        transcription_run_id="run-1",
        sample_rate_hz=48_000,
        audio_head_sample=96_000,
        provisional_sample=90_000,
        commit_sample=80_000,
        recorded_at=NOW,
    )

    assert event.onset_sample == 48_000
    assert horizon.commit_sample == 80_000
    with pytest.raises(ValidationError, match="cannot precede onset"):
        EventRevision.model_validate(
            event.model_dump() | {"offset_sample": 47_999}
        )
    with pytest.raises(ValidationError, match="cannot pass the audio head"):
        Horizon.model_validate(
            horizon.model_dump() | {"commit_sample": 96_001}
        )


def test_pcm_envelope_rejects_versions_and_byte_mismatch() -> None:
    value = {
        "protocol_version": "atpiano.pcm.v1",
        "workspace_id": "local",
        "session_id": "session-1",
        "capture_id": "capture-1",
        "stream_id": "stream-1",
        "sequence": 0,
        "first_sample": 0,
        "frame_count": 4,
        "sample_rate_hz": 48_000,
        "channel_count": 1,
        "sample_format": "pcm-s16le",
        "payload_byte_count": 8,
    }

    assert PcmEnvelope.model_validate(value).first_sample == 0
    with pytest.raises(ValidationError, match="atpiano.pcm.v1"):
        PcmEnvelope.model_validate(value | {"protocol_version": "atpiano.pcm.v2"})
    with pytest.raises(ValidationError, match="payload size"):
        PcmEnvelope.model_validate(value | {"payload_byte_count": 6})
