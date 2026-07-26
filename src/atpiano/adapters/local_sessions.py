"""Explicit contract views over existing corrected-session directories."""

from __future__ import annotations

import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atpiano import __version__
from atpiano.contracts.schemas import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    ArtifactKind,
    ArtifactPage,
    DeleteSessionResult,
    EventKind,
    EventLifecycle,
    EventPage,
    EventRevision,
    Horizon,
    OffsetState,
    Provenance,
    Session,
    SessionPage,
    SessionStatus,
    SourceKind,
    Workspace,
    WorkspaceMode,
)
from atpiano.corrected import (
    CORRECTED_EVENT_SCHEMA,
    CORRECTED_HORIZONS_SCHEMA,
    CORRECTED_SESSION_SCHEMA,
)
from atpiano.corrected_export import (
    MAX_QUERY_LIMIT,
    query_history_index,
    query_materialized_index,
)
from atpiano.score_snapshot import (
    SCORE_SNAPSHOT_SCHEMA,
    score_snapshot_is_plausible,
)
from atpiano.util import read_json, sha256_file

LOCAL_WORKSPACE_ID = "local"
SESSION_ID_PATTERN = re.compile(r"\d{8}T\d{6}-[0-9a-f]{12}")
DEFAULT_PAGE_LIMIT = 100
MAX_SESSION_PAGE_LIMIT = 500


class LocalSessionNotFoundError(LookupError):
    pass


class LocalSessionConflictError(RuntimeError):
    pass


def _parse_time(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _legacy_run_id(session_id: str) -> str:
    return f"legacy-v2:{session_id}"


class LocalSessionStore:
    """Bounded catalog, reader, artifact, and recoverable-trash adapter."""

    def __init__(self, workspace_directory: Path) -> None:
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)

    def _validate_session_id(self, session_id: str) -> str:
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise LocalSessionNotFoundError("session does not exist")
        return session_id

    def resolve(self, session_id: str) -> Path:
        session_id = self._validate_session_id(session_id)
        candidate = (self.workspace_directory / session_id).resolve()
        if candidate.parent != self.workspace_directory:
            raise LocalSessionNotFoundError("session does not exist")
        manifest = candidate / "session.json"
        if not manifest.is_file():
            raise LocalSessionNotFoundError("session does not exist")
        return candidate

    def _manifests(self) -> list[tuple[datetime, str, Path, dict[str, Any]]]:
        rows: list[tuple[datetime, str, Path, dict[str, Any]]] = []
        for manifest_path in self.workspace_directory.glob("*/session.json"):
            session_id = manifest_path.parent.name
            if not SESSION_ID_PATTERN.fullmatch(session_id):
                continue
            try:
                manifest = read_json(manifest_path)
                if (
                    manifest.get("schema_version") != CORRECTED_SESSION_SCHEMA
                    or manifest.get("session_id") != session_id
                ):
                    continue
                started_at = _parse_time(
                    manifest.get("started_at"),
                    field="session.started_at",
                )
            except (OSError, TypeError, ValueError):
                continue
            rows.append((started_at, session_id, manifest_path.parent, manifest))
        rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return rows

    def workspace(self) -> Workspace:
        manifests = self._manifests()
        if manifests:
            created_at = min(row[0] for row in manifests)
        else:
            created_at = datetime.fromtimestamp(
                self.workspace_directory.stat().st_mtime,
                tz=timezone.utc,
            )
        return Workspace(
            workspace_id=LOCAL_WORKSPACE_ID,
            name="On this device",
            mode=WorkspaceMode.LOCAL,
            created_at=created_at,
        )

    def _available_artifact_kinds(self, directory: Path) -> tuple[ArtifactKind, ...]:
        kinds: list[ArtifactKind] = []
        if any((directory / "audio").glob("*.wav")):
            kinds.append(ArtifactKind.AUDIO)
        if (directory / "exports" / "session.jsonl").is_file():
            kinds.append(ArtifactKind.EVENT_HISTORY)
        if (directory / "exports" / "session.mid").is_file():
            kinds.append(ArtifactKind.MIDI)
        score_pointer = directory / "score" / "current.json"
        if score_pointer.is_file() and self._valid_score_pointer(score_pointer):
            kinds.append(ArtifactKind.MUSICXML)
            try:
                pointer = read_json(score_pointer)
                alignment = (
                    directory / Path(str(pointer["alignment"]["path"]))
                ).resolve()
                if (
                    alignment.is_relative_to(directory)
                    and alignment.is_file()
                ):
                    kinds.append(ArtifactKind.SCORE_ALIGNMENT)
            except (KeyError, OSError, TypeError, ValueError):
                pass
        return tuple(kinds)

    @staticmethod
    def _valid_score_pointer(score_pointer: Path) -> bool:
        try:
            return score_snapshot_is_plausible(read_json(score_pointer))
        except (OSError, ValueError):
            return False

    def _session(
        self,
        directory: Path,
        manifest: dict[str, Any],
        *,
        active_session_id: str | None,
    ) -> Session:
        session_id = str(manifest["session_id"])
        persisted_status = str(manifest.get("status", "failed"))
        status = (
            SessionStatus.ACTIVE
            if (
                session_id == active_session_id
                and persisted_status == "active"
            )
            else (
                SessionStatus.FAILED
                if persisted_status == "active"
                else SessionStatus(persisted_status)
            )
        )
        completed_value = manifest.get("completed_at")
        completed_at = (
            _parse_time(completed_value, field="session.completed_at")
            if completed_value
            else None
        )
        source = SourceKind(str(manifest["source"]))
        started_at = _parse_time(manifest["started_at"], field="session.started_at")
        display_time = started_at.astimezone().strftime("%d %b %Y, %H:%M")
        return Session(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            status=status,
            source=source,
            sample_rate_hz=int(manifest["sample_rate_hz"]),
            source_frame_count=int(manifest.get("source_frame_count", 0)),
            started_at=started_at,
            completed_at=completed_at,
            active_capture_id=(
                f"capture:{session_id}"
                if (
                    session_id == active_session_id
                    and persisted_status == "active"
                )
                else None
            ),
            current_transcription_run_id=_legacy_run_id(session_id),
            display_name=f"{display_time}, {source.value}",
            available_artifact_kinds=self._available_artifact_kinds(directory),
        )

    def list_sessions(
        self,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        active_session_id: str | None = None,
    ) -> SessionPage:
        if not 0 < limit <= MAX_SESSION_PAGE_LIMIT:
            raise ValueError("session page limit is invalid")
        rows = self._manifests()
        start = 0
        if cursor is not None:
            indices = [index for index, row in enumerate(rows) if row[1] == cursor]
            if not indices:
                raise ValueError("session cursor is invalid")
            start = indices[0] + 1
        selected = rows[start : start + limit]
        next_cursor = (
            selected[-1][1] if start + len(selected) < len(rows) else None
        )
        return SessionPage(
            workspace_id=LOCAL_WORKSPACE_ID,
            items=tuple(
                self._session(directory, manifest, active_session_id=active_session_id)
                for _, _, directory, manifest in selected
            ),
            next_cursor=next_cursor,
        )

    def get_session(
        self,
        session_id: str,
        *,
        active_session_id: str | None = None,
    ) -> Session:
        directory = self.resolve(session_id)
        manifest = read_json(directory / "session.json")
        if (
            manifest.get("schema_version") != CORRECTED_SESSION_SCHEMA
            or manifest.get("session_id") != session_id
        ):
            raise LocalSessionNotFoundError("session does not exist")
        return self._session(
            directory,
            manifest,
            active_session_id=active_session_id,
        )

    def horizon(self, session_id: str) -> Horizon:
        directory = self.resolve(session_id)
        value = read_json(directory / "horizons.json")
        if value.get("schema_version") != CORRECTED_HORIZONS_SCHEMA:
            raise ValueError("session horizon schema is unsupported")
        return Horizon(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            transcription_run_id=_legacy_run_id(session_id),
            sample_rate_hz=int(value["sample_rate_hz"]),
            audio_head_sample=int(value["audio_head_sample"]),
            provisional_sample=int(value["provisional_sample"]),
            commit_sample=int(value["commit_sample"]),
            recorded_at=_parse_time(value["recorded_at"], field="horizon.recorded_at"),
        )

    def _event(self, session_id: str, value: dict[str, Any]) -> EventRevision:
        if (
            value.get("schema_version") != CORRECTED_EVENT_SCHEMA
            or value.get("session_id") != session_id
        ):
            raise ValueError("corrected event schema or target is unsupported")
        controller = value.get("controller")
        kind = (
            EventKind.SUSTAIN
            if controller == 64
            else EventKind.SOFT_PEDAL
            if controller == 67
            else EventKind.NOTE
        )
        revision = int(value["revision"])
        return EventRevision(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            transcription_run_id=_legacy_run_id(session_id),
            event_id=str(value["event_id"]),
            revision=revision,
            lane=str(value["lane"]),
            kind=kind,
            lifecycle=EventLifecycle(str(value["lifecycle"])),
            onset_sample=int(value["onset_sample"]),
            offset_sample=(
                int(value["offset_sample"])
                if value.get("offset_sample") is not None
                else None
            ),
            offset_state=OffsetState(str(value["offset_state"])),
            pitch=int(value["pitch"]) if value.get("pitch") is not None else None,
            velocity=(
                int(value["velocity"])
                if value.get("velocity") is not None
                else None
            ),
            confidence=(
                float(value["confidence"])
                if value.get("confidence") is not None
                else None
            ),
            supersedes_revision=revision - 1 if revision > 1 else None,
        )

    def events(
        self,
        session_id: str,
        *,
        start_sample: int,
        end_sample: int,
        cursor: str | None = None,
        limit: int = 1024,
    ) -> EventPage:
        directory = self.resolve(session_id)
        if cursor not in {None, ""}:
            raise ValueError("materialized event ranges do not use a cursor")
        if not 0 < limit <= MAX_QUERY_LIMIT:
            raise ValueError("event page limit is invalid")
        values = query_materialized_index(
            directory / "event-index.sqlite3",
            start_sample=start_sample,
            end_sample=end_sample,
        )
        if len(values) > limit:
            raise ValueError("materialized event range exceeds page limit")
        return EventPage(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            start_sample=start_sample,
            end_sample=end_sample,
            items=tuple(self._event(session_id, value) for value in values),
            next_cursor=None,
        )

    def history(
        self,
        session_id: str,
        *,
        after_sequence: int,
        limit: int = 1024,
    ) -> tuple[EventRevision, ...]:
        directory = self.resolve(session_id)
        values = query_history_index(
            directory / "event-index.sqlite3",
            after_sequence=after_sequence,
            limit=limit,
        )
        return tuple(self._event(session_id, value) for value in values)

    def _artifact_candidates(self, session_id: str) -> list[tuple[Artifact, Path]]:
        directory = self.resolve(session_id)
        session = self.get_session(session_id)
        audio_horizons: dict[Path, int] = {}
        score_horizons: dict[Path, int] = {}
        audio_index = directory / "audio" / "segments.jsonl"
        if audio_index.is_file():
            for line in audio_index.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                row = json.loads(line)
                segment_path = (audio_index.parent / str(row["path"])).resolve()
                audio_horizons[segment_path] = (
                    int(row["first_sample"]) + int(row["frame_count"])
                )
        paths = [
            *sorted((directory / "audio").glob("*.wav")),
            *sorted((directory / "playback").glob("*.mp3")),
            *sorted((directory / "exports").glob("*")),
        ]
        score_pointer = directory / "score" / "current.json"
        if score_pointer.is_file() and self._valid_score_pointer(score_pointer):
            paths.append(score_pointer)
            try:
                pointer = read_json(score_pointer)
                score_horizon = int(pointer["commit_sample"])
                score_horizons[score_pointer.resolve()] = score_horizon
                for section in ("midi", "musicxml", "alignment"):
                    relative = Path(str(pointer[section]["path"]))
                    candidate = (directory / relative).resolve()
                    if candidate.is_relative_to(directory) and candidate.is_file():
                        paths.append(candidate)
                        score_horizons[candidate] = score_horizon
            except (KeyError, OSError, TypeError, ValueError):
                pass
        unique_paths = sorted({path.resolve() for path in paths if path.is_file()})
        artifacts = [
            (
                self._artifact(
                    session_id,
                    path,
                    source_horizon_sample=audio_horizons.get(
                        path,
                        score_horizons.get(
                            path,
                            session.source_frame_count,
                        ),
                    ),
                ),
                path,
            )
            for path in unique_paths
        ]
        artifacts.sort(key=lambda pair: (pair[0].kind.value, pair[0].filename))
        return artifacts

    def _artifact(
        self,
        session_id: str,
        path: Path,
        *,
        source_horizon_sample: int,
    ) -> Artifact:
        directory = self.resolve(session_id)
        path = path.resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise LocalSessionNotFoundError("artifact does not exist")
        digest = sha256_file(path)
        media_type = mimetypes.guess_type(path.name)[0]
        if path.suffix == ".jsonl":
            media_type = "application/x-ndjson"
        elif path.suffix in {".mid", ".midi"}:
            media_type = "audio/midi"
        elif path.suffix == ".musicxml":
            media_type = "application/vnd.recordare.musicxml+xml"
        media_type = media_type or "application/octet-stream"
        kind = (
            ArtifactKind.AUDIO
            if path.suffix in {".wav", ".mp3"}
            else ArtifactKind.EVENT_HISTORY
            if path.suffix == ".jsonl"
            else ArtifactKind.MIDI
            if path.suffix in {".mid", ".midi"}
            else ArtifactKind.MUSICXML
            if path.suffix == ".musicxml"
            else ArtifactKind.SCORE_ALIGNMENT
            if path.name == "alignment.json"
            else ArtifactKind.MANIFEST
        )
        provenance = Provenance(
            application_version=__version__,
            schema_versions={
                "contract": CONTRACT_SCHEMA_VERSION,
                "source": CORRECTED_SESSION_SCHEMA,
            },
            adapter="legacy-corrected-session-v1",
            execution_backend="local-filesystem",
            source_artifact_sha256=(),
        )
        return Artifact(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            artifact_id=f"artifact:{digest[:24]}",
            kind=kind,
            media_type=media_type,
            filename=path.name,
            sha256=digest,
            byte_count=path.stat().st_size,
            source_horizon_sample=source_horizon_sample,
            created_at=datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.utc,
            ),
            transcription_run_id=_legacy_run_id(session_id),
            provenance=provenance,
        )

    def _retained_score_artifacts(
        self,
        session_id: str,
    ) -> list[tuple[Artifact, Path]]:
        directory = self.resolve(session_id)
        snapshots = directory / "score" / "snapshots"
        artifacts: list[tuple[Artifact, Path]] = []
        for snapshot in sorted(path for path in snapshots.glob("*") if path.is_dir()):
            try:
                manifest = read_json(snapshot / "manifest.json")
                if (
                    manifest.get("schema_version") != SCORE_SNAPSHOT_SCHEMA
                    or manifest.get("session_id") != session_id
                    or not score_snapshot_is_plausible(manifest)
                ):
                    continue
                commit_sample = int(manifest["commit_sample"])
            except (KeyError, OSError, TypeError, ValueError):
                continue
            for section in ("musicxml", "alignment"):
                try:
                    resolved = (
                        directory / Path(str(manifest[section]["path"]))
                    ).resolve()
                    if (
                        resolved.parent != snapshot.resolve()
                        or not resolved.is_file()
                        or str(manifest[section]["sha256"])
                        != sha256_file(resolved)
                    ):
                        continue
                except (KeyError, OSError, TypeError, ValueError):
                    continue
                artifacts.append(
                    (
                        self._artifact(
                            session_id,
                            resolved,
                            source_horizon_sample=commit_sample,
                        ),
                        resolved,
                    )
                )
        return artifacts

    def list_artifacts(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> ArtifactPage:
        if not 0 < limit <= MAX_SESSION_PAGE_LIMIT:
            raise ValueError("artifact page limit is invalid")
        candidates = self._artifact_candidates(session_id)
        start = 0
        if cursor is not None:
            indices = [
                index
                for index, pair in enumerate(candidates)
                if pair[0].artifact_id == cursor
            ]
            if not indices:
                raise ValueError("artifact cursor is invalid")
            start = indices[0] + 1
        selected = candidates[start : start + limit]
        next_cursor = (
            selected[-1][0].artifact_id
            if start + len(selected) < len(candidates)
            else None
        )
        return ArtifactPage(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            items=tuple(pair[0] for pair in selected),
            next_cursor=next_cursor,
        )

    def get_artifact(self, session_id: str, artifact_id: str) -> Artifact:
        return self.get_artifact_with_path(session_id, artifact_id)[0]

    def get_artifact_with_path(
        self,
        session_id: str,
        artifact_id: str,
    ) -> tuple[Artifact, Path]:
        for artifact, path in self._artifact_candidates(session_id):
            if artifact.artifact_id == artifact_id:
                return artifact, path
        if re.fullmatch(r"artifact:[0-9a-f]{24}", artifact_id):
            for artifact, path in self._retained_score_artifacts(session_id):
                if artifact.artifact_id == artifact_id:
                    return artifact, path
        raise LocalSessionNotFoundError("artifact does not exist")

    def trash_session(
        self,
        session_id: str,
        *,
        active_session_id: str | None,
        running_score_session_id: str | None,
    ) -> DeleteSessionResult:
        directory = self.resolve(session_id)
        if session_id == active_session_id:
            raise LocalSessionConflictError("active session cannot be deleted")
        if session_id == running_score_session_id:
            raise LocalSessionConflictError(
                "session with a running score job cannot be deleted"
            )
        trash = self.workspace_directory / ".trash"
        trash.mkdir(exist_ok=True)
        deleted_at = datetime.now(timezone.utc)
        stamp = deleted_at.strftime("%Y%m%dT%H%M%S%fZ")
        target = trash / f"{session_id}-{stamp}"
        if target.exists():
            raise LocalSessionConflictError("trash target already exists")
        directory.replace(target)
        return DeleteSessionResult(
            workspace_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            trashed_at=deleted_at,
        )
