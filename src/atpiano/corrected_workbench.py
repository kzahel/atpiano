"""Loopback-only web application for bounded corrected-note sessions."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
import webbrowser
from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from pydantic import ValidationError

from atpiano.adapters.local_models import LocalModelPool
from atpiano.adapters.local_replay import LocalReplaySource
from atpiano.adapters.local_scores import LocalScoreExecutor
from atpiano.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalSessionConflictError,
    LocalSessionNotFoundError,
    LocalSessionStore,
)
from atpiano.application import (
    ApplicationNotFoundError,
    ApplicationServices,
    CaptureApplicationService,
    ScoreApplicationService,
    SessionApplicationService,
)
from atpiano.backend_profile import (
    BackendSchedulerIdentity,
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
    RuntimeCapabilities,
    RuntimeMode,
    ScoreJobStart,
    ScoreVariant,
    ScoreVariantRequest,
    SourceKind,
)
from atpiano.corrected import CorrectedSession
from atpiano.corrected_commit import (
    CommitModel,
)
from atpiano.corrected_export import (
    MAX_QUERY_LIMIT,
    query_history_index,
    query_materialized_index,
    write_corrected_exports,
)
from atpiano.corrected_pipeline import CorrectedSessionPipeline
from atpiano.live import LiveWindowModel, parse_pcm_block
from atpiano.score_snapshot import (
    ScoreRunner,
    ScoreVariantRunner,
    score_snapshot_is_plausible,
)
from atpiano.util import read_json
from atpiano.websocket import encode_frame, encode_json, read_frame, websocket_accept

CORRECTED_WORKBENCH_SCHEMA = "atpiano.corrected-workbench.v1"
CORRECTED_STREAM_SCHEMA = "atpiano.corrected-stream.v1"
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


def _default_commit_model(
    *,
    device: str,
    thread_limit: int | None = None,
) -> CommitModel:
    from atpiano.corrected_commit import TranskunCommitModel

    return TranskunCommitModel(
        device=device,
        thread_limit=thread_limit,
    )


class CorrectedWorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        workspace_directory: Path,
        *,
        bind: str = "127.0.0.1",
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
        score_variant_runner: ScoreVariantRunner | None = None,
        web_root: Path = WEB_ROOT,
        application_mode: str = "corrected-workbench-v2",
        isolate_models: bool = True,
        commit_threads: int | None = 2,
        correction_mode: str = "auto",
        backend_profile_path: Path | None = None,
        public_origin: str | None = None,
    ) -> None:
        if minimum_free_bytes < 0:
            raise ValueError("minimum free bytes cannot be negative")
        if replay_repeat <= 0:
            raise ValueError("replay repetition count must be positive")
        if replay_silence_s < 0:
            raise ValueError("replay silence cannot be negative")
        if commit_threads is not None and commit_threads <= 0:
            raise ValueError("commit worker thread limit must be positive")
        if correction_mode not in {
            "live",
            "delayed",
            "after-stop",
            "unavailable",
            "auto",
        }:
            raise ValueError("local correction mode is invalid")
        if public_origin is not None:
            parsed_public_origin = urlsplit(public_origin)
            if (
                parsed_public_origin.scheme != "https"
                or not parsed_public_origin.netloc
                or parsed_public_origin.path
                or parsed_public_origin.query
                or parsed_public_origin.fragment
                or public_origin
                != (
                    f"{parsed_public_origin.scheme}://"
                    f"{parsed_public_origin.netloc}"
                )
            ):
                raise ValueError(
                    "public origin must be an HTTPS origin without a path"
                )
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        self.session_store = LocalSessionStore(self.workspace_directory)
        self.preview_model_factory = preview_model_factory
        self.commit_model_factory = commit_model_factory
        self.minimum_free_bytes = minimum_free_bytes
        score_executor = LocalScoreExecutor(
            score_runtime.resolve(),
            score_runner=score_runner,
            score_variant_runner=score_variant_runner,
        )
        self.web_root = web_root.resolve()
        self.application_mode = application_mode
        self.isolate_models = isolate_models
        self.commit_threads = commit_threads
        self.correction_mode = correction_mode
        self.public_origin = public_origin
        self.backend_profile_path = (
            backend_profile_path.resolve()
            if backend_profile_path is not None
            else None
        )
        model_pool = LocalModelPool(
            preview_model_factory=preview_model_factory,
            commit_model_factory=commit_model_factory,
            isolate_models=isolate_models,
            commit_threads=commit_threads,
            correction_mode=correction_mode,
            backend_profile_path=backend_profile_path,
        )
        replay_source = (
            LocalReplaySource(
                replay_manifest,
                repeat=replay_repeat,
                silence_s=replay_silence_s,
                realtime=replay_realtime,
            )
            if replay_manifest is not None
            else None
        )
        sessions = SessionApplicationService(
            self.session_store,
            workspace_id=LOCAL_WORKSPACE_ID,
        )
        capture = CaptureApplicationService(
            self.session_store,
            model_pool,
            minimum_free_bytes=minimum_free_bytes,
            free_bytes=lambda: shutil.disk_usage(
                self.workspace_directory
            ).free,
            finalizer=self._finalize_microphone_session,
            replay_source=replay_source,
        )
        scores = ScoreApplicationService(
            self.session_store,
            score_executor,
            workspace_id=LOCAL_WORKSPACE_ID,
            current_session_id=capture.current_session_id,
        )
        self.application = ApplicationServices(
            capture=capture,
            sessions=sessions,
            scores=scores,
        )
        super().__init__((bind, port), CorrectedWorkbenchHandler)

    def asset_path(self, request_path: str) -> Path | None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (self.web_root / relative).resolve()
        if self.web_root != candidate and self.web_root not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None

    def get_preview_model(self) -> LiveWindowModel:
        return self.application.capture.preview_model()

    def get_commit_model(self) -> CommitModel:
        return self.application.capture.commit_model()

    def get_models(self) -> tuple[LiveWindowModel, CommitModel]:
        return self.application.capture.models()

    def model_worker_status(self) -> list[dict[str, Any]]:
        return self.application.capture.worker_status()

    @staticmethod
    def correction_scheduler_identity() -> BackendSchedulerIdentity:
        return (
            CaptureApplicationService.correction_scheduler_identity()
        )

    def resolve_correction_mode(
        self,
        commit_model: CommitModel,
    ) -> tuple[str, str, str | None]:
        return self.application.capture.resolve_correction_mode(
            commit_model
        )

    def server_close(self) -> None:
        self.application.capture.close()
        super().server_close()

    def claim_session(self, *, source: str) -> tuple[str, Path]:
        return self.application.capture.claim_session(source=source)

    def set_active(
        self,
        session: CorrectedSession,
        pipeline: CorrectedSessionPipeline | None = None,
    ) -> None:
        self.application.capture.set_active(session, pipeline)

    def record_delivery(self, events: list[dict[str, Any]]) -> None:
        self.application.capture.observe_delivery(events)

    def complete_session(self) -> None:
        self.application.capture.complete_session()

    def fail_session(self, error: Exception) -> None:
        self.application.capture.fail_session(error)

    def begin_stop(self) -> None:
        self.application.capture.begin_stop()

    def current_directory(self) -> Path | None:
        return self.application.capture.current_directory()

    def active_session_id(self) -> str | None:
        return self.application.capture.active_session_id()

    def current_session_id(self) -> str | None:
        return self.application.capture.current_session_id()

    def public_state(self) -> dict[str, Any]:
        return self.application.capture.state()

    def _finalize_microphone_session(
        self,
        session: CorrectedSession,
    ) -> None:
        write_corrected_exports(
            session.directory,
            allow_settling=True,
        )

    def _runtime_state(self) -> dict[str, Any]:
        return self.application.scores.runtime_state()

    def public_score_state(
        self,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        return self.application.scores.state(session_id)

    def start_score(
        self,
        session_id: str | None = None,
        *,
        expected_commit_sample: int | None = None,
    ) -> Job:
        return self.application.scores.start(
            session_id,
            expected_commit_sample=expected_commit_sample,
        )

    def score_job(self, job_id: str) -> Job:
        return self.application.scores.job(job_id)

    def create_score_variant(
        self,
        request: ScoreVariantRequest,
    ) -> ScoreVariant:
        return self.application.scores.create_variant(request)

    def delete_api_session(self, session_id: str) -> dict[str, Any]:
        result = self.application.sessions.delete_session(
            LOCAL_WORKSPACE_ID,
            session_id,
            active_session_id=self.active_session_id(),
            running_score_session_id=(
                self.application.scores.running_session_id()
            ),
        )
        self.application.capture.session_deleted(session_id)
        return result.model_dump(mode="json")

    def start_replay(self) -> None:
        self.application.capture.start_replay()


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

    def _host_is_trusted(self) -> bool:
        port = self.server.server_address[1]
        trusted_hosts = {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
        }
        if self.server.public_origin is not None:
            trusted_hosts.add(urlsplit(self.server.public_origin).netloc)
        return self.headers.get("Host", "") in trusted_hosts

    def _origin_is_trusted(self) -> bool:
        port = self.server.server_address[1]
        trusted_origins = {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }
        if self.server.public_origin is not None:
            trusted_origins.add(self.server.public_origin)
        return self.headers.get("Origin") in trusted_origins

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
        if self._host_is_trusted():
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
        start = 0
        end = max(0, size - 1)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if match is None or size == 0:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            first, last = match.groups()
            if not first:
                suffix_length = int(last)
                start = max(0, size - suffix_length)
            else:
                start = int(first)
            if last and first:
                end = min(end, int(last))
            if start >= size or end < start:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            status = HTTPStatus.PARTIAL_CONTENT
        content_length = end - start + 1
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not include_body:
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = content_length
            while remaining and (block := handle.read(min(64 * 1024, remaining))):
                if not self._write_body(block):
                    return
                remaining -= len(block)

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
                page = self.server.application.sessions.list_workspaces()
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
                page = self.server.application.sessions.list_sessions(
                    workspace_id,
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
                page = self.server.application.sessions.get_events(
                    workspace_id,
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
                horizon = self.server.application.sessions.get_horizon(
                    workspace_id,
                    session_id,
                )
                self._send_json(horizon.model_dump(mode="json"))
                return True
            artifacts_match = re.fullmatch(
                f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)/artifacts",
                request_path,
            )
            if artifacts_match:
                workspace_id, session_id = artifacts_match.groups()
                page = self.server.application.sessions.list_artifacts(
                    workspace_id,
                    session_id,
                    cursor=query.get("cursor", [None])[0],
                    limit=self._api_query_limit(query),
                )
                self._send_json(page.model_dump(mode="json"))
                return True
            variants_match = re.fullmatch(
                (
                    f"{prefix}/workspaces/([^/]+)/sessions/([^/]+)"
                    r"/score-variants"
                ),
                request_path,
            )
            if variants_match:
                workspace_id, session_id = variants_match.groups()
                page = (
                    self.server.application.sessions.list_score_variants(
                        workspace_id,
                        session_id,
                    )
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
                artifact, path = self.server.application.sessions.get_artifact(
                    workspace_id,
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
                session = self.server.application.sessions.get_session(
                    workspace_id,
                    session_id,
                    active_session_id=self.server.active_session_id(),
                )
                self._send_json(session.model_dump(mode="json"))
                return True
        except (
            ApplicationNotFoundError,
            LocalSessionNotFoundError,
        ) as error:
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
                    "replay": (
                        self.server.application.capture.replay_configuration()
                    ),
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
        if not self._origin_is_trusted():
            if request_path.startswith("/api/v1/"):
                self._send_api_error(
                    "API actions require a trusted origin",
                    code=ErrorCode.INVALID_REQUEST,
                    status=HTTPStatus.FORBIDDEN,
                )
            else:
                self._send_json(
                    {"error": "corrected workbench actions require a trusted origin"},
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
                target = self.server.application.sessions.get_session(
                    workspace_id,
                    session_id,
                )
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
        variant_match = re.fullmatch(
            (
                r"/api/v1/workspaces/([^/]+)/sessions/([^/]+)"
                r"/score-variants"
            ),
            request_path,
        )
        if variant_match:
            workspace_id, session_id = variant_match.groups()
            try:
                request = ScoreVariantRequest.model_validate(
                    self._read_api_json()
                )
                if (
                    workspace_id != LOCAL_WORKSPACE_ID
                    or request.workspace_id != workspace_id
                    or request.session_id != session_id
                ):
                    raise ValueError(
                        "score variant request target does not match its path"
                    )
                variant = self.server.create_score_variant(request)
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
                    code=(
                        ErrorCode.SCORE_BUSY
                        if "already running" in str(error)
                        else ErrorCode.CONFLICT
                    ),
                    status=HTTPStatus.CONFLICT,
                    workspace_id=workspace_id,
                    session_id=session_id,
                )
                return
            self._send_json(
                variant.model_dump(mode="json"),
                HTTPStatus.CREATED,
            )
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
        if not self._origin_is_trusted():
            self._send_api_error(
                "API actions require a trusted origin",
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
        if not self._origin_is_trusted():
            self._send_json(
                {"error": "microphone capture requires a trusted origin"},
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
                    session = (
                        self.server.application.capture.accept_block(
                        block,
                        received_ns=time.perf_counter_ns(),
                    )
                    )
                    events: list[dict[str, Any]] = []
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
                    started = (
                        self.server.application.capture.start_microphone(
                        sample_rate_hz=sample_rate_hz,
                        client_metadata=metadata,
                    )
                    )
                    session = started.session
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "ready",
                            "session_id": session.session_id,
                            "sample_rate_hz": sample_rate_hz,
                            "lanes": [lane.status() for lane in session.lanes],
                            "correction": {
                                "mode": started.correction_mode,
                                "reason": started.correction_reason,
                                "profile_id": (
                                    started.correction_profile_id
                                ),
                            },
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
                    ):
                        raise ValueError("microphone Stop counts are invalid")
                    transport = message.get("transport")
                    if transport is not None and not isinstance(
                        transport,
                        dict,
                    ):
                        raise ValueError(
                            "microphone transport evidence must be an object"
                        )
                    manifest = (
                        self.server.application.capture.stop_microphone(
                            frame_count=frame_count,
                            block_count=block_count,
                            transport=transport,
                        )
                    )
                    stopped = True
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "stopped",
                            "session": manifest,
                            "exports": {},
                            "settling": True,
                        }
                    )
                    self._send_websocket_close()
                    return
                else:
                    raise ValueError(f"unsupported microphone control type: {message_type}")
        except (ConnectionError, OSError, RuntimeError, ValueError) as error:
            self.server.application.capture.abort_microphone(error)
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
                self.server.application.capture.abort_microphone(error)


def create_corrected_workbench_server(
    workspace_directory: Path,
    *,
    bind: str = "127.0.0.1",
    port: int = 8001,
    preview_model_factory: PreviewModelFactory = _default_preview_model,
    commit_model_factory: CommitModelFactory | None = None,
    commit_device: str = "cpu",
    commit_threads: int | None = 2,
    isolate_models: bool = True,
    correction_mode: str = "auto",
    backend_profile_path: Path | None = None,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    score_runtime: Path = Path("results/midi2score-runtime"),
    score_runner: ScoreRunner | None = None,
    score_variant_runner: ScoreVariantRunner | None = None,
    web_root: Path = WEB_ROOT,
    application_mode: str = "corrected-workbench-v2",
    public_origin: str | None = None,
) -> CorrectedWorkbenchServer:
    factory = commit_model_factory or partial(
        _default_commit_model,
        device=commit_device,
        thread_limit=commit_threads,
    )
    return CorrectedWorkbenchServer(
        workspace_directory,
        bind=bind,
        port=port,
        preview_model_factory=preview_model_factory,
        commit_model_factory=factory,
        commit_threads=commit_threads,
        isolate_models=isolate_models,
        correction_mode=correction_mode,
        backend_profile_path=backend_profile_path,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        score_runtime=score_runtime,
        score_runner=score_runner,
        score_variant_runner=score_variant_runner,
        web_root=web_root,
        application_mode=application_mode,
        public_origin=public_origin,
    )


def serve_corrected_workbench(
    workspace_directory: Path,
    *,
    bind: str = "127.0.0.1",
    port: int = 8001,
    open_browser: bool = True,
    commit_device: str = "cpu",
    commit_threads: int | None = 2,
    correction_mode: str = "auto",
    backend_profile_path: Path | None = None,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    score_runtime: Path = Path("results/midi2score-runtime"),
    web_root: Path = WEB_ROOT,
    application_mode: str = "corrected-workbench-v2",
    application_label: str = "Corrected-note workspace",
    public_origin: str | None = None,
) -> None:
    server = create_corrected_workbench_server(
        workspace_directory,
        bind=bind,
        port=port,
        commit_device=commit_device,
        commit_threads=commit_threads,
        correction_mode=correction_mode,
        backend_profile_path=backend_profile_path,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        score_runtime=score_runtime,
        web_root=web_root,
        application_mode=application_mode,
        public_origin=public_origin,
    )
    actual_port = server.server_address[1]
    local_host = "127.0.0.1" if bind in {"", "0.0.0.0"} else bind
    url = f"http://{local_host}:{actual_port}/"
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
    bind: str = "127.0.0.1",
    port: int = 8002,
    open_browser: bool = True,
    commit_device: str = "cpu",
    commit_threads: int | None = 2,
    correction_mode: str = "auto",
    backend_profile_path: Path | None = None,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    score_runtime: Path = Path("results/midi2score-runtime"),
    public_origin: str | None = None,
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
        bind=bind,
        port=port,
        open_browser=open_browser,
        commit_device=commit_device,
        commit_threads=commit_threads,
        correction_mode=correction_mode,
        backend_profile_path=backend_profile_path,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        score_runtime=score_runtime,
        web_root=app_root / "dist",
        application_mode="shared-react-v3",
        application_label="Atpiano performance workspace",
        public_origin=public_origin,
    )
