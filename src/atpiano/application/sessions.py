"""Session catalog, historical reads, artifacts, and deletion policy."""

from __future__ import annotations

from pathlib import Path

from atpiano.application.errors import ApplicationNotFoundError
from atpiano.application.ports import SessionRepository
from atpiano.contracts.schemas import (
    Artifact,
    ArtifactPage,
    DeleteSessionResult,
    EventPage,
    EventRevision,
    Horizon,
    ScoreVariantPage,
    Session,
    SessionAnnotation,
    SessionPage,
    SessionPerformerAttribution,
    WorkspacePage,
)


class SessionApplicationService:
    """Explicitly addressed session operations independent of HTTP."""

    def __init__(
        self,
        repository: SessionRepository,
        *,
        workspace_id: str,
    ) -> None:
        self._repository = repository
        self.workspace_id = workspace_id

    def require_workspace(self, workspace_id: str) -> None:
        if workspace_id != self.workspace_id:
            raise ApplicationNotFoundError("workspace does not exist")

    def list_workspaces(self) -> WorkspacePage:
        return WorkspacePage(
            items=(self._repository.workspace(),),
            next_cursor=None,
        )

    def list_sessions(
        self,
        workspace_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
        active_session_id: str | None = None,
    ) -> SessionPage:
        self.require_workspace(workspace_id)
        return self._repository.list_sessions(
            cursor=cursor,
            limit=limit,
            active_session_id=active_session_id,
        )

    def get_session(
        self,
        workspace_id: str,
        session_id: str,
        *,
        active_session_id: str | None = None,
    ) -> Session:
        self.require_workspace(workspace_id)
        return self._repository.get_session(
            session_id,
            active_session_id=active_session_id,
        )

    def get_horizon(
        self,
        workspace_id: str,
        session_id: str,
    ) -> Horizon:
        self.require_workspace(workspace_id)
        return self._repository.horizon(session_id)

    def get_events(
        self,
        workspace_id: str,
        session_id: str,
        *,
        start_sample: int,
        end_sample: int,
        cursor: str | None = None,
        limit: int = 1024,
    ) -> EventPage:
        self.require_workspace(workspace_id)
        return self._repository.events(
            session_id,
            start_sample=start_sample,
            end_sample=end_sample,
            cursor=cursor,
            limit=limit,
        )

    def get_history(
        self,
        workspace_id: str,
        session_id: str,
        *,
        after_sequence: int,
        limit: int = 1024,
    ) -> tuple[EventRevision, ...]:
        self.require_workspace(workspace_id)
        return self._repository.history(
            session_id,
            after_sequence=after_sequence,
            limit=limit,
        )

    def list_artifacts(
        self,
        workspace_id: str,
        session_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> ArtifactPage:
        self.require_workspace(workspace_id)
        return self._repository.list_artifacts(
            session_id,
            cursor=cursor,
            limit=limit,
        )

    def get_artifact(
        self,
        workspace_id: str,
        session_id: str,
        artifact_id: str,
    ) -> tuple[Artifact, Path]:
        self.require_workspace(workspace_id)
        return self._repository.get_artifact_with_path(
            session_id,
            artifact_id,
        )

    def list_score_variants(
        self,
        workspace_id: str,
        session_id: str,
    ) -> ScoreVariantPage:
        self.require_workspace(workspace_id)
        return self._repository.score_variants(session_id)

    def update_session_annotation(
        self,
        workspace_id: str,
        session_id: str,
        *,
        display_name: str,
    ) -> SessionAnnotation:
        self.require_workspace(workspace_id)
        return self._repository.update_session_annotation(
            session_id,
            display_name=display_name,
        )

    def update_session_performer(
        self,
        workspace_id: str,
        session_id: str,
        *,
        performed_by_profile_id: str | None,
    ) -> SessionPerformerAttribution:
        self.require_workspace(workspace_id)
        return self._repository.update_session_performer(
            session_id,
            performed_by_profile_id=performed_by_profile_id,
        )

    def delete_session(
        self,
        workspace_id: str,
        session_id: str,
        *,
        active_session_id: str | None,
        running_score_session_id: str | None,
    ) -> DeleteSessionResult:
        self.require_workspace(workspace_id)
        return self._repository.trash_session(
            session_id,
            active_session_id=active_session_id,
            running_score_session_id=running_score_session_id,
        )
