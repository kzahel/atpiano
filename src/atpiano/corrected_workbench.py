"""Loopback-only web application for bounded corrected-note sessions."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
import webbrowser
from collections.abc import Callable
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from pydantic import ValidationError

from atpiano.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalSessionConflictError,
    LocalSessionNotFoundError,
    LocalSessionStore,
)
from atpiano.contracts.schemas import (
    CONTRACT_SCHEMA_VERSION,
    PCM_PROTOCOL_VERSION,
    ArtifactAccess,
    AtpianoError,
    DeleteSessionRequest,
    ErrorCode,
    ErrorResponse,
    Job,
    JobKind,
    RunStatus,
    RuntimeCapabilities,
    RuntimeMode,
    ScoreJobStart,
    SourceKind,
    WorkspacePage,
)
from atpiano.corrected import (
    CorrectedSession,
    run_corrected_replay,
)
from atpiano.corrected_commit import CommitModel, CorrectedCommitLane
from atpiano.corrected_export import (
    MAX_QUERY_LIMIT,
    ensure_materialized_index,
    query_history_index,
    query_materialized_index,
    write_corrected_exports,
)
from atpiano.corrected_preview import CorrectedPreviewLane
from atpiano.live import LiveWindowModel, parse_pcm_block
from atpiano.score_snapshot import (
    SCORE_SNAPSHOT_SCHEMA,
    ScoreRunner,
    generate_score_snapshot,
    inspect_score_runtime,
    score_snapshot_is_plausible,
)
from atpiano.util import read_json, utc_now, write_json
from atpiano.websocket import encode_frame, encode_json, read_frame, websocket_accept

CORRECTED_WORKBENCH_SCHEMA = "atpiano.corrected-workbench.v1"
CORRECTED_STREAM_SCHEMA = "atpiano.corrected-stream.v1"
CORRECTED_SCORE_STATE_SCHEMA = "atpiano.corrected-score-state.v1"
MAX_CLIENT_METADATA_BYTES = 16 * 1024
MAX_VISIBLE_RANGE_S = 120.0
DEFAULT_MINIMUM_FREE_BYTES = 2 * 1024**3
WEB_ROOT = Path(__file__).with_name("web_v2")
EXPORT_ASSETS = {
    "/api/artifacts/exports/session.mid": "session.mid",
    "/api/artifacts/exports/session.jsonl": "session.jsonl",
    "/api/artifacts/exports/manifest.json": "manifest.json",
}
SCORE_ASSETS = {
    "/api/artifacts/score/current.musicxml": ("musicxml", "path"),
    "/api/artifacts/score/current.mid": ("midi", "path"),
}
SESSION_ID_PATTERN = re.compile(r"\d{8}T\d{6}-[0-9a-f]{12}")

PreviewModelFactory = Callable[[], LiveWindowModel]
CommitModelFactory = Callable[[], CommitModel]


def _new_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def _default_preview_model() -> LiveWindowModel:
    from atpiano.live import BasicPitchLiveModel

    return BasicPitchLiveModel()


def _default_commit_model(*, device: str) -> CommitModel:
    from atpiano.corrected_commit import TranskunCommitModel

    return TranskunCommitModel(device=device)


class CorrectedWorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        workspace_directory: Path,
        *,
        port: int,
        preview_model_factory: PreviewModelFactory = _default_preview_model,
        commit_model_factory: CommitModelFactory,
        minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
        replay_manifest: Path | None = None,
        replay_repeat: int = 1,
        replay_silence_s: float = 0.0,
        replay_realtime: bool = True,
        score_runtime: Path = Path("results/midi2score-runtime"),
        score_runner: ScoreRunner | None = None,
        web_root: Path = WEB_ROOT,
        application_mode: str = "corrected-workbench-v2",
    ) -> None:
        if minimum_free_bytes < 0:
            raise ValueError("minimum free bytes cannot be negative")
        if replay_repeat <= 0:
            raise ValueError("replay repetition count must be positive")
        if replay_silence_s < 0:
            raise ValueError("replay silence cannot be negative")
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        self.session_store = LocalSessionStore(self.workspace_directory)
        self.preview_model_factory = preview_model_factory
        self.commit_model_factory = commit_model_factory
        self.minimum_free_bytes = minimum_free_bytes
        self.replay_manifest = replay_manifest.resolve() if replay_manifest else None
        self.replay_repeat = replay_repeat
        self.replay_silence_s = replay_silence_s
        self.replay_realtime = replay_realtime
        self.score_runtime = score_runtime.resolve()
        self.score_runner = score_runner
        self.web_root = web_root.resolve()
        self.application_mode = application_mode
        self.state_lock = threading.Lock()
        self.model_lock = threading.Lock()
        self.score_lock = threading.Lock()
        self._preview_model: LiveWindowModel | None = None
        self._commit_model: CommitModel | None = None
        self._active_session: CorrectedSession | None = None
        self._session_id: str | None = None
        self._session_directory: Path | None = None
        self._status = "idle"
        self._error: str | None = None
        self._received_blocks = 0
        self._last_event_sequence = 0
        self._score_status = "idle"
        self._score_error: str | None = None
        self._score_session_id: str | None = None
        self._score_commit_sample: int | None = None
        self._score_job_id: str | None = None
        self._score_created_at: datetime | None = None
        self._score_started_at: datetime | None = None
        self._score_completed_at: datetime | None = None
        self._load_latest_session()
        super().__init__(("127.0.0.1", port), CorrectedWorkbenchHandler)

    def asset_path(self, request_path: str) -> Path | None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (self.web_root / relative).resolve()
        if self.web_root != candidate and self.web_root not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None

    def _load_latest_session(self) -> None:
        manifests = sorted(
            self.workspace_directory.glob("*/session.json"),
            key=lambda path: path.stat().st_mtime_ns,
        )
        if not manifests:
            return
        latest_path = manifests[-1]
        try:
            latest = read_json(latest_path)
        except (OSError, ValueError):
            return
        session_id = str(latest.get("session_id", ""))
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            return
        try:
            ensure_materialized_index(latest_path.parent / "event-index.sqlite3")
        except (FileNotFoundError, sqlite3.Error):
            return
        self._session_id = session_id
        self._session_directory = latest_path.parent
        persisted_status = str(latest.get("status", "failed"))
        if persisted_status == "active":
            self._status = "failed"
            self._error = "The prior process ended before this session stopped."
        else:
            self._status = persisted_status
            self._error = latest.get("error")

    def get_models(self) -> tuple[LiveWindowModel, CommitModel]:
        with self.model_lock:
            if self._preview_model is None:
                self._preview_model = self.preview_model_factory()
            if self._commit_model is None:
                self._commit_model = self.commit_model_factory()
            return self._preview_model, self._commit_model

    def claim_session(self, *, source: str) -> tuple[str, Path]:
        with self.state_lock:
            if self._active_session is not None or self._status in {
                "warming",
                "active",
                "stopping",
            }:
                raise RuntimeError("another corrected session is already active")
            session_id = _new_session_id()
            directory = self.workspace_directory / session_id
            self._session_id = session_id
            self._session_directory = directory
            self._status = "warming"
            self._error = None
            self._received_blocks = 0
            self._last_event_sequence = 0
        return session_id, directory

    def set_active(self, session: CorrectedSession) -> None:
        with self.state_lock:
            if session.session_id != self._session_id:
                raise RuntimeError("corrected session claim changed during startup")
            self._active_session = session
            self._status = "active"

    def record_delivery(self, events: list[dict[str, Any]]) -> None:
        with self.state_lock:
            self._received_blocks += 1
            if events:
                self._last_event_sequence = max(
                    self._last_event_sequence,
                    max(int(event["sequence"]) for event in events),
                )

    def complete_session(self) -> None:
        with self.state_lock:
            self._active_session = None
            self._status = "complete"
            self._error = None

    def fail_session(self, error: Exception) -> None:
        with self.state_lock:
            self._active_session = None
            self._status = "failed"
            self._error = f"{type(error).__name__}: {error}"

    def begin_stop(self) -> None:
        with self.state_lock:
            self._status = "stopping"

    def current_directory(self) -> Path | None:
        with self.state_lock:
            return self._session_directory

    def active_session_id(self) -> str | None:
        with self.state_lock:
            if self._active_session is not None:
                return self._active_session.session_id
            if self._status in {"warming", "active", "stopping"}:
                return self._session_id
            return None

    def public_state(self) -> dict[str, Any]:
        with self.state_lock:
            status = self._status
            error = self._error
            session_id = self._session_id
            directory = self._session_directory
            active = self._active_session
            received_blocks = self._received_blocks
            last_event_sequence = self._last_event_sequence
        session: dict[str, Any] | None = None
        horizons: dict[str, Any] | None = None
        lanes: list[dict[str, Any]] = []
        if active is not None:
            horizons = active.horizons.document(sample_rate_hz=active.sample_rate_hz)
            session = {
                "session_id": active.session_id,
                "status": status,
                "source": active.source,
                "realtime": active.realtime,
                "sample_rate_hz": active.sample_rate_hz,
                "source_frame_count": active.horizons.audio_head_sample,
                "started_at": active.started_at,
            }
            lanes = [lane.status() for lane in active.lanes]
            minimum_free_bytes = active.audio.minimum_free_bytes
        elif directory is not None and (directory / "session.json").is_file():
            try:
                session = read_json(directory / "session.json")
                horizon_path = directory / "horizons.json"
                horizons = read_json(horizon_path) if horizon_path.is_file() else None
                lanes = list(session.get("lanes", []))
                minimum_free_bytes = int(session.get("retention", {}).get("minimum_free_bytes", 0))
            except (OSError, TypeError, ValueError):
                session = None
                minimum_free_bytes = self.minimum_free_bytes
        else:
            minimum_free_bytes = self.minimum_free_bytes
        usage = shutil.disk_usage(self.workspace_directory)
        audio_frames = (
            int(horizons["audio_head_sample"])
            if horizons is not None
            else int((session or {}).get("source_frame_count", 0))
        )
        sample_rate_hz = int((session or {}).get("sample_rate_hz", 0))
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
                "free_bytes": usage.free,
                "minimum_free_bytes": minimum_free_bytes,
                "warning": usage.free < minimum_free_bytes * 5 // 4,
            },
            "transport": {
                "received_blocks": received_blocks,
                "last_event_sequence": last_event_sequence,
                "recovery": "bounded indexed sequence query",
            },
            "duration_s": (audio_frames / sample_rate_hz if sample_rate_hz else 0.0),
            "exports_ready": bool(
                directory is not None and (directory / "exports" / "manifest.json").is_file()
            ),
        }

    def _runtime_state(self) -> dict[str, Any]:
        if self.score_runner is not None:
            return {
                "available": True,
                "directory": str(self.score_runtime),
                "injected_runner": True,
            }
        return inspect_score_runtime(self.score_runtime)

    def _score_target(
        self,
        session_id: str | None,
    ) -> tuple[str | None, Path | None, int]:
        state = self.public_state()
        current_session = state.get("session")
        current_session_id = (
            str(current_session.get("session_id"))
            if isinstance(current_session, dict) and current_session.get("session_id")
            else None
        )
        target_session_id = session_id or current_session_id
        if target_session_id is None:
            return None, None, 0
        if target_session_id == current_session_id:
            directory = self.current_directory()
            horizons = state.get("horizons")
            commit_sample = (
                int(horizons.get("commit_sample", 0))
                if isinstance(horizons, dict)
                else 0
            )
            return target_session_id, directory, commit_sample
        directory = self.session_store.resolve(target_session_id)
        horizons = read_json(directory / "horizons.json")
        return target_session_id, directory, int(horizons.get("commit_sample", 0))

    def public_score_state(
        self,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        target_session_id, directory, current_commit_sample = self._score_target(
            session_id
        )
        snapshot: dict[str, Any] | None = None
        if directory is not None:
            snapshot_path = directory / "score" / "current.json"
            if snapshot_path.is_file():
                try:
                    candidate = read_json(snapshot_path)
                    if (
                        candidate.get("schema_version") == SCORE_SNAPSHOT_SCHEMA
                        and candidate.get("session_id") == target_session_id
                        and score_snapshot_is_plausible(candidate)
                    ):
                        snapshot = candidate
                except (OSError, ValueError):
                    pass
        with self.score_lock:
            job_status = self._score_status
            job_error = self._score_error
            job_session_id = self._score_session_id
            job_commit_sample = self._score_commit_sample
        if job_session_id != target_session_id:
            job_status = "complete" if snapshot is not None else "idle"
            job_error = None
        elif job_status == "idle" and snapshot is not None:
            job_status = "complete"
        runtime = self._runtime_state()
        running = job_status == "running" and job_session_id == target_session_id
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
                and int(snapshot.get("commit_sample", -1)) != current_commit_sample
            ),
            "can_generate": bool(
                runtime["available"]
                and target_session_id
                and current_commit_sample > 0
                and not running
            ),
        }

    def start_score(
        self,
        session_id: str | None = None,
        *,
        expected_commit_sample: int | None = None,
    ) -> Job:
        runtime = self._runtime_state()
        if not runtime["available"]:
            raise RuntimeError(str(runtime["error"]))
        target_session_id, directory, commit_sample = self._score_target(session_id)
        if directory is None or target_session_id is None:
            raise ValueError("no corrected session is available to score")
        if commit_sample <= 0:
            raise ValueError("the session has no committed prefix to score yet")
        if (
            expected_commit_sample is not None
            and expected_commit_sample != commit_sample
        ):
            raise ValueError("score request commit horizon is stale")
        job_id = f"job-score:{uuid.uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)
        with self.score_lock:
            if self._score_status == "running":
                raise RuntimeError("a committed score snapshot is already running")
            self._score_status = "running"
            self._score_error = None
            self._score_session_id = target_session_id
            self._score_commit_sample = commit_sample
            self._score_job_id = job_id
            self._score_created_at = created_at
            self._score_started_at = created_at
            self._score_completed_at = None
        thread = threading.Thread(
            target=self._run_score,
            args=(job_id, target_session_id, directory, commit_sample),
            name=f"atpiano-score-{target_session_id}",
            daemon=True,
        )
        thread.start()
        return self.score_job(job_id)

    def _run_score(
        self,
        job_id: str,
        session_id: str,
        directory: Path,
        commit_sample: int,
    ) -> None:
        try:
            generate_score_snapshot(
                directory,
                self.score_runtime,
                commit_sample=commit_sample,
                runner=self.score_runner,
            )
        except Exception as error:
            with self.score_lock:
                if (
                    self._score_job_id == job_id
                    and
                    self._score_session_id == session_id
                    and self._score_commit_sample == commit_sample
                ):
                    self._score_status = "failed"
                    self._score_error = f"{type(error).__name__}: {error}"
                    self._score_completed_at = datetime.now(timezone.utc)
        else:
            with self.score_lock:
                if (
                    self._score_job_id == job_id
                    and
                    self._score_session_id == session_id
                    and self._score_commit_sample == commit_sample
                ):
                    self._score_status = "complete"
                    self._score_error = None
                    self._score_completed_at = datetime.now(timezone.utc)

    def score_job(self, job_id: str) -> Job:
        with self.score_lock:
            if job_id != self._score_job_id:
                raise LocalSessionNotFoundError("job does not exist")
            status = self._score_status
            error_text = self._score_error
            session_id = self._score_session_id
            commit_sample = self._score_commit_sample
            created_at = self._score_created_at
            started_at = self._score_started_at
            completed_at = self._score_completed_at
        if (
            session_id is None
            or commit_sample is None
            or created_at is None
        ):
            raise LocalSessionNotFoundError("job does not exist")
        error = (
            AtpianoError(
                error_id=f"error:{job_id}",
                code=ErrorCode.INTERNAL,
                message=error_text or "Score generation failed.",
                retryable=True,
                workspace_id=LOCAL_WORKSPACE_ID,
                session_id=session_id,
                job_id=job_id,
            )
            if status == "failed"
            else None
        )
        return Job(
            workspace_id=LOCAL_WORKSPACE_ID,
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

    def delete_api_session(self, session_id: str) -> dict[str, Any]:
        with self.state_lock:
            active_session_id = (
                self._active_session.session_id
                if self._active_session is not None
                else self._session_id
                if self._status in {"warming", "active", "stopping"}
                else None
            )
            with self.score_lock:
                running_score_session_id = (
                    self._score_session_id
                    if self._score_status == "running"
                    else None
                )
            result = self.session_store.trash_session(
                session_id,
                active_session_id=active_session_id,
                running_score_session_id=running_score_session_id,
            )
            if self._session_id == session_id:
                self._session_id = None
                self._session_directory = None
                self._status = "idle"
                self._error = None
                self._received_blocks = 0
                self._last_event_sequence = 0
                self._load_latest_session()
        return result.model_dump(mode="json")

    def start_replay(self) -> None:
        if self.replay_manifest is None:
            raise ValueError("no replay manifest was configured")
        session_id, directory = self.claim_session(source="replay")
        thread = threading.Thread(
            target=self._run_replay,
            args=(session_id, directory),
            name=f"atpiano-replay-{session_id}",
            daemon=True,
        )
        thread.start()

    def _run_replay(self, session_id: str, directory: Path) -> None:
        try:
            preview_model, commit_model = self.get_models()
            manifest = run_corrected_replay(
                self.replay_manifest or Path(),
                directory,
                repeat=self.replay_repeat,
                silence_s=self.replay_silence_s,
                realtime=self.replay_realtime,
                minimum_free_bytes=self.minimum_free_bytes,
                preview_model=preview_model,
                commit_model=commit_model,
                session_callback=self.set_active,
            )
            if manifest["session_id"] != session_id:
                raise RuntimeError("corrected replay returned a different session")
            write_corrected_exports(directory)
        except Exception as error:
            self.fail_session(error)
        else:
            self.complete_session()


class CorrectedWorkbenchHandler(BaseHTTPRequestHandler):
    server: CorrectedWorkbenchServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_body(self, body: bytes) -> bool:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return False
        return True

    def _host_is_local(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
        }

    def _origin_is_local(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Origin") in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def _send_json(
        self,
        value: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self._write_body(body)

    def _require_local_host(self) -> bool:
        if self._host_is_local():
            return True
        self._send_json(
            {"error": "corrected workbench requests require the local address"},
            HTTPStatus.FORBIDDEN,
        )
        return False

    def _send_file(self, path: Path, *, include_body: bool) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not include_body:
            return
        with path.open("rb") as handle:
            while block := handle.read(64 * 1024):
                if not self._write_body(block):
                    return

    def _current_export(self, request_path: str) -> Path | None:
        name = EXPORT_ASSETS.get(request_path)
        directory = self.server.current_directory()
        if name is None or directory is None:
            return None
        return directory / "exports" / name

    def _current_score_asset(self, request_path: str) -> Path | None:
        selector = SCORE_ASSETS.get(request_path)
        directory = self.server.current_directory()
        if selector is None or directory is None:
            return None
        try:
            manifest = read_json(directory / "score" / "current.json")
            if not score_snapshot_is_plausible(manifest):
                return None
            section, field = selector
            relative_path = Path(str(manifest[section][field]))
            candidate = (directory / relative_path).resolve()
        except (KeyError, OSError, TypeError, ValueError):
            return None
        if directory.resolve() not in candidate.parents:
            return None
        return candidate

    def _send_api_error(
        self,
        message: str,
        *,
        code: ErrorCode,
        status: HTTPStatus,
        workspace_id: str | None = None,
        session_id: str | None = None,
        job_id: str | None = None,
    ) -> None:
        error = ErrorResponse(
            error=AtpianoError(
                error_id=f"error:{uuid.uuid4().hex[:16]}",
                code=code,
                message=message,
                retryable=code
                in {
                    ErrorCode.CAPTURE_BUSY,
                    ErrorCode.SCORE_BUSY,
                    ErrorCode.STORAGE_UNAVAILABLE,
                    ErrorCode.MODEL_UNAVAILABLE,
                    ErrorCode.INTERNAL,
                },
                workspace_id=workspace_id,
                session_id=session_id,
                job_id=job_id,
            )
        )
        self._send_json(error.model_dump(mode="json"), status)

    def _read_api_json(self) -> dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Content-Length is invalid") from error
        if not 0 < content_length <= 64 * 1024:
            raise ValueError("API request body size is invalid")
        try:
            value = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("API request body is invalid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("API request body must be an object")
        return value

    def _api_query_limit(
        self,
        query: dict[str, list[str]],
        *,
        default: int = 100,
    ) -> int:
        return int(query.get("limit", [str(default)])[0])

    def _get_api(
        self,
        request_path: str,
        query: dict[str, list[str]],
        *,
        include_body: bool,
    ) -> bool:
        prefix = "/api/v1"
        if not request_path.startswith(prefix):
            return False
        try:
            if request_path == f"{prefix}/capabilities":
                capabilities = RuntimeCapabilities(
                    runtime_mode=RuntimeMode.LOCAL,
                    supported_schema_versions=(CONTRACT_SCHEMA_VERSION,),
                    supported_pcm_protocol_versions=(PCM_PROTOCOL_VERSION,),
                    capture_sources=(SourceKind.MICROPHONE, SourceKind.REPLAY),
                    score_available=bool(
                        self.server._runtime_state().get("available")
                    ),
                    recoverable_delete=True,
                    max_pcm_block_frames=1_048_576,
                    max_event_range_samples=round(
                        MAX_VISIBLE_RANGE_S * 384_000
                    ),
                )
                self._send_json(capabilities.model_dump(mode="json"))
                return True
            if request_path == f"{prefix}/workspaces":
                page = WorkspacePage(
                    items=(self.server.session_store.workspace(),),
                    next_cursor=None,
                )
                self._send_json(page.model_dump(mode="json"))
                return True
            job_match = re.fullmatch(f"{prefix}/jobs/([^/]+)", request_path)
            if job_match:
                job = self.server.score_job(job_match.group(1))
                self._send_json(job.model_dump(mode="json"))
                return True
            sessions_match = re.fullmatch(
                f"{prefix}/workspaces/([^/]+)/sessions",
                request_path,
            )
            if sessions_match:
                workspace_id = sessions_match.group(1)
                if workspace_id != LOCAL_WORKSPACE_ID:
                    raise LocalSessionNotFoundError("workspace does not exist")
                page = self.server.session_store.list_sessions(
                    cursor=query.get("cursor", [None])[0],
                    limit=self._api_query_limit(query),
                    active_session_id=self.server.active_session_id(),
                )
                self._send_json(page.model_dump(mode="json"))
                return True
            event_match = re.fullmatch(
                f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)/events",
                request_path,
            )
            if event_match:
                workspace_id, session_id = event_match.groups()
                if workspace_id != LOCAL_WORKSPACE_ID:
                    raise LocalSessionNotFoundError("workspace does not exist")
                page = self.server.session_store.events(
                    session_id,
                    start_sample=int(query.get("start_sample", ["0"])[0]),
                    end_sample=int(query.get("end_sample", ["0"])[0]),
                    cursor=query.get("cursor", [None])[0],
                    limit=self._api_query_limit(query, default=1024),
                )
                self._send_json(page.model_dump(mode="json"))
                return True
            horizon_match = re.fullmatch(
                f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)/horizon",
                request_path,
            )
            if horizon_match:
                workspace_id, session_id = horizon_match.groups()
                if workspace_id != LOCAL_WORKSPACE_ID:
                    raise LocalSessionNotFoundError("workspace does not exist")
                horizon = self.server.session_store.horizon(session_id)
                self._send_json(horizon.model_dump(mode="json"))
                return True
            artifacts_match = re.fullmatch(
                f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)/artifacts",
                request_path,
            )
            if artifacts_match:
                workspace_id, session_id = artifacts_match.groups()
                if workspace_id != LOCAL_WORKSPACE_ID:
                    raise LocalSessionNotFoundError("workspace does not exist")
                page = self.server.session_store.list_artifacts(
                    session_id,
                    cursor=query.get("cursor", [None])[0],
                    limit=self._api_query_limit(query),
                )
                self._send_json(page.model_dump(mode="json"))
                return True
            artifact_match = re.fullmatch(
                (
                    f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)"
                    r"/artifacts/([^/]+)/(access|content)"
                ),
                request_path,
            )
            if artifact_match:
                workspace_id, session_id, artifact_id, operation = (
                    artifact_match.groups()
                )
                if workspace_id != LOCAL_WORKSPACE_ID:
                    raise LocalSessionNotFoundError("workspace does not exist")
                artifact, path = self.server.session_store.get_artifact_with_path(
                    session_id,
                    artifact_id,
                )
                if operation == "content":
                    self._send_file(path, include_body=include_body)
                else:
                    content_url = (
                        f"{prefix}/workspaces/{quote(workspace_id, safe='')}"
                        f"/sessions/{quote(session_id, safe='')}"
                        f"/artifacts/{quote(artifact_id, safe='')}/content"
                    )
                    access = ArtifactAccess(
                        workspace_id=workspace_id,
                        session_id=session_id,
                        artifact_id=artifact_id,
                        media_type=artifact.media_type,
                        download_name=artifact.filename,
                        url=content_url,
                    )
                    self._send_json(access.model_dump(mode="json"))
                return True
            session_match = re.fullmatch(
                f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)",
                request_path,
            )
            if session_match:
                workspace_id, session_id = session_match.groups()
                if workspace_id != LOCAL_WORKSPACE_ID:
                    raise LocalSessionNotFoundError("workspace does not exist")
                session = self.server.session_store.get_session(
                    session_id,
                    active_session_id=self.server.active_session_id(),
                )
                self._send_json(session.model_dump(mode="json"))
                return True
        except LocalSessionNotFoundError as error:
            self._send_api_error(
                str(error),
                code=ErrorCode.NOT_FOUND,
                status=HTTPStatus.NOT_FOUND,
            )
            return True
        except (OSError, sqlite3.Error, TypeError, ValueError) as error:
            self._send_api_error(
                str(error),
                code=ErrorCode.INVALID_REQUEST,
                status=HTTPStatus.BAD_REQUEST,
            )
            return True
        self._send_api_error(
            "API resource does not exist",
            code=ErrorCode.NOT_FOUND,
            status=HTTPStatus.NOT_FOUND,
        )
        return True

    def do_GET(self) -> None:
        if not self._require_local_host():
            return
        parsed = urlsplit(self.path)
        request_path = unquote(parsed.path)
        if self._get_api(
            request_path,
            parse_qs(parsed.query),
            include_body=True,
        ):
            return
        if request_path == "/api/live":
            self._handle_live_websocket()
            return
        asset = self.server.asset_path(request_path)
        if asset is not None:
            self._send_file(asset, include_body=True)
            return
        if request_path == "/api/config":
            self._send_json(
                {
                    "schema_version": CORRECTED_WORKBENCH_SCHEMA,
                    "mode": self.server.application_mode,
                    "stream_schema": CORRECTED_STREAM_SCHEMA,
                    "max_visible_range_s": MAX_VISIBLE_RANGE_S,
                    "replay": {
                        "configured": self.server.replay_manifest is not None,
                        "manifest": (
                            str(self.server.replay_manifest)
                            if self.server.replay_manifest
                            else None
                        ),
                        "repeat": self.server.replay_repeat,
                        "silence_s": self.server.replay_silence_s,
                        "realtime": self.server.replay_realtime,
                    },
                    "score": self.server._runtime_state(),
                }
            )
            return
        if request_path == "/api/session":
            self._send_json(self.server.public_state())
            return
        if request_path == "/api/score":
            self._send_json(self.server.public_score_state())
            return
        if request_path == "/api/events":
            self._get_events(parse_qs(parsed.query))
            return
        export_path = self._current_export(request_path)
        if export_path is not None:
            self._send_file(export_path, include_body=True)
            return
        score_path = self._current_score_asset(request_path)
        if score_path is not None:
            self._send_file(score_path, include_body=True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        if not self._require_local_host():
            return
        parsed = urlsplit(self.path)
        request_path = unquote(parsed.path)
        if self._get_api(
            request_path,
            parse_qs(parsed.query),
            include_body=False,
        ):
            return
        asset = self.server.asset_path(request_path)
        if asset is not None:
            self._send_file(asset, include_body=False)
            return
        export_path = self._current_export(request_path)
        if export_path is not None:
            self._send_file(export_path, include_body=False)
            return
        score_path = self._current_score_asset(request_path)
        if score_path is not None:
            self._send_file(score_path, include_body=False)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
        if not self._origin_is_local():
            if request_path.startswith("/api/v1/"):
                self._send_api_error(
                    "API actions require the local origin",
                    code=ErrorCode.INVALID_REQUEST,
                    status=HTTPStatus.FORBIDDEN,
                )
            else:
                self._send_json(
                    {"error": "corrected workbench actions require the local origin"},
                    HTTPStatus.FORBIDDEN,
                )
            return
        score_match = re.fullmatch(
            (
                r"/api/v1/workspaces/([^/]+)/sessions/([^/]+)"
                r"/score-jobs"
            ),
            request_path,
        )
        if score_match:
            workspace_id, session_id = score_match.groups()
            try:
                request = ScoreJobStart.model_validate(
                    self._read_api_json()
                )
                if (
                    workspace_id != LOCAL_WORKSPACE_ID
                    or request.workspace_id != workspace_id
                    or request.session_id != session_id
                ):
                    raise ValueError("score request target does not match its path")
                target = self.server.session_store.get_session(session_id)
                if (
                    request.transcription_run_id
                    != target.current_transcription_run_id
                ):
                    raise ValueError(
                        "score request transcription run is not current"
                    )
                job = self.server.start_score(
                    session_id,
                    expected_commit_sample=request.commit_sample,
                )
            except ValidationError as error:
                self._send_api_error(
                    str(error),
                    code=ErrorCode.INVALID_REQUEST,
                    status=HTTPStatus.BAD_REQUEST,
                    workspace_id=workspace_id,
                    session_id=session_id,
                )
                return
            except LocalSessionNotFoundError as error:
                self._send_api_error(
                    str(error),
                    code=ErrorCode.NOT_FOUND,
                    status=HTTPStatus.NOT_FOUND,
                    workspace_id=workspace_id,
                    session_id=session_id,
                )
                return
            except (OSError, RuntimeError, ValueError) as error:
                self._send_api_error(
                    str(error),
                    code=ErrorCode.SCORE_BUSY
                    if "already running" in str(error)
                    else ErrorCode.CONFLICT,
                    status=HTTPStatus.CONFLICT,
                    workspace_id=workspace_id,
                    session_id=session_id,
                )
                return
            self._send_json(job.model_dump(mode="json"), HTTPStatus.ACCEPTED)
            return
        if request_path == "/api/replay":
            try:
                self.server.start_replay()
            except (OSError, RuntimeError, ValueError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.CONFLICT)
                return
            self._send_json(self.server.public_state(), HTTPStatus.ACCEPTED)
            return
        if request_path == "/api/score":
            try:
                self.server.start_score()
            except (OSError, RuntimeError, ValueError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.CONFLICT)
                return
            self._send_json(
                self.server.public_score_state(),
                HTTPStatus.ACCEPTED,
            )
            return
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

    def do_DELETE(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
        match = re.fullmatch(
            r"/api/v1/workspaces/([^/]+)/sessions/([^/]+)",
            request_path,
        )
        if not match:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        workspace_id, session_id = match.groups()
        if not self._origin_is_local():
            self._send_api_error(
                "API actions require the local origin",
                code=ErrorCode.INVALID_REQUEST,
                status=HTTPStatus.FORBIDDEN,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            return
        try:
            request = DeleteSessionRequest.model_validate(
                self._read_api_json()
            )
            if (
                workspace_id != LOCAL_WORKSPACE_ID
                or request.workspace_id != workspace_id
                or request.session_id != session_id
            ):
                raise ValueError("delete request target does not match its path")
            result = self.server.delete_api_session(session_id)
        except ValidationError as error:
            self._send_api_error(
                str(error),
                code=ErrorCode.INVALID_REQUEST,
                status=HTTPStatus.BAD_REQUEST,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            return
        except LocalSessionNotFoundError as error:
            self._send_api_error(
                str(error),
                code=ErrorCode.NOT_FOUND,
                status=HTTPStatus.NOT_FOUND,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            return
        except LocalSessionConflictError as error:
            self._send_api_error(
                str(error),
                code=ErrorCode.SESSION_ACTIVE
                if "active session" in str(error)
                else ErrorCode.JOB_ACTIVE,
                status=HTTPStatus.CONFLICT,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            return
        except (OSError, ValueError) as error:
            self._send_api_error(
                str(error),
                code=ErrorCode.INVALID_REQUEST,
                status=HTTPStatus.BAD_REQUEST,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            return
        self._send_json(result)

    def _get_events(self, query: dict[str, list[str]]) -> None:
        state = self.server.public_state()
        session = state.get("session")
        directory = self.server.current_directory()
        if not isinstance(session, dict) or directory is None:
            self._send_json({"error": "no corrected session is available"}, HTTPStatus.NOT_FOUND)
            return
        try:
            start_sample = int(query.get("start_sample", ["0"])[0])
            end_sample = int(query.get("end_sample", ["0"])[0])
            after = int(query.get("after", ["0"])[0])
            limit = int(query.get("limit", ["1024"])[0])
            include_history_value = query.get("include_history", ["1"])[0]
            if include_history_value not in {"0", "1"}:
                raise ValueError("include_history must be 0 or 1")
            include_history = include_history_value == "1"
            sample_rate_hz = int(session["sample_rate_hz"])
            if end_sample - start_sample > round(MAX_VISIBLE_RANGE_S * sample_rate_hz):
                raise ValueError("visible event range exceeds the configured bound")
            database_path = directory / "event-index.sqlite3"
            visible = query_materialized_index(
                database_path,
                start_sample=start_sample,
                end_sample=end_sample,
            )
            history = (
                query_history_index(
                    database_path,
                    after_sequence=after,
                    limit=limit,
                )
                if include_history
                else []
            )
        except (FileNotFoundError, sqlite3.Error, TypeError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        cursor = after
        if history:
            cursor = max(int(event["sequence"]) for event in history)
        self._send_json(
            {
                "schema_version": CORRECTED_STREAM_SCHEMA,
                "session_id": session["session_id"],
                "range": {
                    "start_sample": start_sample,
                    "end_sample": end_sample,
                },
                "materialized": visible,
                "history": history,
                "next_sequence": cursor,
                "history_truncated": len(history) == min(limit, MAX_QUERY_LIMIT),
            }
        )

    def _send_websocket_json(self, value: dict[str, Any]) -> None:
        self.connection.sendall(encode_json(value))

    def _send_websocket_close(self, code: int = 1000, reason: str = "") -> None:
        payload = code.to_bytes(2, "big") + reason.encode("utf-8")[:120]
        self.connection.sendall(encode_frame(payload, opcode=0x8))

    def _upgrade_websocket(self) -> bool:
        if not self._origin_is_local():
            self._send_json(
                {"error": "microphone capture requires the local origin"},
                HTTPStatus.FORBIDDEN,
            )
            return False
        if (
            self.headers.get("Upgrade", "").lower() != "websocket"
            or "upgrade" not in self.headers.get("Connection", "").lower()
            or self.headers.get("Sec-WebSocket-Version") != "13"
        ):
            self._send_json(
                {"error": "microphone capture requires a WebSocket upgrade"},
                HTTPStatus.UPGRADE_REQUIRED,
            )
            return False
        try:
            accept = websocket_accept(self.headers.get("Sec-WebSocket-Key", ""))
        except ValueError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return False
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.close_connection = True
        return True

    def _handle_live_websocket(self) -> None:
        if not self._upgrade_websocket():
            return
        session: CorrectedSession | None = None
        stopped = False
        try:
            while True:
                frame = read_frame(self.rfile)
                if frame is None or frame.opcode == 0x8:
                    break
                if frame.opcode == 0x9:
                    self.connection.sendall(encode_frame(frame.payload, opcode=0xA))
                    continue
                if frame.opcode == 0x2:
                    if session is None:
                        raise ValueError("microphone PCM arrived before Start")
                    block = parse_pcm_block(frame.payload)
                    events = session.accept_block(
                        block,
                        received_ns=time.perf_counter_ns(),
                    )
                    self.server.record_delivery(events)
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "block_ack",
                            "sequence": block.sequence,
                            "received_source_frames": session.horizons.audio_head_sample,
                            "events": events,
                            "horizons": session.horizons.document(
                                sample_rate_hz=session.sample_rate_hz
                            ),
                        }
                    )
                    continue
                if frame.opcode != 0x1:
                    raise ValueError("unsupported microphone WebSocket message")
                try:
                    message = json.loads(frame.payload)
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    raise ValueError("microphone control message is invalid JSON") from error
                if not isinstance(message, dict):
                    raise ValueError("microphone control message must be an object")
                if message.get("schema_version") != CORRECTED_STREAM_SCHEMA:
                    raise ValueError("microphone control schema is unsupported")
                message_type = message.get("type")
                if message_type == "start":
                    if session is not None:
                        raise ValueError("microphone session already started")
                    sample_rate_hz = message.get("sample_rate_hz")
                    metadata = message.get("client_metadata")
                    if (
                        not isinstance(sample_rate_hz, int)
                        or isinstance(sample_rate_hz, bool)
                        or not 8_000 <= sample_rate_hz <= 192_000
                        or not isinstance(metadata, dict)
                    ):
                        raise ValueError("microphone Start metadata is invalid")
                    encoded_metadata = json.dumps(metadata, allow_nan=False).encode()
                    if len(encoded_metadata) > MAX_CLIENT_METADATA_BYTES:
                        raise ValueError("microphone client metadata is too large")
                    session_id, directory = self.server.claim_session(source="microphone")
                    preview_model, commit_model = self.server.get_models()
                    session = CorrectedSession(
                        directory,
                        session_id=session_id,
                        sample_rate_hz=sample_rate_hz,
                        source="microphone",
                        minimum_free_bytes=self.server.minimum_free_bytes,
                    )
                    session.add_lane(CorrectedPreviewLane(session, model=preview_model))
                    session.add_lane(CorrectedCommitLane(session, model=commit_model))
                    write_json(
                        directory / "client.json",
                        {
                            "schema_version": "atpiano.corrected-client.v1",
                            "received_at": utc_now(),
                            "metadata": metadata,
                        },
                    )
                    self.server.set_active(session)
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "ready",
                            "session_id": session_id,
                            "sample_rate_hz": sample_rate_hz,
                            "lanes": [lane.status() for lane in session.lanes],
                        }
                    )
                elif message_type == "stop":
                    if session is None:
                        raise ValueError("microphone Stop arrived before Start")
                    frame_count = message.get("frame_count")
                    block_count = message.get("block_count")
                    if (
                        not isinstance(frame_count, int)
                        or isinstance(frame_count, bool)
                        or not isinstance(block_count, int)
                        or isinstance(block_count, bool)
                        or frame_count != session.horizons.audio_head_sample
                        or block_count != session.next_sequence
                    ):
                        raise ValueError("microphone Stop counts do not match accepted PCM")
                    self.server.begin_stop()
                    manifest = session.finalize()
                    exports = write_corrected_exports(session.directory)
                    stopped = True
                    self.server.complete_session()
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "stopped",
                            "session": manifest,
                            "exports": exports,
                        }
                    )
                    self._send_websocket_close()
                    return
                else:
                    raise ValueError(f"unsupported microphone control type: {message_type}")
        except (ConnectionError, OSError, RuntimeError, ValueError) as error:
            if session is not None and not session.closed:
                session.abort(error)
            self.server.fail_session(error)
            try:
                self._send_websocket_json(
                    {
                        "schema_version": CORRECTED_STREAM_SCHEMA,
                        "type": "error",
                        "error": str(error),
                    }
                )
                self._send_websocket_close(1008, str(error))
            except OSError:
                pass
        finally:
            if session is not None and not stopped and not session.closed:
                error = RuntimeError("microphone WebSocket closed before Stop")
                session.abort(error)
                self.server.fail_session(error)


def create_corrected_workbench_server(
    workspace_directory: Path,
    *,
    port: int = 8001,
    preview_model_factory: PreviewModelFactory = _default_preview_model,
    commit_model_factory: CommitModelFactory | None = None,
    commit_device: str = "cpu",
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    score_runtime: Path = Path("results/midi2score-runtime"),
    score_runner: ScoreRunner | None = None,
    web_root: Path = WEB_ROOT,
    application_mode: str = "corrected-workbench-v2",
) -> CorrectedWorkbenchServer:
    factory = commit_model_factory or (lambda: _default_commit_model(device=commit_device))
    return CorrectedWorkbenchServer(
        workspace_directory,
        port=port,
        preview_model_factory=preview_model_factory,
        commit_model_factory=factory,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        score_runtime=score_runtime,
        score_runner=score_runner,
        web_root=web_root,
        application_mode=application_mode,
    )


def serve_corrected_workbench(
    workspace_directory: Path,
    *,
    port: int = 8001,
    open_browser: bool = True,
    commit_device: str = "cpu",
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    score_runtime: Path = Path("results/midi2score-runtime"),
    web_root: Path = WEB_ROOT,
    application_mode: str = "corrected-workbench-v2",
    application_label: str = "Corrected-note workspace",
) -> None:
    server = create_corrected_workbench_server(
        workspace_directory,
        port=port,
        commit_device=commit_device,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        score_runtime=score_runtime,
        web_root=web_root,
        application_mode=application_mode,
    )
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"{application_label}: {server.workspace_directory}")
    print(url)
    if open_browser:
        webbrowser.open(url)
    if replay_manifest is not None:
        server.start_replay()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def serve_shared_application(
    workspace_directory: Path,
    *,
    port: int = 8002,
    open_browser: bool = True,
    commit_device: str = "cpu",
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    score_runtime: Path = Path("results/midi2score-runtime"),
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    app_root = repository_root / "app"
    subprocess.run(
        ["npm", "run", "build", "--prefix", str(app_root)],
        cwd=repository_root,
        check=True,
    )
    serve_corrected_workbench(
        workspace_directory,
        port=port,
        open_browser=open_browser,
        commit_device=commit_device,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        score_runtime=score_runtime,
        web_root=app_root / "dist",
        application_mode="shared-react-v3",
        application_label="Atpiano performance workspace",
    )
