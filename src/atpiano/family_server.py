"""Authenticated FastAPI composition for home-hosted family sharing."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import subprocess
import time
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.websockets import WebSocketDisconnect, WebSocketState

from atpiano.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalSessionConflictError,
    LocalSessionNotFoundError,
)
from atpiano.adapters.passwords import Argon2PasswordHasher
from atpiano.adapters.sqlite_identity import SqlAlchemyIdentityRepository
from atpiano.application.errors import (
    ApplicationConflictError,
    ApplicationNotFoundError,
    AuthenticationError,
    AuthorizationError,
)
from atpiano.application.identity import (
    IdentityApplicationService,
    Principal,
)
from atpiano.contracts.schemas import (
    CONTRACT_SCHEMA_VERSION,
    PCM_PROTOCOL_VERSION,
    ArtifactAccess,
    ArtifactKind,
    ArtifactPage,
    AtpianoError,
    AuthenticatedPrincipal,
    AuthSession,
    DeleteSessionRequest,
    ErrorCode,
    ErrorResponse,
    LoginRequest,
    LogoutResult,
    Membership,
    RuntimeCapabilities,
    RuntimeMode,
    ScoreJobStart,
    ScoreVariantPage,
    ScoreVariantRequest,
    SessionAnnotationPatch,
    SourceKind,
)
from atpiano.corrected import CorrectedSession
from atpiano.corrected_export import MAX_QUERY_LIMIT
from atpiano.corrected_workbench import (
    CORRECTED_STREAM_SCHEMA,
    MAX_CLIENT_METADATA_BYTES,
    MAX_VISIBLE_RANGE_S,
    CorrectedWorkbenchRuntime,
    create_corrected_workbench_runtime,
)
from atpiano.live import parse_pcm_block
from atpiano.persistence import initialize_catalog

SECURE_SESSION_COOKIE = "__Host-atpiano_session"
LOCAL_SESSION_COOKIE = "atpiano_session"
MAX_API_BODY_BYTES = 64 * 1024
WEBSOCKET_REAUTHENTICATION_SECONDS = 60.0
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 5 * 60.0
MAX_LOGIN_ATTEMPT_BUCKETS = 1024
PRIVATE_SCORE_ARTIFACT_KINDS = {
    ArtifactKind.MUSICXML,
    ArtifactKind.SCORE_INPUT_MIDI,
    ArtifactKind.SCORE_ALIGNMENT,
}


class LoginRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("too many login attempts; try again later")
        self.retry_after_seconds = retry_after_seconds


@dataclass
class _LoginAttempts:
    count: int
    first_attempt: float


class LoginAttemptLimiter:
    """Bounded in-process limiter keyed without retaining usernames."""

    def __init__(self) -> None:
        self._attempts: dict[bytes, _LoginAttempts] = {}
        self._lock = Lock()

    @staticmethod
    def _key(client: str, username: str) -> bytes:
        return hashlib.sha256(
            f"{client}\0{username.casefold()}".encode()
        ).digest()

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, value in self._attempts.items()
            if now - value.first_attempt >= LOGIN_ATTEMPT_WINDOW_SECONDS
        ]
        for key in expired:
            del self._attempts[key]
        while len(self._attempts) >= MAX_LOGIN_ATTEMPT_BUCKETS:
            oldest = min(
                self._attempts,
                key=lambda key: self._attempts[key].first_attempt,
            )
            del self._attempts[oldest]

    def check(self, client: str, username: str) -> None:
        now = time.monotonic()
        key = self._key(client, username)
        with self._lock:
            self._prune(now)
            value = self._attempts.get(key)
            if value is None or value.count < LOGIN_ATTEMPT_LIMIT:
                return
            remaining = LOGIN_ATTEMPT_WINDOW_SECONDS - (
                now - value.first_attempt
            )
            raise LoginRateLimitError(max(1, round(remaining)))

    def failure(self, client: str, username: str) -> None:
        now = time.monotonic()
        key = self._key(client, username)
        with self._lock:
            self._prune(now)
            value = self._attempts.get(key)
            if value is None:
                self._attempts[key] = _LoginAttempts(
                    count=1,
                    first_attempt=now,
                )
            else:
                value.count += 1

    def success(self, client: str, username: str) -> None:
        key = self._key(client, username)
        with self._lock:
            self._attempts.pop(key, None)


def _principal_contract(principal: Principal) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=principal.user_id,
        username=principal.username,
        display_name=principal.display_name,
        memberships=tuple(
            Membership(
                workspace_id=membership.workspace_id,
                user_id=principal.user_id,
                role=membership.role,
                created_at=membership.created_at,
            )
            for membership in principal.memberships
        ),
    )


def _auth_session(principal: Principal) -> AuthSession:
    return AuthSession(principal=_principal_contract(principal))


def _error_response(
    message: str,
    *,
    status_code: int,
    code: ErrorCode,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error = ErrorResponse(
        error=AtpianoError(
            error_id=f"error:{uuid.uuid4().hex[:16]}",
            code=code,
            message=message,
            retryable=False,
        )
    )
    response_headers = {"Cache-Control": "no-store"}
    response_headers.update(headers or {})
    return JSONResponse(
        error.model_dump(mode="json"),
        status_code=status_code,
        headers=response_headers,
    )


def create_family_application(
    runtime: CorrectedWorkbenchRuntime,
    identity: IdentityApplicationService,
    *,
    public_origin: str,
    secure_cookie: bool = True,
    public_score_available: bool | None = None,
) -> FastAPI:
    """Create one authenticated ASGI adapter over the shared local runtime."""

    parsed_origin = urlsplit(public_origin)
    if (
        parsed_origin.scheme not in ({"https"} if secure_cookie else {"http", "https"})
        or parsed_origin.hostname is None
        or parsed_origin.path
        or parsed_origin.query
        or parsed_origin.fragment
        or public_origin
        != f"{parsed_origin.scheme}://{parsed_origin.netloc}"
    ):
        raise ValueError("public origin is not a valid exact origin")
    identity.require_enabled_owner()
    runtime_score_available = bool(
        runtime.application.scores.runtime_state().get("available")
    )
    score_available = (
        runtime_score_available
        if public_score_available is None
        else public_score_available and runtime_score_available
    )
    login_limiter = LoginAttemptLimiter()
    cookie_name = (
        SECURE_SESSION_COOKIE if secure_cookie else LOCAL_SESSION_COOKIE
    )
    app = FastAPI(
        title="atpiano family server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            parsed_origin.hostname,
            "127.0.0.1",
            "localhost",
        ],
    )

    @app.middleware("http")
    async def security_boundary(
        request: Request,
        call_next: Any,
    ) -> Response:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            provided_origin = request.headers.get("origin", "")
            if not hmac.compare_digest(provided_origin, public_origin):
                return _error_response(
                    "request origin is not trusted",
                    status_code=403,
                    code=ErrorCode.INVALID_REQUEST,
                )
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    length = int(content_length)
                except ValueError:
                    length = MAX_API_BODY_BYTES + 1
                if length < 0 or length > MAX_API_BODY_BYTES:
                    return _error_response(
                        "request body is too large",
                        status_code=413,
                        code=ErrorCode.INVALID_REQUEST,
                    )
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(AuthenticationError)
    async def authentication_error(
        request: Request,
        _error: AuthenticationError,
    ) -> JSONResponse:
        return _error_response(
            (
                "username or password is incorrect"
                if request.url.path == "/api/v1/auth/login"
                else "authentication is required"
            ),
            status_code=401,
            code=ErrorCode.INVALID_REQUEST,
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error(
        _request: Request,
        error: AuthorizationError,
    ) -> JSONResponse:
        return _error_response(
            str(error),
            status_code=403,
            code=ErrorCode.INVALID_REQUEST,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            "request is invalid",
            status_code=400,
            code=ErrorCode.INVALID_REQUEST,
        )

    @app.exception_handler(LoginRateLimitError)
    async def login_rate_limit(
        _request: Request,
        error: LoginRateLimitError,
    ) -> JSONResponse:
        return _error_response(
            str(error),
            status_code=429,
            code=ErrorCode.CONFLICT,
            headers={
                "Retry-After": str(error.retry_after_seconds),
            },
        )

    @app.exception_handler(ApplicationNotFoundError)
    @app.exception_handler(LocalSessionNotFoundError)
    async def missing_resource(
        _request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(
            str(error),
            status_code=404,
            code=ErrorCode.NOT_FOUND,
        )

    @app.exception_handler(ApplicationConflictError)
    @app.exception_handler(LocalSessionConflictError)
    async def conflict(
        _request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(
            str(error),
            status_code=409,
            code=ErrorCode.CONFLICT,
        )

    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(ValidationError)
    @app.exception_handler(ValueError)
    async def bad_request(
        _request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(
            str(error),
            status_code=400,
            code=ErrorCode.INVALID_REQUEST,
        )

    def principal_for_request(request: Request) -> Principal:
        return identity.authenticate(request.cookies.get(cookie_name))

    def workspace_principal(
        request: Request,
        workspace_id: str,
        *,
        write: bool = False,
    ) -> Principal:
        principal = principal_for_request(request)
        if write:
            principal.require_write(workspace_id)
        else:
            principal.membership(workspace_id)
        return principal

    def public_session(value: Any) -> Any:
        if score_available:
            return value
        return value.model_copy(
            update={
                "available_artifact_kinds": tuple(
                    kind
                    for kind in value.available_artifact_kinds
                    if kind not in PRIVATE_SCORE_ARTIFACT_KINDS
                )
            }
        )

    def require_public_score() -> None:
        if not score_available:
            raise ApplicationNotFoundError(
                "score runtime is not available"
            )

    def require_public_artifact(artifact: Any) -> None:
        if (
            not score_available
            and artifact.kind in PRIVATE_SCORE_ARTIFACT_KINDS
        ):
            raise ApplicationNotFoundError(
                "artifact does not exist"
            )

    @app.post("/api/v1/auth/login", response_model=AuthSession)
    def login(request: Request, credentials: LoginRequest) -> Response:
        client = (
            request.client.host
            if request.client is not None
            else "unknown"
        )
        login_limiter.check(client, credentials.username)
        try:
            issued = identity.login(
                credentials.username,
                credentials.password,
            )
        except AuthenticationError:
            login_limiter.failure(client, credentials.username)
            raise
        login_limiter.success(client, credentials.username)
        response = JSONResponse(
            _auth_session(issued.principal).model_dump(mode="json")
        )
        response.set_cookie(
            cookie_name,
            issued.token,
            max_age=max(
                0,
                int(
                    (
                        issued.absolute_expires_at
                        - datetime.now(timezone.utc)
                    ).total_seconds()
                ),
            ),
            expires=issued.absolute_expires_at,
            path="/",
            secure=secure_cookie,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/api/v1/auth/session", response_model=AuthSession)
    def auth_session(request: Request) -> AuthSession:
        return _auth_session(principal_for_request(request))

    @app.post("/api/v1/auth/logout", response_model=LogoutResult)
    def logout(request: Request) -> Response:
        identity.logout(request.cookies.get(cookie_name))
        response = JSONResponse(
            LogoutResult().model_dump(mode="json")
        )
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=secure_cookie,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get(
        "/api/v1/capabilities",
        response_model=RuntimeCapabilities,
    )
    def capabilities(request: Request) -> RuntimeCapabilities:
        principal_for_request(request)
        return RuntimeCapabilities(
            runtime_mode=RuntimeMode.LOCAL,
            supported_schema_versions=(CONTRACT_SCHEMA_VERSION,),
            supported_pcm_protocol_versions=(PCM_PROTOCOL_VERSION,),
            capture_sources=(SourceKind.MICROPHONE, SourceKind.REPLAY),
            score_available=score_available,
            recoverable_delete=True,
            max_pcm_block_frames=1_048_576,
            max_event_range_samples=round(
                MAX_VISIBLE_RANGE_S * 384_000
            ),
        )

    @app.get("/api/v1/workspaces")
    def workspaces(request: Request) -> dict[str, Any]:
        principal = principal_for_request(request)
        allowed = {
            membership.workspace_id
            for membership in principal.memberships
        }
        page = runtime.application.sessions.list_workspaces()
        return (
            page.model_copy(
                update={
                    "items": tuple(
                        item
                        for item in page.items
                        if item.workspace_id in allowed
                    )
                }
            ).model_dump(mode="json")
        )

    @app.get("/api/v1/workspaces/{workspace_id}/sessions")
    def sessions(
        request: Request,
        workspace_id: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id)
        page = runtime.application.sessions.list_sessions(
            workspace_id,
            cursor=cursor,
            limit=limit,
            active_session_id=runtime.active_session_id(),
        )
        return page.model_copy(
            update={
                "items": tuple(
                    public_session(item) for item in page.items
                )
            }
        ).model_dump(mode="json")

    @app.get(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}",
    )
    def session(
        request: Request,
        workspace_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id)
        return public_session(
            runtime.application.sessions.get_session(
                workspace_id,
                session_id,
                active_session_id=runtime.active_session_id(),
            )
        ).model_dump(mode="json")

    @app.patch(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}",
    )
    def update_session_annotation(
        request: Request,
        workspace_id: str,
        session_id: str,
        annotation: SessionAnnotationPatch,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id, write=True)
        if (
            annotation.workspace_id != workspace_id
            or annotation.session_id != session_id
        ):
            raise ValueError(
                "session annotation target does not match its path"
            )
        return runtime.application.sessions.update_session_annotation(
            workspace_id,
            session_id,
            display_name=annotation.display_name,
        ).model_dump(mode="json")

    @app.get(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/horizon",
    )
    def horizon(
        request: Request,
        workspace_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id)
        return runtime.application.sessions.get_horizon(
            workspace_id,
            session_id,
        ).model_dump(mode="json")

    @app.get(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/events",
    )
    def events(
        request: Request,
        workspace_id: str,
        session_id: str,
        start_sample: int,
        end_sample: int,
        cursor: str | None = None,
        limit: int = 1024,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id)
        return runtime.application.sessions.get_events(
            workspace_id,
            session_id,
            start_sample=start_sample,
            end_sample=end_sample,
            cursor=cursor,
            limit=min(limit, MAX_QUERY_LIMIT),
        ).model_dump(mode="json")

    @app.get(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/artifacts",
    )
    def artifacts(
        request: Request,
        workspace_id: str,
        session_id: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id)
        page = runtime.application.sessions.list_artifacts(
            workspace_id,
            session_id,
            cursor=cursor,
            limit=limit,
        )
        if score_available:
            return page.model_dump(mode="json")
        return ArtifactPage(
            workspace_id=page.workspace_id,
            session_id=page.session_id,
            items=tuple(
                item
                for item in page.items
                if item.kind not in PRIVATE_SCORE_ARTIFACT_KINDS
            ),
            next_cursor=page.next_cursor,
        ).model_dump(mode="json")

    @app.get(
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/artifacts/{artifact_id}/access"
        ),
        response_model=ArtifactAccess,
    )
    def artifact_access(
        request: Request,
        workspace_id: str,
        session_id: str,
        artifact_id: str,
    ) -> ArtifactAccess:
        workspace_principal(request, workspace_id)
        artifact, _path = runtime.application.sessions.get_artifact(
            workspace_id,
            session_id,
            artifact_id,
        )
        require_public_artifact(artifact)
        content_url = (
            f"/api/v1/workspaces/{quote(workspace_id, safe='')}"
            f"/sessions/{quote(session_id, safe='')}"
            f"/artifacts/{quote(artifact_id, safe='')}/content"
        )
        return ArtifactAccess(
            workspace_id=workspace_id,
            session_id=session_id,
            artifact_id=artifact_id,
            media_type=artifact.media_type,
            download_name=artifact.filename,
            url=content_url,
        )

    @app.get(
        
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/artifacts/{artifact_id}/content"
        
    )
    def artifact_content(
        request: Request,
        workspace_id: str,
        session_id: str,
        artifact_id: str,
    ) -> FileResponse:
        workspace_principal(request, workspace_id)
        artifact, path = runtime.application.sessions.get_artifact(
            workspace_id,
            session_id,
            artifact_id,
        )
        require_public_artifact(artifact)
        return FileResponse(
            path,
            media_type=artifact.media_type,
            headers={"Cache-Control": "no-store"},
        )

    @app.get(
        
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/score-variants"
        
    )
    def score_variants(
        request: Request,
        workspace_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id)
        if not score_available:
            return ScoreVariantPage(
                workspace_id=workspace_id,
                session_id=session_id,
                items=(),
            ).model_dump(mode="json")
        return runtime.application.sessions.list_score_variants(
            workspace_id,
            session_id,
        ).model_dump(mode="json")

    @app.post(
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/score-jobs"
        ),
        status_code=202,
    )
    def start_score_job(
        request: Request,
        workspace_id: str,
        session_id: str,
        start: ScoreJobStart,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id, write=True)
        require_public_score()
        if (
            start.workspace_id != workspace_id
            or start.session_id != session_id
        ):
            raise ValueError("score request target does not match its path")
        target = runtime.application.sessions.get_session(
            workspace_id,
            session_id,
        )
        if (
            start.transcription_run_id
            != target.current_transcription_run_id
        ):
            raise ValueError(
                "score request transcription run is not current"
            )
        return runtime.start_score(
            session_id,
            expected_commit_sample=start.commit_sample,
        ).model_dump(mode="json")

    @app.post(
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/score-variants"
        ),
        status_code=201,
    )
    def create_score_variant(
        request: Request,
        workspace_id: str,
        session_id: str,
        variant: ScoreVariantRequest,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id, write=True)
        require_public_score()
        if (
            variant.workspace_id != workspace_id
            or variant.session_id != session_id
        ):
            raise ValueError(
                "score variant request target does not match its path"
            )
        return runtime.create_score_variant(variant).model_dump(
            mode="json"
        )

    @app.get("/api/v1/jobs/{job_id}")
    def score_job(
        request: Request,
        job_id: str,
    ) -> dict[str, Any]:
        job = runtime.score_job(job_id)
        workspace_principal(request, job.workspace_id)
        return job.model_dump(mode="json")

    @app.delete(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}",
    )
    def delete_session(
        request: Request,
        workspace_id: str,
        session_id: str,
        deletion: DeleteSessionRequest,
    ) -> dict[str, Any]:
        workspace_principal(request, workspace_id, write=True)
        if (
            deletion.workspace_id != workspace_id
            or deletion.session_id != session_id
        ):
            raise ValueError(
                "delete request target does not match its path"
            )
        return runtime.delete_api_session(session_id)

    @app.post("/api/replay", status_code=202)
    def replay(
        request: Request,
        _start: dict[str, Any],
    ) -> dict[str, Any]:
        workspace_principal(request, LOCAL_WORKSPACE_ID, write=True)
        runtime.start_replay()
        return runtime.public_state()

    @app.websocket("/api/live")
    async def live(websocket: WebSocket) -> None:
        if not hmac.compare_digest(
            websocket.headers.get("origin", ""),
            public_origin,
        ):
            await websocket.close(code=4403)
            return
        token = websocket.cookies.get(cookie_name)
        try:
            principal = identity.authenticate(token)
            principal.require_write(LOCAL_WORKSPACE_ID)
        except AuthenticationError:
            await websocket.close(code=4401)
            return
        except AuthorizationError:
            await websocket.close(code=4403)
            return
        await websocket.accept()
        last_authenticated = time.monotonic()
        capture_session: CorrectedSession | None = None
        stopped = False
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if (
                    time.monotonic() - last_authenticated
                    >= WEBSOCKET_REAUTHENTICATION_SECONDS
                ):
                    principal = identity.authenticate(token)
                    principal.require_write(LOCAL_WORKSPACE_ID)
                    last_authenticated = time.monotonic()
                binary = message.get("bytes")
                text = message.get("text")
                if binary is not None:
                    if capture_session is None:
                        raise ValueError(
                            "microphone PCM arrived before Start"
                        )
                    block = parse_pcm_block(binary)
                    capture_session = (
                        runtime.application.capture.accept_block(
                            block,
                            received_ns=time.perf_counter_ns(),
                        )
                    )
                    events: list[dict[str, Any]] = []
                    runtime.record_delivery(events)
                    await websocket.send_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "block_ack",
                            "sequence": block.sequence,
                            "received_source_frames": (
                                capture_session.horizons.audio_head_sample
                            ),
                            "events": events,
                            "horizons": (
                                capture_session.horizons.document(
                                    sample_rate_hz=(
                                        capture_session.sample_rate_hz
                                    )
                                )
                            ),
                        }
                    )
                    continue
                if text is None:
                    raise ValueError(
                        "microphone WebSocket message is invalid"
                    )
                if len(text.encode("utf-8")) > MAX_CLIENT_METADATA_BYTES:
                    raise ValueError(
                        "microphone control message is too large"
                    )
                try:
                    control = json.loads(text)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "microphone control message is invalid JSON"
                    ) from error
                if (
                    not isinstance(control, dict)
                    or control.get("schema_version")
                    != CORRECTED_STREAM_SCHEMA
                ):
                    raise ValueError(
                        "microphone control schema is unsupported"
                    )
                message_type = control.get("type")
                if message_type == "start":
                    if capture_session is not None:
                        raise ValueError(
                            "microphone session already started"
                        )
                    sample_rate_hz = control.get("sample_rate_hz")
                    metadata = control.get("client_metadata")
                    if (
                        not isinstance(sample_rate_hz, int)
                        or isinstance(sample_rate_hz, bool)
                        or not 8_000 <= sample_rate_hz <= 192_000
                        or not isinstance(metadata, dict)
                    ):
                        raise ValueError(
                            "microphone Start metadata is invalid"
                        )
                    encoded_metadata = json.dumps(
                        metadata,
                        allow_nan=False,
                    ).encode()
                    if (
                        len(encoded_metadata)
                        > MAX_CLIENT_METADATA_BYTES
                    ):
                        raise ValueError(
                            "microphone client metadata is too large"
                        )
                    started = (
                        runtime.application.capture.start_microphone(
                            sample_rate_hz=sample_rate_hz,
                            client_metadata=metadata,
                        )
                    )
                    capture_session = started.session
                    await websocket.send_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "ready",
                            "session_id": capture_session.session_id,
                            "sample_rate_hz": sample_rate_hz,
                            "lanes": [
                                lane.status()
                                for lane in capture_session.lanes
                            ],
                            "correction": {
                                "mode": started.correction_mode,
                                "reason": started.correction_reason,
                                "profile_id": (
                                    started.correction_profile_id
                                ),
                            },
                        }
                    )
                    continue
                if message_type == "stop":
                    if capture_session is None:
                        raise ValueError(
                            "microphone Stop arrived before Start"
                        )
                    frame_count = control.get("frame_count")
                    block_count = control.get("block_count")
                    transport = control.get("transport")
                    if (
                        not isinstance(frame_count, int)
                        or isinstance(frame_count, bool)
                        or not isinstance(block_count, int)
                        or isinstance(block_count, bool)
                        or (
                            transport is not None
                            and not isinstance(transport, dict)
                        )
                    ):
                        raise ValueError(
                            "microphone Stop evidence is invalid"
                        )
                    manifest = (
                        runtime.application.capture.stop_microphone(
                            frame_count=frame_count,
                            block_count=block_count,
                            transport=transport,
                        )
                    )
                    stopped = True
                    await websocket.send_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "stopped",
                            "session": manifest,
                            "exports": {},
                            "settling": True,
                        }
                    )
                    await websocket.close(code=1000)
                    return
                raise ValueError(
                    f"unsupported microphone control type: {message_type}"
                )
        except WebSocketDisconnect:
            pass
        except (
            AuthenticationError,
            AuthorizationError,
            ConnectionError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            runtime.application.capture.abort_microphone(error)
            if websocket.application_state is WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "schema_version": CORRECTED_STREAM_SCHEMA,
                        "type": "error",
                        "error": str(error),
                    }
                )
                await websocket.close(code=1008)
        finally:
            if (
                capture_session is not None
                and not stopped
                and not capture_session.closed
            ):
                runtime.application.capture.abort_microphone(
                    RuntimeError(
                        "microphone WebSocket closed before Stop"
                    )
                )

    @app.get("/api/{api_path:path}", include_in_schema=False)
    def unknown_api(api_path: str) -> JSONResponse:
        return _error_response(
            f"API resource does not exist: /api/{api_path}",
            status_code=404,
            code=ErrorCode.NOT_FOUND,
        )

    @app.get("/{asset_path:path}", include_in_schema=False)
    def static_asset(asset_path: str) -> FileResponse:
        request_path = f"/{asset_path}"
        asset = runtime.asset_path(request_path)
        if asset is None:
            asset = runtime.asset_path("/")
        if asset is None:
            raise ApplicationNotFoundError(
                "application asset does not exist"
            )
        return FileResponse(asset)

    return app


def serve_family_application(
    workspace_directory: Path,
    *,
    bind: str,
    port: int,
    public_origin: str,
    open_browser: bool = True,
    insecure_local_cookie: bool = False,
    commit_device: str = "cpu",
    commit_threads: int | None = 2,
    correction_mode: str = "auto",
    backend_profile_path: Path | None = None,
    score_runtime: Path = Path("results/midi2score-runtime"),
    minimum_free_bytes: int,
    model_idle_timeout_s: float,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_silence_s: float = 0.0,
    replay_realtime: bool = True,
    compact_recordings: bool = True,
    debug_retention: bool = False,
    debug_byte_cap: int = 64 * 1024**2,
    debug_max_age_s: float = 72 * 60 * 60,
) -> None:
    """Build and run the authenticated single-process family application."""

    if insecure_local_cookie and bind not in {"127.0.0.1", "localhost"}:
        raise ValueError(
            "insecure local cookies require a loopback bind"
        )
    repository_root = Path(__file__).resolve().parents[2]
    app_root = repository_root / "app"
    subprocess.run(
        ["npm", "run", "build", "--prefix", str(app_root)],
        cwd=repository_root,
        check=True,
    )
    runtime = create_corrected_workbench_runtime(
        workspace_directory,
        commit_device=commit_device,
        commit_threads=commit_threads,
        correction_mode=correction_mode,
        backend_profile_path=backend_profile_path,
        score_runtime=score_runtime,
        minimum_free_bytes=minimum_free_bytes,
        model_idle_timeout_s=model_idle_timeout_s,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_silence_s=replay_silence_s,
        replay_realtime=replay_realtime,
        web_root=app_root / "dist",
        application_mode="shared-react-family",
        public_origin=None,
        compact_recordings=compact_recordings,
        debug_retention=debug_retention,
        debug_byte_cap=debug_byte_cap,
        debug_max_age_s=debug_max_age_s,
    )
    _, engine = initialize_catalog(workspace_directory)
    try:
        identity = IdentityApplicationService(
            SqlAlchemyIdentityRepository(engine),
            Argon2PasswordHasher(),
            workspace_id=LOCAL_WORKSPACE_ID,
        )
        identity.prune_sessions()
        application = create_family_application(
            runtime,
            identity,
            public_origin=public_origin,
            secure_cookie=not insecure_local_cookie,
        )
        print(f"Atpiano family workspace: {runtime.workspace_directory}")
        print(public_origin)
        if open_browser:
            webbrowser.open(public_origin)
        import uvicorn

        uvicorn.run(
            application,
            host=bind,
            port=port,
            proxy_headers=False,
            server_header=False,
        )
    finally:
        engine.dispose()
        runtime.close()
