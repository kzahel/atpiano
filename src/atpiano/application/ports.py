"""Ports consumed by the framework-independent application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from atpiano.contracts.schemas import (
    Artifact,
    ArtifactPage,
    DeleteSessionResult,
    EventPage,
    EventRevision,
    Horizon,
    ScoreVariantPage,
    Session,
    SessionPage,
    Workspace,
)


class SessionRepository(Protocol):
    """Persistent session catalog and artifact operations."""

    def workspace(self) -> Workspace: ...

    def list_sessions(
        self,
        *,
        cursor: str | None = None,
        limit: int = 100,
        active_session_id: str | None = None,
    ) -> SessionPage: ...

    def get_session(
        self,
        session_id: str,
        *,
        active_session_id: str | None = None,
    ) -> Session: ...

    def horizon(self, session_id: str) -> Horizon: ...

    def events(
        self,
        session_id: str,
        *,
        start_sample: int,
        end_sample: int,
        cursor: str | None = None,
        limit: int = 1024,
    ) -> EventPage: ...

    def history(
        self,
        session_id: str,
        *,
        after_sequence: int,
        limit: int = 1024,
    ) -> tuple[EventRevision, ...]: ...

    def list_artifacts(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> ArtifactPage: ...

    def get_artifact_with_path(
        self,
        session_id: str,
        artifact_id: str,
    ) -> tuple[Artifact, Path]: ...

    def score_variants(self, session_id: str) -> ScoreVariantPage: ...

    def current_score_snapshot(
        self,
        session_id: str,
    ) -> dict[str, Any] | None: ...

    def resolve(self, session_id: str) -> Path: ...

    def trash_session(
        self,
        session_id: str,
        *,
        active_session_id: str | None,
        running_score_session_id: str | None,
    ) -> DeleteSessionResult: ...
