"""Build and audit the relocatable Windows x64 desktop runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import queue
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from atpiano.desktop import (
    DESKTOP_PROTOCOL_VERSION,
    MODEL_PACK_SCHEMA,
    ModelPack,
    desktop_runtime_environment,
    load_model_pack,
    model_pack_sha256,
)
from atpiano.desktop_packaging import MODEL_PACK_ID
from atpiano.musical_fixture import generate_musical_fixture
from atpiano.util import sha256_file, utc_now, write_json
from atpiano.windows_desktop_media import stage_runtime as stage_media_runtime
from atpiano.windows_desktop_media import validate_runtime as validate_media_runtime
from atpiano.windows_score_support import (
    _audit_native,
    _inventory,
    _materialize_runtime_symlinks,
    _package_inventory,
    _prune_python,
    _remove_tree,
    _tree_sha256_without,
    _uv_command,
    _validate_distributions,
    audit_windows_score_support,
    stage_windows_score_support,
)

PYTHON_VERSION = "3.10.19"
PYTHON_KEY = "cpython-3.10.19-windows-x86_64-none"
PLATFORM = "windows"
ARCHITECTURE = "x86_64"
EXECUTION_BACKEND = "cpu"
BUNDLE_MANIFEST_SCHEMA = "atpiano.desktop-bundle.v1"
BUNDLE_AUDIT_SCHEMA = "atpiano.windows-desktop-bundle-audit.v1"
MODEL_ASSET_PATHS = {
    "basic_pitch": Path("basic_pitch/saved_models/icassp_2022/nmp.onnx"),
    "transkun_checkpoint": Path("transkun/pretrained/2.0.pt"),
    "transkun_config": Path("transkun/pretrained/2.0.conf"),
}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _expected_stage_root(repository: Path) -> Path:
    return (repository / "app" / "src-tauri" / "resources" / "desktop-runtime").resolve()


def _run(
    arguments: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(argument) for argument in arguments],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
        env=dict(env) if env is not None else None,
    )


def _require_windows_builder() -> None:
    if platform.system() != "Windows" or platform.machine().upper() not in {"AMD64", "ARM64"}:
        raise RuntimeError("Windows desktop runtime requires a Windows build host")


def _resolve_managed_python_path(value: str, *, home: Path | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (home or Path.home()) / path
    return path.resolve()


def _managed_python(uv: Sequence[str]) -> tuple[Path, dict[str, Any]]:
    result = _run(
        [
            *uv,
            "python",
            "list",
            PYTHON_VERSION,
            "--only-installed",
            "--managed-python",
            "--output-format",
            "json",
        ],
        capture_output=True,
    )
    candidates = json.loads(result.stdout)
    selected = next(
        (candidate for candidate in candidates if candidate.get("key") == PYTHON_KEY),
        None,
    )
    if not isinstance(selected, dict) or not selected.get("path"):
        raise RuntimeError(f"uv-managed {PYTHON_KEY} is not installed")
    executable = _resolve_managed_python_path(str(selected["path"]))
    runtime_root = executable.parent
    identity = json.loads(
        _run(
            [
                executable,
                "-I",
                "-B",
                "-c",
                (
                    "import json,platform,sys;"
                    "print(json.dumps({'version': platform.python_version(),"
                    "'machine': platform.machine(), 'maxsize': sys.maxsize}))"
                ),
            ],
            capture_output=True,
        ).stdout
    )
    if identity != {
        "version": PYTHON_VERSION,
        "machine": "AMD64",
        "maxsize": 9_223_372_036_854_775_807,
    }:
        raise RuntimeError("managed desktop Python is not Windows x64")
    build = (runtime_root / "BUILD").read_text(encoding="utf-8").strip()
    acquisition_url = (
        "https://github.com/astral-sh/python-build-standalone/"
        f"releases/download/{build}/cpython-{PYTHON_VERSION}%2B{build}-"
        "x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
    )
    return runtime_root, {
        "key": PYTHON_KEY,
        "version": PYTHON_VERSION,
        "build": build,
        "acquisition_url": acquisition_url,
        "source_tree_sha256": _tree_sha256_without(runtime_root, set()),
    }


def _site_packages(runtime_root: Path) -> Path:
    return runtime_root / "Lib" / "site-packages"


def _stage_dependencies(
    runtime_root: Path,
    repository: Path,
    working_root: Path,
    uv: Sequence[str],
) -> None:
    site_packages = _site_packages(runtime_root)
    if site_packages.exists():
        _remove_tree(site_packages)
    (runtime_root / "Lib" / "EXTERNALLY-MANAGED").unlink(missing_ok=True)
    requirements = working_root / "requirements.lock"
    _run(
        [
            *uv,
            "export",
            "--frozen",
            "--extra",
            "corrected",
            "--no-dev",
            "--no-editable",
            "--no-emit-project",
            "--output-file",
            requirements,
        ],
        cwd=repository,
        capture_output=True,
    )
    python = runtime_root / "python.exe"
    _run(
        [
            *uv,
            "pip",
            "install",
            "--python",
            python,
            "--requirements",
            requirements,
            "--require-hashes",
            "--exact",
            "--strict",
            "--link-mode",
            "copy",
        ],
        cwd=repository,
    )
    requirements.unlink()
    _run(
        [
            *uv,
            "pip",
            "install",
            "--python",
            python,
            "--no-deps",
            "--reinstall",
            "--strict",
            "--link-mode",
            "copy",
            repository,
        ],
        cwd=repository,
    )


def _stage_model_pack(site_packages: Path, runtime_root: Path) -> ModelPack:
    sources = {key: site_packages / relative for key, relative in MODEL_ASSET_PATHS.items()}
    for source in sources.values():
        if not source.is_file():
            raise RuntimeError(f"Windows desktop model asset is missing: {source.name}")
    pack_root = runtime_root / "model-pack"
    basic_pitch = pack_root / "basic-pitch" / "nmp.onnx"
    checkpoint = pack_root / "transkun" / "2.0.pt"
    config = pack_root / "transkun" / "2.0.conf"
    basic_pitch.parent.mkdir(parents=True)
    checkpoint.parent.mkdir(parents=True)
    shutil.copy2(sources["basic_pitch"], basic_pitch)
    shutil.copy2(sources["transkun_checkpoint"], checkpoint)
    shutil.copy2(sources["transkun_config"], config)
    pack = ModelPack.model_validate(
        {
            "schema_version": MODEL_PACK_SCHEMA,
            "model_pack_id": MODEL_PACK_ID,
            "platform": PLATFORM,
            "architecture": ARCHITECTURE,
            "execution_backend": EXECUTION_BACKEND,
            "assets": [
                {
                    "asset_id": "basic-pitch-icassp-2022",
                    "adapter": "atpiano-basic-pitch-live-window-v1",
                    "package": "basic-pitch",
                    "package_version": "0.4.0",
                    "path": "basic-pitch/nmp.onnx",
                    "sha256": sha256_file(basic_pitch),
                    "kind": "file",
                },
                {
                    "asset_id": "transkun-2.0",
                    "adapter": "atpiano-transkun-trailing-v1",
                    "package": "transkun",
                    "package_version": "2.0.1",
                    "path": "transkun/2.0.pt",
                    "sha256": sha256_file(checkpoint),
                    "kind": "file",
                },
                {
                    "asset_id": "transkun-2.0-config",
                    "adapter": "atpiano-transkun-trailing-v1",
                    "package": "transkun",
                    "package_version": "2.0.1",
                    "path": "transkun/2.0.conf",
                    "sha256": sha256_file(config),
                    "kind": "file",
                },
            ],
        }
    )
    write_json(pack_root / "model-pack.json", pack.model_dump(mode="json"))
    _remove_tree(site_packages / "basic_pitch" / "saved_models")
    _remove_tree(site_packages / "transkun" / "pretrained")
    return pack


def _stage_fixture(runtime_root: Path) -> None:
    fixture = runtime_root / "fixture"
    manifest = generate_musical_fixture(fixture)
    manifest["created_at"] = "2026-07-27T00:00:00+00:00"
    write_json(fixture / "input.json", manifest)


def _score_support_record(root: Path) -> dict[str, Any]:
    manifest_path = root / "support-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "enabled": True,
        "relative_path": "score-support",
        "manifest_sha256": sha256_file(manifest_path),
        **manifest,
    }


def _validate_score_build_root(root: Path) -> None:
    if len(str(root)) > 60:
        raise RuntimeError(
            "Windows score build root is too long; set ATPIANO_WINDOWS_BUILD_ROOT "
            "to a short workspace path"
        )


def _score_build_root(repository: Path) -> Path:
    configured = os.environ.get("ATPIANO_WINDOWS_BUILD_ROOT")
    root = (
        Path(configured).expanduser().resolve()
        if configured
        else (repository.parent / ".atpiano-build").resolve()
    )
    _validate_score_build_root(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _stage_score_support(root: Path, repository: Path) -> None:
    staged = Path(
        tempfile.mkdtemp(prefix="atps-", dir=_score_build_root(repository))
    ).resolve()
    staged.rmdir()
    try:
        stage_windows_score_support(staged, repository)
        shutil.move(str(staged), root)
    finally:
        if staged.exists():
            _remove_tree(staged)


def _package_identities(packages: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return sorted(
        (
            {"name": str(package["name"]), "version": str(package["version"])}
            for package in packages
        ),
        key=lambda item: item["name"].lower(),
    )


def _run_import_smoke(python: Path) -> None:
    for imports in (
        "import atpiano.desktop_sidecar, onnxruntime",
        "import torch; assert not torch.cuda.is_available()",
    ):
        _run([python, "-I", "-B", "-c", imports])


def _read_ready_line(process: subprocess.Popen[str], timeout: float) -> str:
    if process.stdout is None:
        raise RuntimeError("Windows desktop sidecar stdout is unavailable")
    lines: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

    def read() -> None:
        try:
            lines.put(process.stdout.readline())
        except BaseException as error:  # pragma: no cover - subprocess boundary
            lines.put(error)

    threading.Thread(target=read, daemon=True).start()
    try:
        result = lines.get(timeout=timeout)
    except queue.Empty as error:
        raise RuntimeError("Windows desktop sidecar did not become ready") from error
    if isinstance(result, BaseException):
        raise RuntimeError("Windows desktop sidecar ready read failed") from result
    if not result:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError(f"Windows desktop sidecar exited before ready: {stderr[-1000:]}")
    return result


def smoke_sidecar(runtime_root: Path, working_root: Path) -> dict[str, Any]:
    token = hashlib.sha256(os.urandom(32)).hexdigest()
    workspace = working_root / "workspace"
    workspace.mkdir()
    python = runtime_root / "python.exe"
    model_pack = runtime_root / "model-pack" / "model-pack.json"
    fixture = runtime_root / "fixture" / "input.json"
    environment = dict(os.environ)
    environment.update(desktop_runtime_environment(workspace))
    environment.update(
        {
            "ATPIANO_DESKTOP_TOKEN": token,
            "ATPIANO_EXECUTION_BACKEND": EXECUTION_BACKEND,
            "CUDA_VISIBLE_DEVICES": "",
            "PATH": f"{runtime_root / 'bin'}{os.pathsep}{environment.get('PATH', '')}",
        }
    )
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "ATPIANO_BASIC_PITCH_MODEL",
        "ATPIANO_TRANSKUN_CHECKPOINT",
        "ATPIANO_TRANSKUN_CONFIG",
    ):
        environment.pop(name, None)
    process = subprocess.Popen(
        [
            str(python),
            "-I",
            "-B",
            "-m",
            "atpiano.desktop_sidecar",
            "--workspace",
            str(workspace),
            "--replay-manifest",
            str(fixture),
            "--model-pack",
            str(model_pack),
            "--expected-model-pack",
            MODEL_PACK_ID,
            "--expected-protocol",
            DESKTOP_PROTOCOL_VERSION,
            "--expected-contract",
            "atpiano.contract.v1",
            "--desktop-origin",
            "http://tauri.localhost",
        ],
        cwd=working_root,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready_line = _read_ready_line(process, 30)
        ready = json.loads(ready_line)
        base_url = f"http://127.0.0.1:{ready['port']}"
        try:
            urllib.request.urlopen(f"{base_url}/desktop/v1/handshake", timeout=2)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise RuntimeError("Windows sidecar returned an unexpected auth status") from error
        else:
            raise RuntimeError("Windows sidecar accepted an unauthenticated request")
        request = urllib.request.Request(
            f"{base_url}/desktop/v1/handshake",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": "http://tauri.localhost",
            },
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            handshake = json.load(response)
        if handshake["model_pack_sha256"] != ready["model_pack_sha256"]:
            raise RuntimeError("Windows sidecar model identity changed")
        assert process.stdin is not None
        process.stdin.close()
        if process.wait(timeout=15) != 0:
            raise RuntimeError("Windows desktop sidecar did not stop cleanly")
        stderr = process.stderr.read() if process.stderr is not None else ""
        if token in ready_line or token in stderr:
            raise RuntimeError("Windows desktop sidecar leaked its bearer token")
        return {
            "status": "passed",
            "protocol_version": ready["protocol_version"],
            "model_pack_id": ready["model_pack_id"],
            "score_available": handshake["score_available"],
            "unauthenticated_status": 401,
            "parent_eof_shutdown": True,
        }
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def audit_runtime(root: Path, repository: Path) -> dict[str, Any]:
    root = root.resolve()
    repository = repository.resolve()
    manifest_path = root / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": BUNDLE_MANIFEST_SCHEMA,
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "execution_backend": EXECUTION_BACKEND,
        "uv_lock_sha256": sha256_file(repository / "uv.lock"),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Windows desktop bundle identity changed")
    python = root / "python.exe"
    if not python.is_file():
        raise RuntimeError("Windows desktop Python is missing")
    pack = load_model_pack(root / "model-pack" / "model-pack.json")
    if (pack.platform, pack.architecture) != (PLATFORM, ARCHITECTURE):
        raise RuntimeError("Windows desktop model-pack identity changed")
    if manifest.get("model_pack_sha256") != model_pack_sha256(pack):
        raise RuntimeError("Windows desktop model-pack manifest changed")
    packages = _package_inventory(python)
    _validate_distributions(root, packages)
    if manifest.get("packages") != _package_identities(packages):
        raise RuntimeError("Windows desktop package inventory changed")
    _run_import_smoke(python)
    native = _audit_native(root)
    media = validate_media_runtime(root)
    score_support = audit_windows_score_support(root / "score-support", repository)
    if manifest.get("score_support") != _score_support_record(root / "score-support"):
        raise RuntimeError("Windows desktop score-support record changed")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("Windows desktop runtime contains a symbolic link")
        if path.is_dir() and path.name == "__pycache__":
            raise RuntimeError("Windows desktop runtime contains a Python cache")
        if path.name in {"MIDI2ScoreTF.ckpt", "MIDI2ScoreTransformer", "score-runtime"}:
            raise RuntimeError(f"forbidden score model payload: {path.name}")
    return {
        "schema_version": BUNDLE_AUDIT_SCHEMA,
        "created_at": utc_now(),
        "status": "passed",
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "execution_backend": EXECUTION_BACKEND,
        "manifest_sha256": sha256_file(manifest_path),
        "payload_sha256": _tree_sha256_without(root, {"bundle-manifest.json"}),
        "package_count": len(packages),
        "native_file_count": len(native),
        "native_files": native,
        "media": media,
        "score_support": score_support,
        "inventory": _inventory(root),
    }


def stage_windows_runtime(output: Path, repository: Path) -> dict[str, Any]:
    _require_windows_builder()
    output = output.resolve()
    repository = repository.resolve()
    if output != _expected_stage_root(repository):
        raise RuntimeError(f"refusing unexpected Windows desktop stage target: {output}")
    if output.exists():
        raise RuntimeError("Windows desktop stage target already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    uv = _uv_command()
    python_source, python_provenance = _managed_python(uv)
    temporary = Path(tempfile.mkdtemp(prefix=".windows-desktop-", dir=output.parent)).resolve()
    root = temporary / "desktop-runtime"
    try:
        shutil.copytree(python_source, root, symlinks=True)
        _stage_dependencies(root, repository, temporary, uv)
        pack = _stage_model_pack(_site_packages(root), root)
        _stage_fixture(root)
        media = stage_media_runtime(root)
        _prune_python(root)
        _materialize_runtime_symlinks(root)
        packages = _package_inventory(root / "python.exe")
        _validate_distributions(root, packages)
        _run_import_smoke(root / "python.exe")
        _audit_native(root)
        score_root = root / "score-support"
        _stage_score_support(score_root, repository)
        score_support = _score_support_record(score_root)
        sidecar = smoke_sidecar(root, temporary)
        _remove_tree(temporary / "workspace")
        manifest = {
            "schema_version": BUNDLE_MANIFEST_SCHEMA,
            "created_at": utc_now(),
            "platform": PLATFORM,
            "architecture": ARCHITECTURE,
            "execution_backend": EXECUTION_BACKEND,
            "python": python_provenance,
            "uv_lock_sha256": sha256_file(repository / "uv.lock"),
            "model_pack_id": pack.model_pack_id,
            "model_pack_sha256": model_pack_sha256(pack),
            "media": media,
            "sidecar_smoke": sidecar,
            "score_support": score_support,
            "internal_score_runtime": {
                "enabled": False,
                "internal_only": False,
                "public_distribution": False,
            },
            "packages": _package_identities(packages),
            "inventory_before_manifest": _inventory(root),
        }
        write_json(root / "bundle-manifest.json", manifest)
        result = audit_runtime(root, repository)
        os.replace(root, output)
        temporary.rmdir()
        return result
    finally:
        if temporary.exists():
            _remove_tree(temporary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m atpiano.windows_desktop_packaging")
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--repository", type=Path, default=_repository_root())
    stage.add_argument("--output", type=Path)
    stage.add_argument("--report", type=Path)
    audit = commands.add_parser("audit")
    audit.add_argument("--repository", type=Path, default=_repository_root())
    audit.add_argument("--root", type=Path, required=True)
    audit.add_argument("--report", type=Path)
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    repository = args.repository.resolve()
    if args.command == "stage":
        output = (args.output or _expected_stage_root(repository)).resolve()
        result = stage_windows_runtime(output, repository)
    else:
        result = audit_runtime(args.root, repository)
    if args.report is not None:
        write_json(args.report, result)
    print(json.dumps(result["inventory"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
