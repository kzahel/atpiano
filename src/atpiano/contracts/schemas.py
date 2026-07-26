"""Pydantic source schemas for the versioned atpiano contract."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

CONTRACT_SCHEMA_VERSION = "atpiano.contract.v1"
PCM_PROTOCOL_VERSION = "atpiano.pcm.v1"

OpaqueId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
MediaType = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=127,
        pattern=r"^[a-z0-9][a-z0-9.+-]+/[a-z0-9][a-z0-9.+-]+$",
    ),
]
Cursor = Annotated[str, StringConstraints(min_length=1, max_length=512)]
PositiveLimit = Annotated[int, Field(ge=1, le=4096)]
SampleIndex = Annotated[int, Field(ge=0)]


class ContractModel(BaseModel):
    """Strict immutable base for wire-visible contract values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class VersionedContractModel(ContractModel):
    schema_version: Literal["atpiano.contract.v1"] = CONTRACT_SCHEMA_VERSION


class WorkspaceMode(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    SYNCED = "synced"


class RuntimeMode(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"
    FIXTURE = "fixture"


class MembershipRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    STOPPING = "stopping"
    COMPLETE = "complete"
    FAILED = "failed"
    TRASHED = "trashed"


class CaptureStatus(str, Enum):
    REQUESTING = "requesting"
    WARMING = "warming"
    RECORDING = "recording"
    STOPPING = "stopping"
    COMPLETE = "complete"
    FAILED = "failed"


class CorrectionMode(str, Enum):
    LIVE = "live"
    DELAYED = "delayed"
    AFTER_STOP = "after-stop"
    UNAVAILABLE = "unavailable"


class SourceKind(str, Enum):
    MICROPHONE = "microphone"
    REPLAY = "replay"
    UPLOAD = "upload"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventKind(str, Enum):
    NOTE = "note"
    SUSTAIN = "sustain"
    SOFT_PEDAL = "soft-pedal"


class EventLifecycle(str, Enum):
    PROVISIONAL = "provisional"
    COMMITTED = "committed"
    RETRACTED = "retracted"


class OffsetState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class ArtifactKind(str, Enum):
    AUDIO = "audio"
    EVENT_HISTORY = "event-history"
    MIDI = "midi"
    MUSICXML = "musicxml"
    SCORE_INPUT_MIDI = "score-input-midi"
    SCORE_ALIGNMENT = "score-alignment"
    MANIFEST = "manifest"
    DIAGNOSTIC = "diagnostic"


class JobKind(str, Enum):
    TRANSCRIPTION = "transcription"
    SCORE = "score"
    EXPORT = "export"
    UPLOAD = "upload"


class ErrorCode(str, Enum):
    INVALID_REQUEST = "invalid-request"
    INCOMPATIBLE_VERSION = "incompatible-version"
    NOT_FOUND = "not-found"
    CONFLICT = "conflict"
    CAPTURE_BUSY = "capture-busy"
    SCORE_BUSY = "score-busy"
    SESSION_ACTIVE = "session-active"
    JOB_ACTIVE = "job-active"
    STORAGE_UNAVAILABLE = "storage-unavailable"
    MODEL_UNAVAILABLE = "model-unavailable"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class User(VersionedContractModel):
    user_id: OpaqueId
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    created_at: AwareDatetime


class Workspace(VersionedContractModel):
    workspace_id: OpaqueId
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    mode: WorkspaceMode
    created_at: AwareDatetime
    owner_user_id: OpaqueId | None = None


class Membership(VersionedContractModel):
    workspace_id: OpaqueId
    user_id: OpaqueId
    role: MembershipRole
    created_at: AwareDatetime


class Session(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    status: SessionStatus
    source: SourceKind
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=384_000)]
    source_frame_count: SampleIndex
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    active_capture_id: OpaqueId | None = None
    current_transcription_run_id: OpaqueId | None = None
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    available_artifact_kinds: tuple[ArtifactKind, ...] = ()
    correction_mode: CorrectionMode | None = None
    correction_reason: Annotated[
        str,
        StringConstraints(min_length=1, max_length=500),
    ] | None = None
    correction_profile_id: Sha256 | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Session:
        if self.status is SessionStatus.COMPLETE and self.completed_at is None:
            raise ValueError("completed session requires completed_at")
        if self.status in {SessionStatus.ACTIVE, SessionStatus.STOPPING}:
            if self.completed_at is not None:
                raise ValueError("active or stopping session cannot have completed_at")
        return self


class Capture(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    capture_id: OpaqueId
    status: CaptureStatus
    source: SourceKind
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=384_000)]
    accepted_through_sample: SampleIndex
    started_at: AwareDatetime
    stopped_at: AwareDatetime | None = None
    error_id: OpaqueId | None = None


class TranscriptionRun(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    transcription_run_id: OpaqueId
    status: RunStatus
    preview_model: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    commit_model: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    created_at: AwareDatetime
    completed_at: AwareDatetime | None = None


class EventRevision(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    transcription_run_id: OpaqueId
    event_id: OpaqueId
    revision: Annotated[int, Field(ge=1)]
    lane: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    kind: EventKind
    lifecycle: EventLifecycle
    onset_sample: SampleIndex
    offset_sample: SampleIndex | None
    offset_state: OffsetState
    pitch: Annotated[int, Field(ge=21, le=108)] | None = None
    velocity: Annotated[int, Field(ge=0, le=127)] | None = None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    supersedes_revision: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def validate_event(self) -> EventRevision:
        if self.kind is EventKind.NOTE and self.pitch is None:
            raise ValueError("note event requires pitch")
        if self.kind is not EventKind.NOTE and self.pitch is not None:
            raise ValueError("pedal event cannot have pitch")
        if self.offset_state is OffsetState.CLOSED and self.offset_sample is None:
            raise ValueError("closed event requires offset_sample")
        if self.offset_state is OffsetState.OPEN and self.offset_sample is not None:
            raise ValueError("open event cannot have offset_sample")
        if self.offset_sample is not None and self.offset_sample < self.onset_sample:
            raise ValueError("event offset cannot precede onset")
        if self.revision == 1 and self.supersedes_revision is not None:
            raise ValueError("first revision cannot supersede another revision")
        if self.revision > 1 and self.supersedes_revision != self.revision - 1:
            raise ValueError("revision must supersede the immediately prior revision")
        return self


class Horizon(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    transcription_run_id: OpaqueId
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=384_000)]
    audio_head_sample: SampleIndex
    provisional_sample: SampleIndex
    commit_sample: SampleIndex
    recorded_at: AwareDatetime

    @model_validator(mode="after")
    def validate_horizons(self) -> Horizon:
        if self.provisional_sample > self.audio_head_sample:
            raise ValueError("provisional horizon cannot pass the audio head")
        if self.commit_sample > self.audio_head_sample:
            raise ValueError("commit horizon cannot pass the audio head")
        return self


class Provenance(VersionedContractModel):
    application_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    schema_versions: dict[str, Annotated[str, StringConstraints(min_length=1, max_length=128)]]
    adapter: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    execution_backend: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    model_id: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    checkpoint_sha256: Sha256 | None = None
    settings_sha256: Sha256 | None = None
    source_artifact_sha256: tuple[Sha256, ...] = ()


class Artifact(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    artifact_id: OpaqueId
    kind: ArtifactKind
    media_type: MediaType
    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    sha256: Sha256
    byte_count: Annotated[int, Field(ge=0)]
    source_horizon_sample: SampleIndex
    created_at: AwareDatetime
    transcription_run_id: OpaqueId | None = None
    producing_job_id: OpaqueId | None = None
    provenance: Provenance


class ScoreSnapshot(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    score_snapshot_id: OpaqueId
    producing_job_id: OpaqueId
    transcription_run_id: OpaqueId
    commit_sample: SampleIndex
    note_count: Annotated[int, Field(ge=0)]
    artifact_ids: tuple[OpaqueId, ...]
    created_at: AwareDatetime


ErrorDetail = str | int | float | bool | None


class AtpianoError(VersionedContractModel):
    error_id: OpaqueId
    code: ErrorCode
    message: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    retryable: bool
    workspace_id: OpaqueId | None = None
    session_id: OpaqueId | None = None
    capture_id: OpaqueId | None = None
    job_id: OpaqueId | None = None
    details: dict[str, ErrorDetail] = Field(default_factory=dict)


class Job(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    job_id: OpaqueId
    kind: JobKind
    status: RunStatus
    input_horizon_sample: SampleIndex
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    artifact_ids: tuple[OpaqueId, ...] = ()
    error: AtpianoError | None = None

    @model_validator(mode="after")
    def validate_job(self) -> Job:
        if self.status is RunStatus.FAILED and self.error is None:
            raise ValueError("failed job requires a structured error")
        if self.status is not RunStatus.FAILED and self.error is not None:
            raise ValueError("only failed jobs carry an error")
        return self


class RuntimeCapabilities(VersionedContractModel):
    runtime_mode: RuntimeMode
    supported_schema_versions: tuple[str, ...]
    supported_pcm_protocol_versions: tuple[str, ...]
    capture_sources: tuple[SourceKind, ...]
    score_available: bool
    recoverable_delete: bool
    max_pcm_block_frames: Annotated[int, Field(ge=1)]
    max_event_range_samples: Annotated[int, Field(ge=1)]


class PcmEnvelope(ContractModel):
    protocol_version: Literal["atpiano.pcm.v1"] = PCM_PROTOCOL_VERSION
    workspace_id: OpaqueId
    session_id: OpaqueId
    capture_id: OpaqueId
    stream_id: OpaqueId
    sequence: SampleIndex
    first_sample: SampleIndex
    frame_count: Annotated[int, Field(ge=1, le=1_048_576)]
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=384_000)]
    channel_count: Annotated[int, Field(ge=1, le=8)]
    sample_format: Literal["pcm-s16le"] = "pcm-s16le"
    payload_byte_count: Annotated[int, Field(ge=2)]

    @model_validator(mode="after")
    def validate_payload_size(self) -> PcmEnvelope:
        expected = self.frame_count * self.channel_count * 2
        if self.payload_byte_count != expected:
            raise ValueError("PCM payload size does not match frame format")
        return self


class CaptureStart(VersionedContractModel):
    workspace_id: OpaqueId
    source: Literal[SourceKind.MICROPHONE]
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=384_000)]
    request_id: OpaqueId


class CaptureStop(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    capture_id: OpaqueId
    accepted_frame_count: SampleIndex
    request_id: OpaqueId


class ReplayStart(VersionedContractModel):
    workspace_id: OpaqueId
    fixture_id: OpaqueId
    repeat: Annotated[int, Field(ge=1, le=10_000)] = 1
    silence_samples: SampleIndex = 0
    realtime: bool = True
    request_id: OpaqueId


class ScoreJobStart(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    transcription_run_id: OpaqueId
    commit_sample: SampleIndex
    request_id: OpaqueId


class DeleteSessionRequest(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    request_id: OpaqueId
    confirmation: Literal["recoverable-delete"]


class DeleteSessionResult(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    trashed_at: AwareDatetime
    recoverable: Literal[True] = True


class ArtifactAccess(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    artifact_id: OpaqueId
    media_type: MediaType
    download_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    url: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    expires_at: AwareDatetime | None = None


class WorkspacePage(VersionedContractModel):
    items: tuple[Workspace, ...]
    next_cursor: Cursor | None = None


class SessionPage(VersionedContractModel):
    workspace_id: OpaqueId
    items: tuple[Session, ...]
    next_cursor: Cursor | None = None


class EventPage(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    start_sample: SampleIndex
    end_sample: SampleIndex
    items: tuple[EventRevision, ...]
    next_cursor: Cursor | None = None


class ArtifactPage(VersionedContractModel):
    workspace_id: OpaqueId
    session_id: OpaqueId
    items: tuple[Artifact, ...]
    next_cursor: Cursor | None = None


class ErrorResponse(VersionedContractModel):
    error: AtpianoError


def contract_models() -> tuple[type[BaseModel], ...]:
    """Return named public models in deterministic generation order."""

    return (
        User,
        Workspace,
        Membership,
        Session,
        Capture,
        TranscriptionRun,
        EventRevision,
        Horizon,
        Provenance,
        Artifact,
        ScoreSnapshot,
        AtpianoError,
        Job,
        RuntimeCapabilities,
        PcmEnvelope,
        CaptureStart,
        CaptureStop,
        ReplayStart,
        ScoreJobStart,
        DeleteSessionRequest,
        DeleteSessionResult,
        ArtifactAccess,
        WorkspacePage,
        SessionPage,
        EventPage,
        ArtifactPage,
        ErrorResponse,
    )


def utc_datetime(value: str) -> datetime:
    """Parse an aware timestamp for fixture builders without hiding validation."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed
