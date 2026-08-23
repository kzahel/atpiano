from __future__ import annotations

import json
import os
import platform
import select
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.desktop import (
    DESKTOP_PROTOCOL_VERSION,
    DESKTOP_TOKEN_ENV,
    DesktopHandshake,
    DesktopReady,
    apply_model_pack,
    create_handshake,
    create_ready,
    desktop_runtime_environment,
    load_model_pack,
    model_pack_sha256,
    normalize_desktop_identity,
    validate_desktop_origin,
    validate_desktop_token,
)
from atpiano.fixture import generate_fixture
from atpiano.score_snapshot import (
    MIDI2SCORE_CHECKPOINT_SHA256,
    MIDI2SCORE_COMMIT,
    SCORE_RUNTIME_SCHEMA,
)
from atpiano.util import sha256_path, write_json

DESKTOP_ORIGIN = "tauri://localhost"
DESKTOP_TOKEN = "ab" * 32
IS_MACOS_ARM64 = platform.system() == "Darwin" and platform.machine() == "arm64"


def test_desktop_runtime_environment_redirects_library_caches(
    tmp_path: Path,
) -> None:
    environment = desktop_runtime_environment(tmp_path / "workspace")
    cache_root = (tmp_path / "workspace" / ".runtime-cache").resolve()

    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["NUMBA_CACHE_DIR"] == str(cache_root / "numba")
    assert environment["MPLCONFIGDIR"] == str(cache_root / "matplotlib")
    assert environment["XDG_CACHE_HOME"] == str(cache_root)
    assert environment["HF_HOME"] == str(cache_root / "huggingface")


def _write_model_pack(
    root: Path,
    *,
    platform_name: str = "macos",
    architecture: str = "arm64",
) -> Path:
    basic_pitch = root / "models" / "basic-pitch"
    basic_pitch.mkdir(parents=True)
    (basic_pitch / "model.mlmodel").write_bytes(b"basic-pitch-model")
    transkun = root / "models" / "transkun" / "2.0.pt"
    transkun.parent.mkdir(parents=True)
    transkun.write_bytes(b"transkun-checkpoint")
    transkun_config = transkun.with_suffix(".conf")
    transkun_config.write_text('{"model": "transkun"}\n', encoding="utf-8")
    manifest = root / "model-pack.json"
    write_json(
        manifest,
        {
            "schema_version": "atpiano.model-pack.v1",
            "model_pack_id": "atpiano-cpu-models-2026.07",
            "platform": platform_name,
            "architecture": architecture,
            "execution_backend": "cpu",
            "assets": [
                {
                    "asset_id": "basic-pitch-icassp-2022",
                    "adapter": "basic-pitch-0.4-live-v1",
                    "package": "basic-pitch",
                    "package_version": "0.4.0",
                    "path": "models/basic-pitch",
                    "sha256": sha256_path(basic_pitch),
                    "kind": "directory",
                },
                {
                    "asset_id": "transkun-2.0",
                    "adapter": "transkun-2.0-commit-v1",
                    "package": "transkun",
                    "package_version": "2.0.1",
                    "path": "models/transkun/2.0.pt",
                    "sha256": sha256_path(transkun),
                    "kind": "file",
                },
                {
                    "asset_id": "transkun-2.0-config",
                    "adapter": "transkun-2.0-commit-v1",
                    "package": "transkun",
                    "package_version": "2.0.1",
                    "path": "models/transkun/2.0.conf",
                    "sha256": sha256_path(transkun_config),
                    "kind": "file",
                },
            ],
        },
    )
    return manifest


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> urllib.request.Request:
    return urllib.request.Request(url, method=method, headers=headers or {})


def _write_score_runtime(root: Path) -> Path:
    repository = root / "MIDI2ScoreTransformer"
    repository.mkdir(parents=True)
    (root / "MIDI2ScoreTF.ckpt").write_bytes(b"score")
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"python")
    write_json(
        root / "runtime.json",
        {
            "schema_version": SCORE_RUNTIME_SCHEMA,
            "repository": {"commit": MIDI2SCORE_COMMIT},
            "checkpoint": {"sha256": MIDI2SCORE_CHECKPOINT_SHA256},
        },
    )
    return root


def _start_desktop_server(tmp_path: Path) -> tuple[Any, threading.Thread, str]:
    manifest = _write_model_pack(tmp_path / "pack")
    handshake = create_handshake(load_model_pack(manifest))
    server = create_corrected_workbench_server(
        tmp_path / "workspace",
        port=0,
        preview_model_factory=lambda: None,
        commit_model_factory=lambda: None,
        minimum_free_bytes=0,
        isolate_models=False,
        correction_mode="after-stop",
        desktop_origin=DESKTOP_ORIGIN,
        desktop_token=DESKTOP_TOKEN,
        desktop_handshake=handshake,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, thread, base_url


def test_desktop_token_is_exact_lowercase_hex() -> None:
    assert validate_desktop_token(DESKTOP_TOKEN) == DESKTOP_TOKEN
    for value in ("", "ab" * 31, "AB" * 32, "g0" * 32, "ab" * 33):
        with pytest.raises(ValueError, match="desktop token"):
            validate_desktop_token(value)


def test_desktop_origin_accepts_only_release_origins() -> None:
    assert validate_desktop_origin("tauri://localhost") == "tauri://localhost"
    assert validate_desktop_origin("http://tauri.localhost") == "http://tauri.localhost"
    assert (
        validate_desktop_origin("http://tauri.localhost", "windows")
        == "http://tauri.localhost"
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_desktop_origin("http://tauri.localhost", "macos")
    for value in (
        "https://tauri.localhost",
        "http://localhost",
        "tauri://localhost/",
        "http://tauri.localhost/",
    ):
        with pytest.raises(ValueError, match="bundled Tauri origin"):
            validate_desktop_origin(value)


def test_desktop_identity_accepts_release_targets() -> None:
    assert normalize_desktop_identity("Darwin", "arm64") == ("macos", "arm64")
    assert normalize_desktop_identity("Darwin", "aarch64") == ("macos", "arm64")
    assert normalize_desktop_identity("Windows", "AMD64") == (
        "windows",
        "x86_64",
    )
    assert normalize_desktop_identity("Windows", "x86_64") == (
        "windows",
        "x86_64",
    )


@pytest.mark.parametrize(
    ("system_name", "machine_name"),
    [
        ("Darwin", "x86_64"),
        ("Windows", "ARM64"),
        ("Linux", "x86_64"),
        ("Windows", "i686"),
    ],
)
def test_desktop_identity_rejects_unsupported_targets(
    system_name: str,
    machine_name: str,
) -> None:
    with pytest.raises(ValueError, match="macOS arm64 or Windows x86_64"):
        normalize_desktop_identity(system_name, machine_name)


def test_model_pack_verifies_assets_and_applies_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _write_model_pack(tmp_path)
    pack = load_model_pack(manifest)

    assert pack.model_pack_id == "atpiano-cpu-models-2026.07"
    assert len(model_pack_sha256(pack)) == 64
    monkeypatch.setenv("ATPIANO_BASIC_PITCH_MODEL", "previous-basic-pitch")
    monkeypatch.setenv("ATPIANO_TRANSKUN_CHECKPOINT", "previous-transkun")
    monkeypatch.setenv("ATPIANO_TRANSKUN_CONFIG", "previous-config")
    apply_model_pack(pack, manifest)
    assert Path(os.environ["ATPIANO_BASIC_PITCH_MODEL"]).is_dir()
    assert Path(os.environ["ATPIANO_TRANSKUN_CHECKPOINT"]).is_file()
    assert Path(os.environ["ATPIANO_TRANSKUN_CONFIG"]).is_file()

    checkpoint = tmp_path / "models" / "transkun" / "2.0.pt"
    checkpoint.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_model_pack(manifest)


def test_windows_x64_desktop_contracts_are_supported(tmp_path: Path) -> None:
    pack = load_model_pack(
        _write_model_pack(
            tmp_path,
            platform_name="windows",
            architecture="x86_64",
        )
    )
    handshake = DesktopHandshake(
        sidecar_version="0.1.0",
        python_version="3.10.19",
        platform="windows",
        architecture="x86_64",
        execution_backend="cpu",
        model_pack=pack,
        model_pack_sha256=model_pack_sha256(pack),
    )
    ready = DesktopReady(
        sidecar_version=handshake.sidecar_version,
        port=49152,
        platform=handshake.platform,
        architecture=handshake.architecture,
        execution_backend=handshake.execution_backend,
        model_pack_id=pack.model_pack_id,
        model_pack_sha256=handshake.model_pack_sha256,
    )

    assert ready.platform == "windows"
    assert ready.architecture == "x86_64"


def test_desktop_contracts_reject_cross_platform_pairs(tmp_path: Path) -> None:
    manifest = _write_model_pack(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["architecture"] = "x86_64"
    write_json(manifest, document)
    with pytest.raises(ValueError, match="macOS arm64 or Windows x86_64"):
        load_model_pack(manifest)

    pack = load_model_pack(_write_model_pack(tmp_path / "valid"))
    with pytest.raises(ValueError, match="does not match the host identity"):
        DesktopHandshake(
            sidecar_version="0.1.0",
            python_version="3.10.19",
            platform="windows",
            architecture="x86_64",
            execution_backend="cpu",
            model_pack=pack,
            model_pack_sha256=model_pack_sha256(pack),
        )


def test_model_pack_rejects_path_escape(tmp_path: Path) -> None:
    manifest = _write_model_pack(tmp_path / "pack")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["assets"][0]["path"] = "../outside"
    write_json(manifest, document)

    with pytest.raises(ValueError, match="escapes its pack"):
        load_model_pack(manifest)


@pytest.mark.skipif(not IS_MACOS_ARM64, reason="Phase 5 targets macOS arm64")
def test_desktop_handshake_and_ready_are_versioned(tmp_path: Path) -> None:
    pack = load_model_pack(_write_model_pack(tmp_path))
    handshake = create_handshake(pack)
    ready = create_ready(handshake, 49152)

    assert handshake.protocol_version == DESKTOP_PROTOCOL_VERSION
    assert handshake.model_pack == pack
    assert handshake.execution_backend == "cpu"
    assert handshake.score_available is False
    assert ready.protocol_version == DESKTOP_PROTOCOL_VERSION
    assert ready.model_pack_sha256 == handshake.model_pack_sha256
    assert ready.port == 49152

    score_handshake = create_handshake(pack, score_available=True)
    assert score_handshake.score_available is True


@pytest.mark.skipif(not IS_MACOS_ARM64, reason="Phase 5 targets macOS arm64")
def test_desktop_http_requires_bearer_and_exact_origin(tmp_path: Path) -> None:
    server, thread, base_url = _start_desktop_server(tmp_path)
    authorized = {
        "Authorization": f"Bearer {DESKTOP_TOKEN}",
        "Origin": DESKTOP_ORIGIN,
    }
    try:
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(f"{base_url}/api/config", timeout=2)
        assert missing.value.code == 401

        with urllib.request.urlopen(
            _request(f"{base_url}/desktop/v1/handshake", headers=authorized),
            timeout=2,
        ) as response:
            body = response.read()
            assert response.headers["Access-Control-Allow-Origin"] == DESKTOP_ORIGIN
        handshake = json.loads(body)
        assert handshake["protocol_version"] == DESKTOP_PROTOCOL_VERSION
        assert DESKTOP_TOKEN.encode() not in body

        preflight = _request(
            f"{base_url}/api/config",
            method="OPTIONS",
            headers={
                "Origin": DESKTOP_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "Authorization, Content-Type, X-Atpiano-Filename, "
                    "X-Atpiano-Performer-Profile, X-Atpiano-Request-Id"
                ),
            },
        )
        with urllib.request.urlopen(preflight, timeout=2) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Origin"] == DESKTOP_ORIGIN
            assert (
                "X-Atpiano-Performer-Profile"
                in response.headers["Access-Control-Allow-Headers"]
            )

        foreign = _request(
            f"{base_url}/api/config",
            method="OPTIONS",
            headers={
                "Origin": "https://attacker.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(foreign, timeout=2)
        assert denied.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(not IS_MACOS_ARM64, reason="Phase 5 targets macOS arm64")
def test_desktop_websocket_requires_token_subprotocol(tmp_path: Path) -> None:
    server, thread, base_url = _start_desktop_server(tmp_path)
    port = int(base_url.rsplit(":", 1)[1])

    def upgrade(protocol: str | None) -> tuple[bytes, bytes]:
        connection = socket.create_connection(("127.0.0.1", port), timeout=2)
        stream = connection.makefile("rb")
        request = (
            "GET /api/live HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Origin: {DESKTOP_ORIGIN}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        )
        if protocol is not None:
            request += f"Sec-WebSocket-Protocol: {protocol}\r\n"
        connection.sendall((request + "\r\n").encode("ascii"))
        status = stream.readline()
        headers = bytearray()
        while True:
            line = stream.readline()
            if line in {b"\r\n", b""}:
                break
            headers.extend(line)
        stream.close()
        connection.close()
        return status, bytes(headers)

    try:
        missing_status, _ = upgrade(None)
        assert missing_status.startswith(b"HTTP/1.0 401")
        wrong_status, _ = upgrade(f"{DESKTOP_PROTOCOL_VERSION}.{'cd' * 32}")
        assert wrong_status.startswith(b"HTTP/1.0 401")
        protocol = f"{DESKTOP_PROTOCOL_VERSION}.{DESKTOP_TOKEN}"
        multiple_status, _ = upgrade(f"other.v1, {protocol}")
        assert multiple_status.startswith(b"HTTP/1.0 401")
        accepted_status, accepted_headers = upgrade(protocol)
        assert accepted_status.startswith(b"HTTP/1.0 101")
        assert f"Sec-WebSocket-Protocol: {protocol}".encode() in accepted_headers
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_sidecar_rejects_incompatible_protocol_without_leaking_token(
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment[DESKTOP_TOKEN_ENV] = DESKTOP_TOKEN
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "atpiano.desktop_sidecar",
            "--workspace",
            str(tmp_path / "workspace"),
            "--replay-manifest",
            str(tmp_path / "missing-replay.json"),
            "--model-pack",
            str(tmp_path / "missing-model-pack.json"),
            "--expected-model-pack",
            "atpiano-cpu-models-2026.07",
            "--expected-protocol",
            "atpiano.desktop.v999",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )

    assert result.returncode == 2
    assert "desktop protocol is incompatible" in result.stderr
    assert DESKTOP_TOKEN not in result.stdout
    assert DESKTOP_TOKEN not in result.stderr


@pytest.mark.skipif(not IS_MACOS_ARM64, reason="Phase 5 targets macOS arm64")
def test_sidecar_starts_authenticated_and_stops_on_parent_eof(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture"
    generate_fixture(fixture)
    model_pack = _write_model_pack(tmp_path / "pack")
    score_runtime = _write_score_runtime(tmp_path / "score-runtime")
    environment = os.environ.copy()
    environment[DESKTOP_TOKEN_ENV] = DESKTOP_TOKEN
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "atpiano.desktop_sidecar",
            "--workspace",
            str(tmp_path / "workspace"),
            "--replay-manifest",
            str(fixture / "input.json"),
            "--model-pack",
            str(model_pack),
            "--expected-model-pack",
            "atpiano-cpu-models-2026.07",
            "--minimum-free-gib",
            "0",
            "--score-runtime",
            str(score_runtime),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    assert process.stdin is not None
    try:
        readable, _, _ = select.select([process.stdout], [], [], 15)
        if not readable:
            process.terminate()
            process.wait(timeout=5)
            pytest.fail(f"sidecar did not become ready: {process.stderr.read()}")
        ready_line = process.stdout.readline()
        ready = json.loads(ready_line)
        assert ready["protocol_version"] == DESKTOP_PROTOCOL_VERSION
        assert ready["host"] == "127.0.0.1"
        assert DESKTOP_TOKEN not in ready_line

        request = _request(
            f"http://127.0.0.1:{ready['port']}/desktop/v1/handshake",
            headers={
                "Authorization": f"Bearer {DESKTOP_TOKEN}",
                "Origin": DESKTOP_ORIGIN,
            },
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            handshake = json.load(response)
        assert handshake["model_pack"]["model_pack_id"] == ready["model_pack_id"]
        assert handshake["score_available"] is True

        process.stdin.close()
        assert process.wait(timeout=10) == 0
        stderr = process.stderr.read()
        assert DESKTOP_TOKEN not in stderr
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
