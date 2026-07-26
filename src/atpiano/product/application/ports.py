"""Ports required by the next shared-application slices."""

from __future__ import annotations

from typing import Protocol

from atpiano.product.domain.schemas import (
    Artifact,
    ArtifactPage,
    Capture,
    DeleteSessionResult,
    EventPage,
    Horizon,
    Job,
    Session,
    SessionPage,
    Workspace,
)


class SessionCatalog(Protocol):
    def workspace(self) -> Workspace: ...

    def list_sessions(
        self,
        *,
        cursor: str | None,
        limit: int,
        active_session_id: str | None,
    ) -> SessionPage: ...

    def get_session(
        self,
        session_id: str,
        *,
        active_session_id: str | None,
    ) -> Session: ...


class HistoricalSessionReader(Protocol):
    def horizon(self, session_id: str) -> Horizon: ...

    def events(
        self,
        session_id: str,
        *,
        start_sample: int,
        end_sample: int,
        cursor: str | None,
        limit: int,
    ) -> EventPage: ...


class ArtifactRepository(Protocol):
    def list_artifacts(
        self,
        session_id: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> ArtifactPage: ...

    def get_artifact(self, session_id: str, artifact_id: str) -> Artifact: ...


class CaptureCoordinator(Protocol):
    def active_capture(self) -> Capture | None: ...


class ScoreJobCoordinator(Protocol):
    def start(self, session_id: str, commit_sample: int) -> Job: ...

    def get(self, job_id: str) -> Job: ...


class RecoverableSessionTrash(Protocol):
    def trash_session(
        self,
        session_id: str,
        *,
        active_session_id: str | None,
        running_score_session_id: str | None,
    ) -> DeleteSessionResult: ...
