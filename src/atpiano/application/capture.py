"""Framework-independent local capture coordination."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from atpiano.application.ports import SessionRepository
from atpiano.backend_profile import BackendSchedulerIdentity
from atpiano.corrected import CorrectedSession
from atpiano.corrected_commit import (
    DEFAULT_COMMIT_BUFFER_S,
    DEFAULT_COMMIT_GUARD_S,
    DEFAULT_COMMIT_HOP_S,
    DEFAULT_COMMIT_MAX_HOP_S,
    DEFAULT_COMMIT_MIN_CONTEXT_S,
    CommitModel,
    CorrectedCommitLane,
)
from atpiano.corrected_pipeline import CorrectedSessionPipeline
from atpiano.corrected_preview import CorrectedPreviewLane
from atpiano.live import LiveWindowModel, PcmBlock
from atpiano.util import utc_now

CORRECTED_WORKBENCH_SCHEMA = "atpiano.corrected-workbench.v1"


class CaptureModelPool(Protocol):
    """Warmed model processes consumed by capture coordination."""

    correction_mode: str

    def preview(self) -> LiveWindowModel: ...

    def commit(self) -> CommitModel: ...

    def models(self) -> tuple[LiveWindowModel, CommitModel]: ...

    def status(self) -> list[dict[str, Any]]: ...

    def resolve_correction_mode(
        self,
        commit_model: CommitModel,
        *,
        scheduler: BackendSchedulerIdentity,
    ) -> tuple[str, str, str | None]: ...

    def close(self) -> None: ...


SessionFinalizer = Callable[[CorrectedSession], None]
FreeBytesProvider = Callable[[], int]


@dataclass(frozen=True)
class CaptureStart:
    """Application-owned microphone capture resources."""

    session: CorrectedSession
    pipeline: CorrectedSessionPipeline
    correction_mode: str
    correction_reason: str
    correction_profile_id: str | None


def _new_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


class CaptureApplicationService:
    """Own one local capture lease independently of any transport."""

    def __init__(
        self,
        repository: SessionRepository,
        model_pool: CaptureModelPool,
        *,
        minimum_free_bytes: int,
        free_bytes: FreeBytesProvider,
        finalizer: SessionFinalizer,
    ) -> None:
        self._repository = repository
        self._models = model_pool
        self.minimum_free_bytes = minimum_free_bytes
        self._free_bytes = free_bytes
        self._finalizer = finalizer
        self._lock = threading.RLock()
        self._active_session: CorrectedSession | None = None
        self._active_pipeline: CorrectedSessionPipeline | None = None
        self._session_id: str | None = None
        self._session_directory: Path | None = None
        self._status = "idle"
        self._error: str | None = None
        self._received_blocks = 0
        self._last_event_sequence = 0
        self._load_latest_session()

    @staticmethod
    def correction_scheduler_identity() -> BackendSchedulerIdentity:
        return BackendSchedulerIdentity(
            buffer_s=DEFAULT_COMMIT_BUFFER_S,
            base_hop_s=DEFAULT_COMMIT_HOP_S,
            maximum_hop_s=DEFAULT_COMMIT_MAX_HOP_S,
            guard_s=DEFAULT_COMMIT_GUARD_S,
            minimum_context_s=DEFAULT_COMMIT_MIN_CONTEXT_S,
        )

    def _load_latest_session(self) -> None:
        record = self._repository.latest_session_record()
        if record is None:
            return
        directory, latest = record
        session_id = str(latest["session_id"])
        self._session_id = session_id
        self._session_directory = directory
        persisted_status = str(latest.get("status", "failed"))
        if persisted_status in {"active", "stopping"}:
            interrupted_stage = (
                "capture" if persisted_status == "active" else "settlement"
            )
            interruption = (
                "The prior process ended before this session stopped."
                if persisted_status == "active"
                else (
                    "The prior process ended during correction settlement. "
                    "Accepted audio is preserved, but correction must be rerun."
                )
            )
            processing = latest.get("processing")
            if not isinstance(processing, dict):
                processing = {}
            stage_errors = processing.get("stage_errors")
            if not isinstance(stage_errors, dict):
                stage_errors = {}
            processing["stage_errors"] = {
                **stage_errors,
                interrupted_stage: interruption,
            }
            latest.update(
                {
                    "status": "failed",
                    "completed_at": utc_now(),
                    "error": interruption,
                    "processing": processing,
                }
            )
            self._repository.write_document(
                session_id,
                "session.json",
                latest,
            )
            self._status = "failed"
            self._error = interruption
        else:
            self._status = persisted_status
            error = latest.get("error")
            self._error = str(error) if error is not None else None

    def close(self) -> None:
        with self._lock:
            pipeline = self._active_pipeline
        if pipeline is not None and not pipeline.wait(0):
            pipeline.abort(
                RuntimeError("local application stopped during capture")
            )
        self._models.close()

    def preview_model(self) -> LiveWindowModel:
        return self._models.preview()

    def commit_model(self) -> CommitModel:
        return self._models.commit()

    def models(self) -> tuple[LiveWindowModel, CommitModel]:
        return self._models.models()

    def worker_status(self) -> list[dict[str, Any]]:
        return self._models.status()

    def resolve_correction_mode(
        self,
        commit_model: CommitModel,
    ) -> tuple[str, str, str | None]:
        return self._models.resolve_correction_mode(
            commit_model,
            scheduler=self.correction_scheduler_identity(),
        )

    def claim_session(self, *, source: str) -> tuple[str, Path]:
        if source not in {"microphone", "replay"}:
            raise ValueError("capture source is invalid")
        with self._lock:
            if self._active_session is not None or self._status in {
                "warming",
                "active",
                "stopping",
            }:
                raise RuntimeError(
                    "another corrected session is already active"
                )
            session_id = _new_session_id()
            directory = self._repository.new_session_directory(session_id)
            self._session_id = session_id
            self._session_directory = directory
            self._status = "warming"
            self._error = None
            self._received_blocks = 0
            self._last_event_sequence = 0
        return session_id, directory

    def set_active(
        self,
        session: CorrectedSession,
        pipeline: CorrectedSessionPipeline | None = None,
    ) -> None:
        with self._lock:
            if session.session_id != self._session_id:
                raise RuntimeError(
                    "corrected session claim changed during startup"
                )
            self._active_session = session
            self._active_pipeline = pipeline
            self._status = "active"

    def complete_session(self) -> None:
        with self._lock:
            self._active_session = None
            self._active_pipeline = None
            self._status = "complete"
            self._error = None

    def fail_session(self, error: Exception) -> None:
        with self._lock:
            self._active_session = None
            self._active_pipeline = None
            self._status = "failed"
            self._error = f"{type(error).__name__}: {error}"

    def begin_stop(self) -> None:
        with self._lock:
            self._status = "stopping"

    def current_directory(self) -> Path | None:
        with self._lock:
            return self._session_directory

    def current_session_id(self) -> str | None:
        with self._lock:
            return self._session_id

    def active_session_id(self) -> str | None:
        with self._lock:
            if self._active_session is not None:
                return self._active_session.session_id
            if self._status in {"warming", "active", "stopping"}:
                return self._session_id
            return None

    def start_microphone(
        self,
        *,
        sample_rate_hz: int,
        client_metadata: dict[str, Any],
    ) -> CaptureStart:
        session_id, directory = self.claim_session(source="microphone")
        preview_model = self.preview_model()
        correction_mode = self._models.correction_mode
        correction_reason = "commit correction is unavailable"
        correction_profile_id: str | None = None
        commit_model: CommitModel | None = None
        if correction_mode != "unavailable":
            try:
                commit_model = self.commit_model()
                (
                    correction_mode,
                    correction_reason,
                    correction_profile_id,
                ) = self.resolve_correction_mode(commit_model)
            except RuntimeError as error:
                correction_mode = "unavailable"
                correction_reason = (
                    "commit worker could not start: "
                    f"{type(error).__name__}: {error}"
                )
        session = CorrectedSession(
            directory,
            session_id=session_id,
            sample_rate_hz=sample_rate_hz,
            source="microphone",
            minimum_free_bytes=self.minimum_free_bytes,
            correction_mode=correction_mode,
            correction_reason=correction_reason,
            correction_profile_id=correction_profile_id,
        )
        session.add_lane(
            CorrectedPreviewLane(session, model=preview_model)
        )
        if commit_model is not None:
            session.add_lane(
                CorrectedCommitLane(session, model=commit_model)
            )
        pipeline = CorrectedSessionPipeline(
            session,
            finalizer=self._finalizer,
            on_settled=self._microphone_settled,
            on_failed=self._microphone_failed,
            defer_until_stop=(
                frozenset({"commit"})
                if correction_mode == "after-stop"
                else frozenset()
            ),
        )
        self._repository.write_document(
            session_id,
            "client.json",
            {
                "schema_version": "atpiano.corrected-client.v1",
                "received_at": utc_now(),
                "metadata": client_metadata,
            },
        )
        self.set_active(session, pipeline)
        return CaptureStart(
            session=session,
            pipeline=pipeline,
            correction_mode=correction_mode,
            correction_reason=correction_reason,
            correction_profile_id=correction_profile_id,
        )

    def accept_block(
        self,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> CorrectedSession:
        with self._lock:
            session = self._active_session
            pipeline = self._active_pipeline
        if session is None or pipeline is None:
            raise RuntimeError("microphone capture pipeline is unavailable")
        pipeline.accept_block(block, received_ns=received_ns)
        with self._lock:
            self._received_blocks += 1
        return session

    def stop_microphone(
        self,
        *,
        frame_count: int,
        block_count: int,
        transport: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._lock:
            session = self._active_session
            pipeline = self._active_pipeline
        if session is None or pipeline is None:
            raise RuntimeError("microphone capture pipeline is unavailable")
        if (
            frame_count != session.horizons.audio_head_sample
            or block_count != session.next_sequence
        ):
            raise ValueError(
                "microphone Stop counts do not match accepted PCM"
            )
        if transport is not None:
            self._validate_transport(
                transport,
                frame_count=frame_count,
                block_count=block_count,
            )
            self._repository.write_document(
                session.session_id,
                "transport.json",
                {
                    "schema_version": "atpiano.corrected-transport.v1",
                    "recorded_at": utc_now(),
                    **transport,
                },
            )
        self.begin_stop()
        return pipeline.begin_stop()

    @staticmethod
    def _validate_transport(
        transport: dict[str, Any],
        *,
        frame_count: int,
        block_count: int,
    ) -> None:
        expected = {
            "sent_frame_count": frame_count,
            "sent_block_count": block_count,
        }
        if any(
            transport.get(name) != value
            for name, value in expected.items()
        ):
            raise ValueError(
                "microphone transport evidence does not match Stop"
            )
        numeric_fields = (
            "acknowledged_frame_count",
            "acknowledged_block_count",
            "socket_buffered_bytes_at_stop",
            "socket_buffered_bytes_high_water",
        )
        if any(
            not isinstance(transport.get(name), int)
            or isinstance(transport.get(name), bool)
            or int(transport[name]) < 0
            for name in numeric_fields
        ):
            raise ValueError(
                "microphone transport evidence is invalid"
            )

    def abort_microphone(self, error: Exception) -> None:
        with self._lock:
            pipeline = self._active_pipeline
            session = self._active_session
        if pipeline is not None:
            pipeline.abort(error)
        elif session is not None and not session.closed:
            session.abort(error)
            self.fail_session(error)
        else:
            self.fail_session(error)

    def _microphone_settled(
        self,
        session: CorrectedSession,
        manifest: dict[str, Any],
    ) -> None:
        del manifest
        with self._lock:
            active = self._active_session
        if active is session:
            self.complete_session()

    def _microphone_failed(
        self,
        session: CorrectedSession,
        error: Exception,
    ) -> None:
        with self._lock:
            active = self._active_session
        if active is session:
            self.fail_session(error)

    def state(self) -> dict[str, Any]:
        with self._lock:
            status = self._status
            error = self._error
            session_id = self._session_id
            active = self._active_session
            pipeline = self._active_pipeline
            received_blocks = self._received_blocks
            last_event_sequence = self._last_event_sequence
        session: dict[str, Any] | None = None
        horizons: dict[str, Any] | None = None
        lanes: list[dict[str, Any]] = []
        if active is not None:
            horizons = active.horizons.document(
                sample_rate_hz=active.sample_rate_hz
            )
            session = {
                "session_id": active.session_id,
                "status": status,
                "source": active.source,
                "realtime": active.realtime,
                "sample_rate_hz": active.sample_rate_hz,
                "source_frame_count": (
                    active.horizons.audio_head_sample
                ),
                "started_at": active.started_at,
            }
            lanes = [lane.status() for lane in active.lanes]
            minimum_free_bytes = active.audio.minimum_free_bytes
        elif session_id is not None:
            try:
                session = self._repository.read_document(
                    session_id,
                    "session.json",
                )
                horizons = self._repository.read_document(
                    session_id,
                    "horizons.json",
                )
                lanes = list(session.get("lanes", []))
                minimum_free_bytes = int(
                    session.get("retention", {}).get(
                        "minimum_free_bytes",
                        0,
                    )
                )
            except (LookupError, OSError, TypeError, ValueError):
                session = None
                minimum_free_bytes = self.minimum_free_bytes
        else:
            minimum_free_bytes = self.minimum_free_bytes
        audio_frames = (
            int(horizons["audio_head_sample"])
            if horizons is not None
            else int((session or {}).get("source_frame_count", 0))
        )
        sample_rate_hz = int((session or {}).get("sample_rate_hz", 0))
        free_bytes = self._free_bytes()
        return {
            "schema_version": CORRECTED_WORKBENCH_SCHEMA,
            "status": status,
            "error": error,
            "session_id": session_id,
            "session": session,
            "horizons": horizons,
            "lanes": lanes,
            "storage": {
                "audio_pcm_bytes": audio_frames * 2,
                "free_bytes": free_bytes,
                "minimum_free_bytes": minimum_free_bytes,
                "warning": (
                    free_bytes < minimum_free_bytes * 5 // 4
                ),
            },
            "transport": {
                "received_blocks": received_blocks,
                "last_event_sequence": last_event_sequence,
                "recovery": "bounded indexed sequence query",
            },
            "pipeline": (
                pipeline.status() if pipeline is not None else None
            ),
            "workers": self.worker_status(),
            "duration_s": (
                audio_frames / sample_rate_hz
                if sample_rate_hz
                else 0.0
            ),
            "exports_ready": bool(
                session_id is not None
                and self._repository.has_file(
                    session_id,
                    "exports/manifest.json",
                )
            ),
        }

    def wait_for_settlement(self, timeout: float | None = None) -> bool:
        with self._lock:
            pipeline = self._active_pipeline
        return pipeline is None or pipeline.wait(timeout)

    def session_deleted(self, session_id: str) -> None:
        with self._lock:
            if self._session_id != session_id:
                return
            self._session_id = None
            self._session_directory = None
            self._status = "idle"
            self._error = None
            self._received_blocks = 0
            self._last_event_sequence = 0
            self._load_latest_session()

    def observe_delivery(
        self,
        events: list[dict[str, Any]],
    ) -> None:
        with self._lock:
            if events:
                self._last_event_sequence = max(
                    self._last_event_sequence,
                    max(int(event["sequence"]) for event in events),
                )
