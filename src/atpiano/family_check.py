"""Passwordless local-operator smoke checks for the family service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi.testclient import TestClient
from httpx import Client

from atpiano.application.errors import AuthenticationError
from atpiano.corrected_workbench import CorrectedWorkbenchRuntime
from atpiano.family_server import (
    SECURE_SESSION_COOKIE,
    create_family_application,
)
from atpiano.identity_cli import identity_service

OPERATOR_ORIGIN = "https://operator.atpiano.invalid"


def _require_status(
    response: Any,
    expected: int,
    description: str,
) -> Any:
    if response.status_code != expected:
        raise RuntimeError(
            f"{description} returned HTTP {response.status_code}; "
            f"expected {expected}"
        )
    return response


def _running_origin(value: str) -> str:
    parsed = urlsplit(value)
    loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if (
        parsed.scheme not in ({"http", "https"} if loopback else {"https"})
        or parsed.hostname is None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base URL must be an HTTPS origin or an HTTP loopback origin"
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def check_family_workspace(
    workspace_directory: Path,
    *,
    session_id: str,
    username: str | None = None,
    web_root: Path | None = None,
    base_url: str | None = None,
    require_score: bool = False,
    score_runtime: Path = Path("results/midi2score-runtime"),
) -> dict[str, Any]:
    """Exercise protected routes and audio bytes without knowing a password."""

    workspace = workspace_directory.resolve()
    repository_root = Path(__file__).resolve().parents[2]
    resolved_web_root = (web_root or repository_root / "app" / "dist").resolve()
    if base_url is None and not (resolved_web_root / "index.html").is_file():
        raise RuntimeError(
            f"built React application does not exist at {resolved_web_root}"
        )

    identity, engine = identity_service(workspace)
    runtime: CorrectedWorkbenchRuntime | None = None
    issued = None
    try:
        issued = identity.issue_local_operator_session(username)
        if base_url is None:
            origin = OPERATOR_ORIGIN
            runtime = CorrectedWorkbenchRuntime(
                workspace,
                commit_model_factory=lambda: None,
                minimum_free_bytes=0,
                score_runtime=score_runtime,
                web_root=resolved_web_root,
                application_mode="shared-react-family-operator-check",
            )
            app = create_family_application(
                runtime,
                identity,
                public_origin=origin,
            )
            client_context: Any = TestClient(app, base_url=origin)
            target = "in-process"
        else:
            origin = _running_origin(base_url)
            client_context = Client(
                base_url=origin,
                follow_redirects=False,
                timeout=30.0,
            )
            target = origin
        cookie = {
            "Cookie": f"{SECURE_SESSION_COOKIE}={issued.token}",
        }
        encoded_session = quote(session_id, safe="")
        session_root = (
            f"/api/v1/workspaces/local/sessions/{encoded_session}"
        )

        with client_context as client:
            _require_status(client.get("/"), 200, "application shell")
            authenticated = _require_status(
                client.get("/api/v1/auth/session", headers=cookie),
                200,
                "operator session",
            ).json()
            capabilities = _require_status(
                client.get("/api/v1/capabilities", headers=cookie),
                200,
                "capabilities",
            ).json()
            if require_score and not capabilities["score_available"]:
                raise RuntimeError("score runtime is not available")
            _require_status(
                client.get(session_root, headers=cookie),
                200,
                "retained session",
            )
            artifact_response = _require_status(
                client.get(
                    f"{session_root}/artifacts",
                    headers=cookie,
                    params={"limit": 100},
                ),
                200,
                "artifact catalog",
            )
            artifacts = artifact_response.json()["items"]
            audio_artifacts = [
                artifact
                for artifact in artifacts
                if artifact["kind"] == "audio"
            ]
            if not audio_artifacts:
                raise RuntimeError(
                    f"session {session_id} has no audio artifact"
                )
            audio = next(
                (
                    artifact
                    for artifact in audio_artifacts
                    if artifact["media_type"] == "audio/mpeg"
                ),
                audio_artifacts[0],
            )
            encoded_artifact = quote(audio["artifact_id"], safe="")
            artifact_root = (
                f"{session_root}/artifacts/{encoded_artifact}"
            )
            access = _require_status(
                client.get(f"{artifact_root}/access", headers=cookie),
                200,
                "audio access metadata",
            ).json()
            content = _require_status(
                client.get(
                    f"{artifact_root}/content",
                    headers={**cookie, "Range": "bytes=0-1023"},
                ),
                206,
                "audio content range",
            )
            if not content.content:
                raise RuntimeError("audio content range was empty")

            score_report = None
            if capabilities["score_available"]:
                variants = _require_status(
                    client.get(
                        f"{session_root}/score-variants",
                        headers=cookie,
                    ),
                    200,
                    "score variants",
                ).json()["items"]
                selected_variant = next(
                    (
                        variant
                        for variant in variants
                        if variant["selected"]
                    ),
                    None,
                )
                musicxml_artifacts = [
                    artifact
                    for artifact in artifacts
                    if artifact["kind"] == "musicxml"
                ]
                score_artifact = next(
                    (
                        artifact
                        for artifact in musicxml_artifacts
                        if (
                            selected_variant is not None
                            and artifact["artifact_id"]
                            == selected_variant["musicxml_artifact_id"]
                        )
                    ),
                    musicxml_artifacts[0] if musicxml_artifacts else None,
                )
                if require_score and score_artifact is None:
                    raise RuntimeError(
                        f"session {session_id} has no rendered score artifact"
                    )
                if score_artifact is not None:
                    encoded_score_artifact = quote(
                        score_artifact["artifact_id"],
                        safe="",
                    )
                    score_root = (
                        f"{session_root}/artifacts/{encoded_score_artifact}"
                    )
                    score_access = _require_status(
                        client.get(
                            f"{score_root}/access",
                            headers=cookie,
                        ),
                        200,
                        "score access metadata",
                    ).json()
                    score_content = _require_status(
                        client.get(
                            f"{score_root}/content",
                            headers=cookie,
                        ),
                        200,
                        "score content",
                    )
                    if b"<score-partwise" not in score_content.content:
                        raise RuntimeError(
                            "rendered score is not MusicXML partwise content"
                        )
                    score_report = {
                        "artifact_id": score_artifact["artifact_id"],
                        "filename": score_artifact["filename"],
                        "media_type": score_access["media_type"],
                        "byte_count": len(score_content.content),
                    }

            _require_status(
                client.post(
                    "/api/v1/auth/logout",
                    headers={
                        **cookie,
                        "Origin": origin,
                    },
                ),
                200,
                "operator logout",
            )
            _require_status(
                client.get("/api/v1/auth/session", headers=cookie),
                401,
                "revoked operator session",
            )

        return {
            "schema_version": "atpiano.family-check.v1",
            "workspace": str(workspace),
            "target": target,
            "operator": authenticated["principal"]["username"],
            "session_id": session_id,
            "artifact_count": len(artifacts),
            "score_available": capabilities["score_available"],
            "score": score_report,
            "audio": {
                "artifact_id": audio["artifact_id"],
                "filename": audio["filename"],
                "media_type": access["media_type"],
                "checked_range_bytes": len(content.content),
            },
            "operator_session_revoked": True,
        }
    finally:
        if issued is not None:
            identity.logout(issued.token)
            try:
                identity.authenticate(issued.token)
            except AuthenticationError:
                pass
            else:
                raise RuntimeError("operator session was not revoked")
        if runtime is not None:
            runtime.close()
        engine.dispose()


def run_family_check(args: object) -> int:
    report = check_family_workspace(
        Path(getattr(args, "workspace")),
        session_id=str(getattr(args, "session")),
        username=getattr(args, "as_user"),
        base_url=getattr(args, "base_url"),
        require_score=bool(getattr(args, "require_score")),
        score_runtime=Path(getattr(args, "score_runtime")),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0
