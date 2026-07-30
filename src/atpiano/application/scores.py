"""Framework-independent score-job coordination."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from atpiano.application.errors import (
    ApplicationNotFoundError,
    bounded_error_message,
)
from atpiano.application.ports import SessionRepository
from atpiano.contracts.schemas import (
    ArtifactKind,
    AtpianoError,
    ErrorCode,
    Job,
    JobKind,
    RunStatus,
    ScoreVariant,
    ScoreVariantRequest,
)

CORRECTED_SCORE_STATE_SCHEMA = "atpiano.corrected-score-state.v1"


class ScoreExecutor(Protocol):
    """Score-process operations required by the application service."""

    def runtime_state(self) -> dict[str, Any]: ...

    def generate_snapshot(
        self,
        session_directory: Path,
        *,
        commit_sample: int,
    ) -> dict[str, Any]: ...

    def generate_variant(
        self,
        session_directory: Path,
        *,
        baseline_musicxml_path: Path,
        baseline_alignment_path: Path,
        clef_policy: str,
        target_key_fifths: int | None,
    ) -> dict[str, Any]: ...


class ScoreApplicationService:
    """Coordinate explicit score targets without depending on HTTP."""

    def __init__(
        self,
        repository: SessionRepository,
        executor: ScoreExecutor,
        *,
        workspace_id: str,
        current_session_id: Callable[[], str | None],
    ) -> None:
        self._repository = repository
        self._executor = executor
        self.workspace_id = workspace_id
        self._current_session_id = current_session_id
        self._lock = threading.Lock()
        self._status = "idle"
        self._error: str | None = None
        self._session_id: str | None = None
        self._commit_sample: int | None = None
        self._job_id: str | None = None
        self._created_at: datetime | None = None
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None

    def runtime_state(self) -> dict[str, Any]:
        return self._executor.runtime_state()

    def running_session_id(self) -> str | None:
        with self._lock:
            return self._session_id if self._status == "running" else None

    def _target(
        self,
        session_id: str | None,
    ) -> tuple[str | None, Path | None, int]:
        target_session_id = session_id or self._current_session_id()
        if target_session_id is None:
            return None, None, 0
        try:
            directory = self._repository.resolve(target_session_id)
            commit_sample = self._repository.horizon(
                target_session_id
            ).commit_sample
        except (LookupError, OSError, ValueError):
            if session_id is not None:
                raise
            return target_session_id, None, 0
        return target_session_id, directory, commit_sample

    def state(self, session_id: str | None = None) -> dict[str, Any]:
        target_session_id, directory, current_commit_sample = self._target(
            session_id
        )
        snapshot = (
            self._repository.current_score_snapshot(target_session_id)
            if directory is not None and target_session_id is not None
            else None
        )
        with self._lock:
            job_status = self._status
            job_error = self._error
            job_session_id = self._session_id
            job_commit_sample = self._commit_sample
        if job_session_id != target_session_id:
            job_status = "complete" if snapshot is not None else "idle"
            job_error = None
        elif job_status == "idle" and snapshot is not None:
            job_status = "complete"
        runtime = self.runtime_state()
        running = (
            job_status == "running"
            and job_session_id == target_session_id
        )
        return {
            "schema_version": CORRECTED_SCORE_STATE_SCHEMA,
            "status": job_status,
            "error": job_error,
            "runtime": runtime,
            "session_id": target_session_id,
            "commit_sample": current_commit_sample,
            "job": {
                "session_id": job_session_id,
                "commit_sample": job_commit_sample,
            },
            "snapshot": snapshot,
            "stale": bool(
                snapshot is not None
                and int(snapshot.get("commit_sample", -1))
                != current_commit_sample
            ),
            "can_generate": bool(
                runtime["available"]
                and target_session_id
                and current_commit_sample > 0
                and not running
            ),
        }

    def start(
        self,
        session_id: str | None = None,
        *,
        expected_commit_sample: int | None = None,
    ) -> Job:
        runtime = self.runtime_state()
        if not runtime["available"]:
            raise RuntimeError(str(runtime["error"]))
        target_session_id, directory, commit_sample = self._target(session_id)
        if directory is None or target_session_id is None:
            raise ValueError("no corrected session is available to score")
        if commit_sample <= 0:
            raise ValueError(
                "the session has no committed prefix to score yet"
            )
        if (
            expected_commit_sample is not None
            and expected_commit_sample != commit_sample
        ):
            raise ValueError("score request commit horizon is stale")
        job_id = f"job-score:{uuid.uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)
        with self._lock:
            if self._status == "running":
                raise RuntimeError(
                    "a committed score snapshot is already running"
                )
            self._status = "running"
            self._error = None
            self._session_id = target_session_id
            self._commit_sample = commit_sample
            self._job_id = job_id
            self._created_at = created_at
            self._started_at = created_at
            self._completed_at = None
        thread = threading.Thread(
            target=self._run,
            args=(
                job_id,
                target_session_id,
                directory,
                commit_sample,
            ),
            name=f"atpiano-score-{target_session_id}",
            daemon=True,
        )
        thread.start()
        return self.job(job_id)

    def _run(
        self,
        job_id: str,
        session_id: str,
        directory: Path,
        commit_sample: int,
    ) -> None:
        try:
            self._executor.generate_snapshot(
                directory,
                commit_sample=commit_sample,
            )
        except Exception as error:
            with self._lock:
                if (
                    self._job_id == job_id
                    and self._session_id == session_id
                    and self._commit_sample == commit_sample
                ):
                    self._status = "failed"
                    self._error = bounded_error_message(
                        error,
                        fallback="Score generation failed.",
                    )
                    self._completed_at = datetime.now(timezone.utc)
        else:
            with self._lock:
                if (
                    self._job_id == job_id
                    and self._session_id == session_id
                    and self._commit_sample == commit_sample
                ):
                    self._status = "complete"
                    self._error = None
                    self._completed_at = datetime.now(timezone.utc)

    def job(self, job_id: str) -> Job:
        with self._lock:
            if job_id != self._job_id:
                raise ApplicationNotFoundError("job does not exist")
            status = self._status
            error_text = self._error
            session_id = self._session_id
            commit_sample = self._commit_sample
            created_at = self._created_at
            started_at = self._started_at
            completed_at = self._completed_at
        if (
            session_id is None
            or commit_sample is None
            or created_at is None
        ):
            raise ApplicationNotFoundError("job does not exist")
        error = (
            AtpianoError(
                error_id=f"error:{job_id}",
                code=ErrorCode.INTERNAL,
                message=error_text or "Score generation failed.",
                retryable=True,
                workspace_id=self.workspace_id,
                session_id=session_id,
                job_id=job_id,
            )
            if status == "failed"
            else None
        )
        return Job(
            workspace_id=self.workspace_id,
            session_id=session_id,
            job_id=job_id,
            kind=JobKind.SCORE,
            status=RunStatus(status),
            input_horizon_sample=commit_sample,
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )

    def create_variant(
        self,
        request: ScoreVariantRequest,
    ) -> ScoreVariant:
        if request.workspace_id != self.workspace_id:
            raise ApplicationNotFoundError("workspace does not exist")
        with self._lock:
            if self._status == "running":
                raise RuntimeError(
                    "a committed score snapshot is already running"
                )
        directory = self._repository.resolve(request.session_id)
        musicxml, musicxml_path = (
            self._repository.get_artifact_with_path(
                request.session_id,
                request.baseline_musicxml_artifact_id,
            )
        )
        alignment, alignment_path = (
            self._repository.get_artifact_with_path(
                request.session_id,
                request.baseline_alignment_artifact_id,
            )
        )
        if (
            musicxml.kind is not ArtifactKind.MUSICXML
            or alignment.kind is not ArtifactKind.SCORE_ALIGNMENT
        ):
            raise ValueError(
                "score variant request requires baseline artifacts"
            )
        record = self._executor.generate_variant(
            directory,
            baseline_musicxml_path=musicxml_path,
            baseline_alignment_path=alignment_path,
            clef_policy=request.clef_policy.value,
            target_key_fifths=request.target_key_fifths,
        )
        return next(
            variant
            for variant in self._repository.score_variants(
                request.session_id
            ).items
            if variant.score_variant_id == record["variant_id"]
        )
