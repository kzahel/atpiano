from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from atpiano.adapters.passwords import Argon2PasswordHasher
from atpiano.adapters.sqlite_identity import SqlAlchemyIdentityRepository
from atpiano.application.identity import IdentityApplicationService
from atpiano.contracts.schemas import MembershipRole
from atpiano.corrected import CorrectedSession
from atpiano.corrected_export import write_corrected_exports
from atpiano.corrected_workbench import CorrectedWorkbenchRuntime
from atpiano.family_server import create_family_application
from atpiano.live import PcmBlock
from atpiano.persistence import initialize_catalog

PUBLIC_ORIGIN = "https://family.test"
SESSION_ID = "20260728T120000-aaaaaaaaaaaa"


def _completed_session(workspace: Path) -> None:
    session = CorrectedSession(
        workspace / SESSION_ID,
        session_id=SESSION_ID,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        minimum_free_bytes=0,
    )
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=100,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0125,
            pcm_s16le=b"\0\0" * 100,
        ),
        received_ns=1,
    )
    session.finalize()
    write_corrected_exports(session.directory)


def _environment(
    tmp_path: Path,
) -> tuple[
    TestClient,
    CorrectedWorkbenchRuntime,
    IdentityApplicationService,
    Any,
]:
    _completed_session(tmp_path)
    web_root = tmp_path / "web"
    web_root.mkdir()
    (web_root / "index.html").write_text(
        "<!doctype html><title>Atpiano login</title>",
        encoding="utf-8",
    )
    runtime = CorrectedWorkbenchRuntime(
        tmp_path,
        commit_model_factory=lambda: None,
        minimum_free_bytes=0,
        score_runtime=tmp_path / "score-runtime",
        web_root=web_root,
        public_origin=PUBLIC_ORIGIN,
    )
    _, engine = initialize_catalog(tmp_path)
    identity = IdentityApplicationService(
        SqlAlchemyIdentityRepository(engine),
        Argon2PasswordHasher(),
        workspace_id="local",
    )
    identity.create_user("owner", "the owner family password")
    identity.create_user(
        "viewer",
        "the viewer family password",
        role=MembershipRole.VIEWER,
    )
    app = create_family_application(
        runtime,
        identity,
        public_origin=PUBLIC_ORIGIN,
    )
    client = TestClient(app, base_url=PUBLIC_ORIGIN)
    return client, runtime, identity, engine


def _login(
    client: TestClient,
    username: str,
    password: str,
) -> Any:
    return client.post(
        "/api/v1/auth/login",
        headers={"Origin": PUBLIC_ORIGIN},
        json={
            "schema_version": "atpiano.contract.v1",
            "username": username,
            "password": password,
        },
    )


def test_static_login_is_public_but_data_and_websocket_are_not(
    tmp_path: Path,
) -> None:
    client, runtime, _identity, engine = _environment(tmp_path)
    try:
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/capabilities").status_code == 401
        assert client.get("/api/legacy").status_code == 404
        artifact_url = (
            f"/api/v1/workspaces/local/sessions/{SESSION_ID}/artifacts"
        )
        assert client.get(artifact_url).status_code == 401
        with pytest.raises(WebSocketDisconnect) as denied:
            with client.websocket_connect(
                "wss://family.test/api/live",
                headers={"Origin": PUBLIC_ORIGIN},
            ):
                pass
        assert denied.value.code == 4401
    finally:
        runtime.close()
        engine.dispose()


def test_owner_cookie_authenticates_api_artifacts_and_websocket(
    tmp_path: Path,
) -> None:
    client, runtime, _identity, engine = _environment(tmp_path)
    try:
        denied = _login(client, "owner", "the password is incorrect")
        assert denied.status_code == 401
        assert (
            denied.json()["error"]["message"]
            == "username or password is incorrect"
        )

        login = _login(client, "OWNER", "the owner family password")
        assert login.status_code == 200
        assert login.json()["principal"]["username"] == "owner"
        cookie = login.headers["set-cookie"]
        assert "__Host-atpiano_session=" in cookie
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=lax" in cookie
        assert "Domain=" not in cookie

        assert client.get("/api/v1/auth/session").status_code == 200
        capabilities = client.get("/api/v1/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["score_available"] is False
        workspaces = client.get("/api/v1/workspaces")
        assert [item["workspace_id"] for item in workspaces.json()["items"]] == [
            "local"
        ]

        artifacts_url = (
            f"/api/v1/workspaces/local/sessions/{SESSION_ID}/artifacts"
        )
        artifacts = client.get(artifacts_url)
        assert artifacts.status_code == 200
        artifact_id = artifacts.json()["items"][0]["artifact_id"]
        content = client.get(f"{artifacts_url}/{artifact_id}/content")
        assert content.status_code == 200
        assert content.content
        ranged = client.get(
            f"{artifacts_url}/{artifact_id}/content",
            headers={"Range": "bytes=0-3"},
        )
        assert ranged.status_code == 206
        assert len(ranged.content) == 4

        with client.websocket_connect(
            "wss://family.test/api/live",
            headers={"Origin": PUBLIC_ORIGIN},
        ):
            pass

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": PUBLIC_ORIGIN},
        )
        assert logout.status_code == 200
        assert client.get("/api/v1/auth/session").status_code == 401
    finally:
        runtime.close()
        engine.dispose()


def test_viewer_cannot_replay_or_delete(tmp_path: Path) -> None:
    client, runtime, _identity, engine = _environment(tmp_path)
    try:
        assert (
            _login(client, "viewer", "the viewer family password").status_code
            == 200
        )
        replay = client.post(
            "/api/replay",
            headers={"Origin": PUBLIC_ORIGIN},
            json={"fixture_id": "fixture:default"},
        )
        assert replay.status_code == 403
        deletion = client.request(
            "DELETE",
            f"/api/v1/workspaces/local/sessions/{SESSION_ID}",
            headers={"Origin": PUBLIC_ORIGIN},
            json={
                "schema_version": "atpiano.contract.v1",
                "workspace_id": "local",
                "session_id": SESSION_ID,
                "request_id": "request:delete",
                "confirmation": "recoverable-delete",
            },
        )
        assert deletion.status_code == 403
        assert (tmp_path / SESSION_ID).is_dir()
    finally:
        runtime.close()
        engine.dispose()


def test_mutations_require_exact_origin_and_bounded_body(
    tmp_path: Path,
) -> None:
    client, runtime, _identity, engine = _environment(tmp_path)
    try:
        assert (
            _login(client, "owner", "the owner family password").status_code
            == 200
        )
        assert client.post("/api/v1/auth/logout").status_code == 403
        oversized = client.post(
            "/api/v1/auth/logout",
            headers={
                "Origin": PUBLIC_ORIGIN,
                "Content-Length": str(64 * 1024 + 1),
            },
        )
        assert oversized.status_code == 413
    finally:
        runtime.close()
        engine.dispose()


def test_family_server_rejects_untrusted_host(tmp_path: Path) -> None:
    client, runtime, _identity, engine = _environment(tmp_path)
    try:
        response = client.get(
            "/",
            headers={"Host": "attacker.example"},
        )
        assert response.status_code == 400
    finally:
        runtime.close()
        engine.dispose()


def test_failed_logins_are_rate_limited_without_plain_username_state(
    tmp_path: Path,
) -> None:
    client, runtime, _identity, engine = _environment(tmp_path)
    try:
        for _attempt in range(5):
            response = _login(
                client,
                "owner",
                "the password is incorrect",
            )
            assert response.status_code == 401
        limited = _login(
            client,
            "owner",
            "the password is incorrect",
        )
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) > 0
        assert (
            _login(
                client,
                "viewer",
                "the viewer family password",
            ).status_code
            == 200
        )
    finally:
        runtime.close()
        engine.dispose()
