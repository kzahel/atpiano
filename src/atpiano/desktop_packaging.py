"""Reproducible staging and audit helpers for the Phase 5 macOS bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import select
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from atpiano.desktop import (
    MODEL_PACK_SCHEMA,
    ModelPack,
    desktop_runtime_environment,
)
from atpiano.desktop_media import (
    default_runtime_root as default_media_runtime_root,
)
from atpiano.desktop_media import validate_runtime as validate_media_runtime
from atpiano.musical_fixture import generate_musical_fixture
from atpiano.score_snapshot import (
    MIDI2SCORE_CHECKPOINT_SHA256,
    MIDI2SCORE_CHECKPOINT_URL,
    MIDI2SCORE_COMMIT,
    MIDI2SCORE_REPOSITORY,
    SCORE_RUNTIME_SCHEMA,
    inspect_score_runtime,
)
from atpiano.util import sha256_file, sha256_path, utc_now, write_json

PYTHON_KEY = "cpython-3.10.19-macos-aarch64-none"
PYTHON_VERSION = "3.10.19"
SCORE_PYTHON_KEY = "cpython-3.11.14-macos-aarch64-none"
SCORE_PYTHON_VERSION = "3.11.14"
MODEL_PACK_ID = "atpiano-cpu-models-2026.07"
BUNDLE_MANIFEST_SCHEMA = "atpiano.desktop-bundle.v1"
BUNDLE_AUDIT_SCHEMA = "atpiano.desktop-bundle-audit.v2"
INTERNAL_SCORE_RUNTIME_NAME = "score-runtime"
SCORE_SUPPORT_RUNTIME_NAME = "score-support"
SCORE_SUPPORT_LAYER_ID = "atpiano-midi2score-support-py311-2026.08"
SCORE_SUPPORT_SCHEMA = "atpiano.score-support.v1"
INTERNAL_SCORE_PAPER_URL = "https://zenodo.org/records/14877339"
SYSTEM_LOAD_PREFIXES = ("/System/Library/", "/usr/lib/")
FORBIDDEN_DISTRIBUTION_PREFIXES = (
    "cuda-",
    "nvidia-",
    "nvidia_",
    "rocm-",
    "triton",
)
FORBIDDEN_DEV_DISTRIBUTIONS = {
    "hypothesis",
    "mypy",
    "pytest",
    "ruff",
}
FORBIDDEN_TEST_NAMESPACES = {"test", "tests", "testing"}
REQUIRED_RUNTIME_TEST_NAMESPACES = {("torch", "testing")}
REQUIRED_SCORE_TEST_NAMESPACES = {
    ("music21", "test"),
    ("torch", "testing"),
}
FORBIDDEN_BASENAMES = {
    "MIDI2ScoreTF.ckpt",
    "midi2score-runtime",
    INTERNAL_SCORE_RUNTIME_NAME,
}
MODEL_ASSET_PATHS = {
    "basic_pitch": Path("basic_pitch/saved_models/icassp_2022/nmp.mlpackage"),
    "transkun_checkpoint": Path("transkun/pretrained/2.0.pt"),
    "transkun_config": Path("transkun/pretrained/2.0.conf"),
}
PRUNABLE_DIRECTORIES = (
    Path("include"),
    Path("share/man"),
    Path("lib/pkgconfig"),
    Path("lib/python3.10/test"),
    Path("lib/python3.10/idlelib"),
    Path("lib/python3.10/tkinter"),
    Path("lib/python3.10/turtledemo"),
)
PRUNABLE_PACKAGE_DIRECTORIES = (
    Path("torch/include"),
    Path("torch/share"),
    Path("pandas/tests"),
    Path("numba/tests"),
    Path("matplotlib/tests"),
    Path("coremltools/test"),
    Path("setuptools/tests"),
    Path("joblib/test"),
    Path("sklearn/tests"),
    Path("mpmath/tests"),
    Path("llvmlite/tests"),
    Path("pooch/tests"),
    Path("pkg_resources/tests"),
    Path("networkx/tests"),
    Path("fsspec/tests"),
    Path("importlib_resources/tests"),
    Path("numpy/tests"),
)


def _run(
    arguments: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(argument) for argument in arguments],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _expected_stage_root() -> Path:
    return (_repository_root() / "app" / "src-tauri" / "resources" / "desktop-runtime").resolve()


def _require_macos_arm64() -> None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("desktop packaging requires macOS arm64")


def _managed_python(
    *,
    key: str = PYTHON_KEY,
    version: str = PYTHON_VERSION,
) -> tuple[Path, dict[str, Any]]:
    result = _run(
        [
            "uv",
            "python",
            "list",
            version,
            "--only-installed",
            "--managed-python",
            "--output-format",
            "json",
        ],
        capture_output=True,
    )
    candidates = json.loads(result.stdout)
    selected = next(
        (candidate for candidate in candidates if candidate.get("key") == key),
        None,
    )
    if not isinstance(selected, dict) or not selected.get("path"):
        raise RuntimeError(f"uv-managed {key} is not installed")
    executable = Path(str(selected["path"])).resolve()
    runtime_root = executable.parent.parent
    build = (runtime_root / "BUILD").read_text(encoding="utf-8").strip()
    acquisition_url = (
        "https://github.com/astral-sh/python-build-standalone/"
        f"releases/download/{build}/"
        f"cpython-{version}%2B{build}-"
        "aarch64-apple-darwin-install_only_stripped.tar.gz"
    )
    return runtime_root, {
        "key": key,
        "version": version,
        "build": build,
        "acquisition_url": acquisition_url,
        "source_tree_sha256": sha256_path(runtime_root),
    }


def _site_packages(
    runtime_root: Path,
    *,
    python_version: str = "3.10",
) -> Path:
    return runtime_root / "lib" / f"python{python_version}" / "site-packages"


def _stage_dependencies(runtime_root: Path, repository: Path) -> None:
    requirements = runtime_root / ".requirements.lock"
    externally_managed = runtime_root / "lib" / "python3.10" / "EXTERNALLY-MANAGED"
    if externally_managed.is_file():
        externally_managed.unlink()
    _run(
        [
            "uv",
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
    python = runtime_root / "bin" / "python3"
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--requirements",
            requirements,
            "--require-hashes",
            "--strict",
            "--link-mode",
            "copy",
        ],
        cwd=repository,
    )
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--no-deps",
            "--reinstall",
            "--link-mode",
            "copy",
            repository,
        ],
        cwd=repository,
    )
    requirements.unlink()


def stage_model_pack(site_packages: Path, runtime_root: Path) -> ModelPack:
    pack_root = runtime_root / "model-pack"
    basic_pitch_source = site_packages / MODEL_ASSET_PATHS["basic_pitch"]
    transkun_source = site_packages / MODEL_ASSET_PATHS["transkun_checkpoint"]
    transkun_config_source = site_packages / MODEL_ASSET_PATHS["transkun_config"]
    for source in (
        basic_pitch_source,
        transkun_source,
        transkun_config_source,
    ):
        if not source.exists():
            raise RuntimeError(f"model asset is missing: {source.name}")

    basic_pitch = pack_root / "basic-pitch" / "nmp.mlpackage"
    transkun = pack_root / "transkun" / "2.0.pt"
    transkun_config = pack_root / "transkun" / "2.0.conf"
    shutil.copytree(basic_pitch_source, basic_pitch)
    transkun.parent.mkdir(parents=True)
    shutil.copy2(transkun_source, transkun)
    shutil.copy2(transkun_config_source, transkun_config)
    manifest = ModelPack.model_validate(
        {
            "schema_version": MODEL_PACK_SCHEMA,
            "model_pack_id": MODEL_PACK_ID,
            "platform": "macos",
            "architecture": "arm64",
            "execution_backend": "cpu",
            "assets": [
                {
                    "asset_id": "basic-pitch-icassp-2022",
                    "adapter": "atpiano-basic-pitch-live-window-v1",
                    "package": "basic-pitch",
                    "package_version": "0.4.0",
                    "path": "basic-pitch/nmp.mlpackage",
                    "sha256": sha256_path(basic_pitch),
                    "kind": "directory",
                },
                {
                    "asset_id": "transkun-2.0",
                    "adapter": "atpiano-transkun-trailing-v1",
                    "package": "transkun",
                    "package_version": "2.0.1",
                    "path": "transkun/2.0.pt",
                    "sha256": sha256_file(transkun),
                    "kind": "file",
                },
                {
                    "asset_id": "transkun-2.0-config",
                    "adapter": "atpiano-transkun-trailing-v1",
                    "package": "transkun",
                    "package_version": "2.0.1",
                    "path": "transkun/2.0.conf",
                    "sha256": sha256_file(transkun_config),
                    "kind": "file",
                },
            ],
        }
    )
    write_json(
        pack_root / "model-pack.json",
        manifest.model_dump(mode="json"),
    )
    shutil.rmtree(
        site_packages / "basic_pitch" / "saved_models",
    )
    shutil.rmtree(site_packages / "transkun" / "pretrained")
    return manifest


def _otool_dependencies(path: Path) -> list[str]:
    result = _run(["otool", "-L", path], capture_output=True)
    dependencies: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        stripped = line.strip()
        if stripped:
            dependencies.append(stripped.split(" (", 1)[0])
    return dependencies


def _is_system_load_path(path: str) -> bool:
    return path.startswith(SYSTEM_LOAD_PREFIXES)


def bundle_media_tools(
    runtime_root: Path,
    *,
    media_runtime_root: Path | None = None,
) -> dict[str, Any]:
    media_root = (media_runtime_root or default_media_runtime_root()).resolve()
    manifest = validate_media_runtime(media_root, exercise=False)
    binaries = runtime_root / "bin"
    libraries = runtime_root / "lib" / "media"
    libraries.mkdir(parents=True, exist_ok=True)
    for name in ("ffmpeg", "ffprobe"):
        source = media_root / "bin" / name
        destination = binaries / name
        shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
    for source in sorted((media_root / "lib" / "media").glob("*.dylib")):
        shutil.copy2(source, libraries / source.name)
    licenses = runtime_root / "share" / "licenses" / "media"
    shutil.copytree(media_root / "share" / "licenses" / "media", licenses)
    shutil.copy2(
        media_root / "build-manifest.json",
        runtime_root / "media-build-manifest.json",
    )
    return {
        "build_identity": manifest["build_identity"],
        "ffmpeg_version": manifest["ffmpeg_version"],
        "configuration": manifest["configuration"],
        "bundled_library_count": len(list(libraries.glob("*.dylib"))),
        "sources": manifest["sources"],
        "license": manifest["license"],
        "notices": "share/licenses/media/THIRD_PARTY_NOTICES.md",
        "build_manifest": "media-build-manifest.json",
    }


def _prune_runtime(runtime_root: Path) -> None:
    site_packages = _site_packages(runtime_root)
    for relative in PRUNABLE_DIRECTORIES:
        target = runtime_root / relative
        if target.is_dir():
            shutil.rmtree(target)
    for relative in PRUNABLE_PACKAGE_DIRECTORIES:
        target = site_packages / relative
        if target.is_dir():
            shutil.rmtree(target)
    _prune_distribution_test_material(site_packages)
    for direct_url in site_packages.rglob("direct_url.json"):
        direct_url.unlink()
    for cache in sorted(
        runtime_root.rglob("__pycache__"),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if cache.is_dir():
            shutil.rmtree(cache)
    for bytecode in runtime_root.rglob("*.py[co]"):
        bytecode.unlink()
    keep = {"python", "python3", "python3.10", "ffmpeg", "ffprobe"}
    for entry in (runtime_root / "bin").iterdir():
        if entry.name not in keep:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()


def _prune_distribution_test_material(
    site_packages: Path,
    *,
    required_namespaces: set[tuple[str, ...]] | None = None,
) -> None:
    required = required_namespaces or REQUIRED_RUNTIME_TEST_NAMESPACES
    candidates = sorted(
        (
            path
            for path in site_packages.rglob("*")
            if path.is_dir() and path.name.lower() in FORBIDDEN_TEST_NAMESPACES
        ),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for candidate in candidates:
        relative = candidate.relative_to(site_packages)
        if relative.parts in required:
            continue
        if candidate.is_dir():
            shutil.rmtree(candidate)


def _package_inventory(
    runtime_root: Path,
    *,
    python: Path | None = None,
) -> list[dict[str, Any]]:
    script = """
import importlib.metadata as metadata
import json
items = []
for distribution in metadata.distributions():
    value = distribution.metadata
    classifiers = value.get_all("Classifier") or []
    license_classifiers = [
        item for item in classifiers if item.startswith("License ::")
    ]
    installed = []
    for relative in distribution.files or []:
        path = distribution.locate_file(relative)
        try:
            if path.is_file():
                installed.append(path.stat().st_size)
        except OSError:
            continue
    items.append({
        "name": value.get("Name", distribution.name),
        "version": distribution.version,
        "license": value.get("License"),
        "license_expression": value.get("License-Expression"),
        "license_classifiers": license_classifiers,
        "installed_bytes": sum(installed),
        "installed_file_count": len(installed),
    })
print(json.dumps(sorted(items, key=lambda item: item["name"].lower())))
"""
    result = _run(
        [
            python or runtime_root / "bin" / "python3",
            "-I",
            "-B",
            "-c",
            script,
        ],
        capture_output=True,
    )
    return json.loads(result.stdout)


def _direct_url_inventory(site_packages: Path) -> list[dict[str, Any]]:
    sources = []
    for path in sorted(site_packages.glob("*.dist-info/direct_url.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        sources.append(
            {
                "distribution": path.parent.name.removesuffix(".dist-info"),
                "source": document,
            }
        )
    return sources


def _remove_runtime_caches(root: Path) -> None:
    for cache in sorted(
        root.rglob("__pycache__"),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if cache.is_dir():
            shutil.rmtree(cache)
    for bytecode in root.rglob("*.py[co]"):
        bytecode.unlink()


def _prune_internal_score_python(python_root: Path) -> None:
    site_packages = _site_packages(
        python_root,
        python_version="3.11",
    )
    relative_directories = (
        Path("include"),
        Path("share/man"),
        Path("lib/pkgconfig"),
        Path("lib/python3.11/test"),
        Path("lib/python3.11/idlelib"),
        Path("lib/python3.11/tkinter"),
        Path("lib/python3.11/turtledemo"),
    )
    for relative in relative_directories:
        target = python_root / relative
        if target.is_dir():
            shutil.rmtree(target)
    for relative in PRUNABLE_PACKAGE_DIRECTORIES:
        target = site_packages / relative
        if target.is_dir():
            shutil.rmtree(target)
    _prune_distribution_test_material(
        site_packages,
        required_namespaces=REQUIRED_SCORE_TEST_NAMESPACES,
    )
    for virtualenv_file in ("_virtualenv.pth", "_virtualenv.py"):
        (site_packages / virtualenv_file).unlink(missing_ok=True)
    for direct_url in site_packages.rglob("direct_url.json"):
        direct_url.unlink()
    _remove_runtime_caches(python_root)
    keep = {"python", "python3", "python3.11"}
    for entry in (python_root / "bin").iterdir():
        if entry.name not in keep:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()


def _materialize_runtime_symlinks(root: Path) -> None:
    resolved_root = root.resolve()
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_symlink():
            continue
        target = path.resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise RuntimeError(f"score support symlink escapes its root: {path}")
        if not target.is_file():
            raise RuntimeError(f"score support symlink is not a regular file: {path}")
        materialized = path.with_name(f".{path.name}.materialized")
        shutil.copy2(target, materialized)
        path.unlink()
        materialized.replace(path)


def _support_vcs_inventory(site_packages: Path) -> list[dict[str, Any]]:
    sources = _direct_url_inventory(site_packages)
    expected = {
        "https://github.com/TimFelixBeyer/music21": (
            "0ed70bb38f2017dc04cb19aada24e88a141517e2"
        ),
        "https://github.com/TimFelixBeyer/amtevaluation.github.io": (
            "4ef1165edda1f719068c4c699bd8ab2076e4d7ec"
        ),
        "https://github.com/TimFelixBeyer/ScoreTransformer": (
            "934a228ee33e5731dde6c7b22a2cf13a0825b18f"
        ),
    }
    observed: dict[str, str] = {}
    for source in sources:
        document = source.get("source")
        if not isinstance(document, dict):
            continue
        vcs = document.get("vcs_info")
        if isinstance(vcs, dict) and vcs.get("vcs") == "git":
            observed[str(document.get("url"))] = str(vcs.get("commit_id"))
    if observed != expected:
        raise RuntimeError("score support VCS provenance differs from its pinned inputs")
    return sources


def _sha256_tree_without(root: Path, excluded: set[str]) -> str:
    digest = hashlib.sha256()
    files = (item for item in root.rglob("*") if item.is_file())
    for child in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = child.relative_to(root).as_posix()
        if relative in excluded:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(child)))
    return digest.hexdigest()


def stage_score_support(runtime_root: Path, repository: Path) -> dict[str, Any]:
    score_root = runtime_root / SCORE_SUPPORT_RUNTIME_NAME
    registry_lock = repository / "desktop-score" / "support-requirements.lock"
    vcs_requirements = repository / "desktop-score" / "support-vcs-requirements.txt"
    python_source, python_provenance = _managed_python(
        key=SCORE_PYTHON_KEY,
        version=SCORE_PYTHON_VERSION,
    )
    python_root = score_root / ".venv"
    shutil.copytree(python_source, python_root, symlinks=True)
    site_packages = _site_packages(python_root, python_version="3.11")
    if site_packages.exists():
        shutil.rmtree(site_packages)
    externally_managed = python_root / "lib" / "python3.11" / "EXTERNALLY-MANAGED"
    externally_managed.unlink(missing_ok=True)
    python = python_root / "bin" / "python3.11"
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--requirements",
            registry_lock,
            "--require-hashes",
            "--exact",
            "--strict",
            "--link-mode",
            "copy",
        ],
        cwd=repository,
    )
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--requirements",
            vcs_requirements,
            "--no-deps",
            "--strict",
            "--link-mode",
            "copy",
        ],
        cwd=repository,
    )
    vcs_sources = _support_vcs_inventory(site_packages)
    _prune_internal_score_python(python_root)
    relocated_native = relocate_runtime_native(python_root, python_source)
    _materialize_runtime_symlinks(score_root)
    packages = _package_inventory(python_root, python=python_root / "bin" / "python")
    _audit_distributions(score_root, packages)
    _audit_symlinks(score_root)
    _audit_native(score_root)
    for imports in (
        "import torch, transformers, lightning, music21",
        "import numba, pretty_midi, score_transformer, muster",
    ):
        _run([python_root / "bin" / "python", "-I", "-B", "-c", imports])
    python_version = _run(
        [python_root / "bin" / "python", "--version"],
        capture_output=True,
    ).stdout.strip()
    packages_document = {
        "schema_version": "atpiano.score-support-packages.v1",
        "support_layer_id": SCORE_SUPPORT_LAYER_ID,
        "python": python_version,
        "python_provenance": python_provenance,
        "registry_requirements": {
            "path": "desktop-score/support-requirements.lock",
            "sha256": sha256_file(registry_lock),
        },
        "vcs_requirements": {
            "path": "desktop-score/support-vcs-requirements.txt",
            "sha256": sha256_file(vcs_requirements),
        },
        "vcs_sources": vcs_sources,
        "relocated_native_files": relocated_native,
        "packages": packages,
    }
    packages_path = score_root / "packages.json"
    write_json(packages_path, packages_document)
    manifest = {
        "schema_version": SCORE_SUPPORT_SCHEMA,
        "support_layer_id": SCORE_SUPPORT_LAYER_ID,
        "platform": "macos",
        "architecture": "arm64",
        "execution_backend": "cpu",
        "python_version": SCORE_PYTHON_VERSION,
        "requirements_sha256": sha256_file(registry_lock),
        "vcs_requirements_sha256": sha256_file(vcs_requirements),
        "packages_sha256": sha256_file(packages_path),
        "payload_sha256": _sha256_tree_without(score_root, {"support-manifest.json"}),
        "package_count": len(packages),
        "payload_bytes": _path_size(score_root),
    }
    write_json(score_root / "support-manifest.json", manifest)
    return {
        "enabled": True,
        "relative_path": SCORE_SUPPORT_RUNTIME_NAME,
        "manifest_sha256": sha256_file(score_root / "support-manifest.json"),
        **manifest,
    }


def stage_internal_score_runtime(
    runtime_root: Path,
    source_runtime: Path,
) -> dict[str, Any]:
    source_runtime = source_runtime.resolve()
    source_state = inspect_score_runtime(source_runtime)
    if not source_state["available"]:
        raise RuntimeError(f"internal score runtime is unavailable: {source_state['error']}")
    source_repository = source_runtime / "MIDI2ScoreTransformer"
    source_checkpoint = source_runtime / "MIDI2ScoreTF.ckpt"
    source_python_packages = source_runtime / ".venv" / "lib" / "python3.11" / "site-packages"
    if not source_python_packages.is_dir():
        raise RuntimeError("internal score runtime Python packages are missing")
    repository_commit = _run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_repository,
        capture_output=True,
    ).stdout.strip()
    if repository_commit != MIDI2SCORE_COMMIT:
        raise RuntimeError("internal score repository differs from the pinned commit")
    if sha256_file(source_checkpoint) != MIDI2SCORE_CHECKPOINT_SHA256:
        raise RuntimeError("internal score checkpoint differs from the pinned hash")

    score_root = runtime_root / INTERNAL_SCORE_RUNTIME_NAME
    python_source, python_provenance = _managed_python(
        key=SCORE_PYTHON_KEY,
        version=SCORE_PYTHON_VERSION,
    )
    python_root = score_root / ".venv"
    shutil.copytree(python_source, python_root, symlinks=True)
    staged_site_packages = _site_packages(
        python_root,
        python_version="3.11",
    )
    if staged_site_packages.exists():
        shutil.rmtree(staged_site_packages)
    shutil.copytree(
        source_python_packages,
        staged_site_packages,
        symlinks=True,
    )
    vcs_sources = _direct_url_inventory(staged_site_packages)
    shutil.copytree(
        source_repository,
        score_root / "MIDI2ScoreTransformer",
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            "*.pyc",
            "*.pyo",
        ),
    )
    shutil.copy2(source_checkpoint, score_root / "MIDI2ScoreTF.ckpt")
    _prune_internal_score_python(python_root)
    relocated_native = relocate_runtime_native(
        python_root,
        python_source,
    )
    python = python_root / "bin" / "python"
    packages = _package_inventory(python_root, python=python)
    _audit_distributions(
        score_root,
        packages,
        allow_internal_score_runtime=True,
    )
    for imports in (
        "import torch, transformers, lightning, music21",
        "import numba, pretty_midi, score_transformer",
    ):
        _run([python, "-I", "-B", "-c", imports])
    python_version = _run(
        [python, "--version"],
        capture_output=True,
    ).stdout.strip()
    manifest = {
        "schema_version": SCORE_RUNTIME_SCHEMA,
        "created_at": utc_now(),
        "internal_use_only": True,
        "internal_only": True,
        "public_distribution": False,
        "license": {
            "status": "provisional-unconfirmed",
            "checkpoint_assumption": "CC-BY-4.0",
            "paper_license": "CC-BY-4.0",
            "paper_record": INTERNAL_SCORE_PAPER_URL,
            "source_license": "unconfirmed",
            "release_gate": ("confirm source and checkpoint rights before distribution"),
        },
        "python": python_version,
        "python_provenance": python_provenance,
        "repository": {
            "url": MIDI2SCORE_REPOSITORY,
            "commit": repository_commit,
            "tree_sha256": sha256_path(score_root / "MIDI2ScoreTransformer"),
        },
        "checkpoint": {
            "url": MIDI2SCORE_CHECKPOINT_URL,
            "sha256": sha256_file(score_root / "MIDI2ScoreTF.ckpt"),
            "bytes": (score_root / "MIDI2ScoreTF.ckpt").stat().st_size,
        },
        "execution": {
            "device": "cpu",
            "beautifulsoup4": "4.13.4",
            "transformers": "4.44.2",
        },
        "vcs_sources": vcs_sources,
        "relocated_native_files": relocated_native,
        "packages": packages,
    }
    write_json(score_root / "runtime.json", manifest)
    if not inspect_score_runtime(score_root)["available"]:
        raise RuntimeError("staged internal score runtime failed its manifest contract")
    return {
        "enabled": True,
        "internal_only": True,
        "public_distribution": False,
        "relative_path": INTERNAL_SCORE_RUNTIME_NAME,
        "manifest_sha256": sha256_file(score_root / "runtime.json"),
        "checkpoint_sha256": MIDI2SCORE_CHECKPOINT_SHA256,
        "repository_commit": MIDI2SCORE_COMMIT,
        "installed_bytes": _path_size(score_root),
        "package_count": len(packages),
    }


def _stage_fixture(runtime_root: Path) -> None:
    fixture = runtime_root / "fixture"
    manifest = generate_musical_fixture(fixture)
    manifest["created_at"] = "2026-07-27T00:00:00+00:00"
    write_json(fixture / "input.json", manifest)


def _path_size(path: Path) -> int:
    return sum(
        child.lstat().st_size for child in path.rglob("*") if child.is_file() or child.is_symlink()
    )


def inventory(root: Path) -> dict[str, Any]:
    files = [path for path in root.rglob("*") if path.is_file() or path.is_symlink()]
    largest = sorted(
        (
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.lstat().st_size,
            }
            for path in files
        ),
        key=lambda item: int(item["bytes"]),
        reverse=True,
    )[:10]
    top_level = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        top_level.append(
            {
                "path": child.name,
                "bytes": (_path_size(child) if child.is_dir() else child.lstat().st_size),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": sum(path.lstat().st_size for path in files),
        "top_level": top_level,
        "largest_files": largest,
    }


def _is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            magic = handle.read(4)
    except OSError:
        return False
    return magic in {
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe",
        b"\xbe\xba\xfe\xca",
        b"\xca\xfe\xba\xbf",
        b"\xbf\xba\xfe\xca",
    }


def _native_candidates(root: Path) -> list[Path]:
    candidates = []
    for path in root.rglob("*"):
        if (
            path.is_file()
            and not path.is_symlink()
            and (path.suffix in {".dylib", ".so"} or os.access(path, os.X_OK))
            and _is_macho(path)
        ):
            candidates.append(path)
    return candidates


def _loader_path(binary: Path, target: Path) -> str:
    relative = os.path.relpath(target, binary.parent)
    return f"@loader_path/{Path(relative).as_posix()}"


def _otool_id(path: Path) -> str | None:
    result = _run(["otool", "-D", path], capture_output=True)
    lines = [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
    return lines[0] if lines else None


def relocate_runtime_native(
    runtime_root: Path,
    python_source: Path,
) -> list[str]:
    modified = []
    for binary in _native_candidates(runtime_root):
        description = _run(
            ["file", "-b", binary],
            capture_output=True,
        ).stdout
        needs_thinning = "arm64" in description and "x86_64" in description
        if needs_thinning:
            original_mode = binary.stat().st_mode
            thinned = binary.with_name(f"{binary.name}.arm64")
            _run(
                [
                    "lipo",
                    binary,
                    "-thin",
                    "arm64",
                    "-output",
                    thinned,
                ],
                capture_output=True,
            )
            os.replace(thinned, binary)
            os.chmod(binary, original_mode)
        changes: list[tuple[str, str]] = []
        for dependency in _otool_dependencies(binary):
            if not dependency.startswith(str(python_source)):
                continue
            relative = Path(dependency).relative_to(python_source)
            target = runtime_root / relative
            if not target.is_file():
                raise RuntimeError(f"copied Python dependency is missing: {relative.as_posix()}")
            changes.append((dependency, _loader_path(binary, target)))
        install_id = _otool_id(binary)
        needs_id = install_id is not None and install_id.startswith(str(python_source))
        for original, replacement in changes:
            _run(
                [
                    "install_name_tool",
                    "-change",
                    original,
                    replacement,
                    binary,
                ],
                capture_output=True,
            )
        if needs_id:
            _run(
                [
                    "install_name_tool",
                    "-id",
                    _loader_path(binary, binary),
                    binary,
                ],
                capture_output=True,
            )
        if needs_thinning or changes or needs_id:
            _run(
                ["codesign", "--force", "--sign", "-", binary],
                capture_output=True,
            )
            modified.append(binary.relative_to(runtime_root).as_posix())
    return modified


def _audit_symlinks(root: Path) -> list[str]:
    links = []
    resolved_root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        target = path.resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise RuntimeError(f"bundle symlink escapes its root: {path}")
        links.append(path.relative_to(root).as_posix())
    return links


def _audit_distributions(
    root: Path,
    packages: list[dict[str, Any]],
    *,
    allow_internal_score_runtime: bool = False,
) -> None:
    for package in packages:
        normalized = str(package["name"]).lower().replace("_", "-")
        if normalized.startswith(FORBIDDEN_DISTRIBUTION_PREFIXES):
            raise RuntimeError(f"forbidden accelerator package: {package['name']}")
        if normalized in FORBIDDEN_DEV_DISTRIBUTIONS:
            raise RuntimeError(f"forbidden development package: {package['name']}")
    for path in root.rglob("*"):
        if path.name in FORBIDDEN_BASENAMES:
            if allow_internal_score_runtime and INTERNAL_SCORE_RUNTIME_NAME in path.parts:
                continue
            raise RuntimeError(f"forbidden score runtime asset: {path.name}")


def _internal_score_policy(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    raw = manifest.get("internal_score_runtime")
    if not isinstance(raw, dict):
        return {
            "enabled": False,
            "internal_only": False,
            "public_distribution": False,
        }
    enabled = raw.get("enabled") is True
    internal_only = raw.get("internal_only") is True
    public_distribution = raw.get("public_distribution") is True
    if enabled and (not internal_only or public_distribution):
        raise RuntimeError("internal score runtime policy is unsafe for this build")
    return {
        **raw,
        "enabled": enabled,
        "internal_only": internal_only,
        "public_distribution": public_distribution,
    }


def _audit_internal_score_runtime(
    runtime_root: Path,
) -> dict[str, Any]:
    score_root = runtime_root / INTERNAL_SCORE_RUNTIME_NAME
    state = inspect_score_runtime(score_root)
    if not state["available"]:
        raise RuntimeError(f"internal score runtime failed validation: {state['error']}")
    runtime_manifest = state["manifest"]
    license_state = runtime_manifest.get("license", {})
    if (
        runtime_manifest.get("internal_only") is not True
        or runtime_manifest.get("public_distribution") is not False
        or not isinstance(license_state, dict)
        or license_state.get("status") != "provisional-unconfirmed"
        or license_state.get("checkpoint_assumption") != "CC-BY-4.0"
        or license_state.get("source_license") != "unconfirmed"
    ):
        raise RuntimeError("internal score runtime lacks its provisional license gate")
    checkpoint = score_root / "MIDI2ScoreTF.ckpt"
    if sha256_file(checkpoint) != MIDI2SCORE_CHECKPOINT_SHA256:
        raise RuntimeError("internal score runtime checkpoint hash mismatch")
    repository = score_root / "MIDI2ScoreTransformer"
    if sha256_path(repository) != runtime_manifest["repository"].get("tree_sha256"):
        raise RuntimeError("internal score runtime source tree hash mismatch")
    if (repository / ".git").exists():
        raise RuntimeError("internal score runtime includes repository history")
    python = score_root / ".venv" / "bin" / "python"
    packages = _package_inventory(
        score_root / ".venv",
        python=python,
    )
    _audit_distributions(
        score_root,
        packages,
        allow_internal_score_runtime=True,
    )
    return {
        "status": "passed",
        "relative_path": INTERNAL_SCORE_RUNTIME_NAME,
        "manifest_sha256": sha256_file(score_root / "runtime.json"),
        "checkpoint_sha256": MIDI2SCORE_CHECKPOINT_SHA256,
        "repository_commit": MIDI2SCORE_COMMIT,
        "package_count": len(packages),
        "largest_packages": sorted(
            (
                {
                    "name": package["name"],
                    "version": package["version"],
                    "installed_bytes": package["installed_bytes"],
                }
                for package in packages
            ),
            key=lambda item: item["installed_bytes"],
            reverse=True,
        )[:10],
        "license": license_state,
    }


def _score_support_payload_bytes(score_root: Path) -> int:
    return sum(
        path.lstat().st_size
        for path in score_root.rglob("*")
        if (path.is_file() or path.is_symlink())
        and path.relative_to(score_root).as_posix() != "support-manifest.json"
    )


def refresh_score_support_manifest(runtime_root: Path) -> dict[str, Any]:
    score_root = runtime_root / SCORE_SUPPORT_RUNTIME_NAME
    manifest_path = score_root / "support-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packages_sha256"] = sha256_file(score_root / "packages.json")
    manifest["payload_sha256"] = _sha256_tree_without(
        score_root,
        {"support-manifest.json"},
    )
    manifest["payload_bytes"] = _score_support_payload_bytes(score_root)
    write_json(manifest_path, manifest)
    bundle_manifest_path = runtime_root / "bundle-manifest.json"
    if bundle_manifest_path.is_file():
        bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))
        score_support = bundle_manifest.get("score_support")
        if not isinstance(score_support, dict):
            raise RuntimeError("desktop bundle score support record is missing")
        bundle_manifest["score_support"] = {
            **score_support,
            **manifest,
            "manifest_sha256": sha256_file(manifest_path),
        }
        write_json(bundle_manifest_path, bundle_manifest)
    return manifest


def _audit_score_support(runtime_root: Path) -> dict[str, Any]:
    repository = _repository_root()
    score_root = runtime_root / SCORE_SUPPORT_RUNTIME_NAME
    manifest_path = score_root / "support-manifest.json"
    packages_path = score_root / "packages.json"
    if not manifest_path.is_file() or not packages_path.is_file():
        raise RuntimeError("desktop score support manifests are missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_manifest = json.loads(
        (runtime_root / "bundle-manifest.json").read_text(encoding="utf-8")
    )
    bundle_score_support = bundle_manifest.get("score_support")
    if not isinstance(bundle_score_support, dict):
        raise RuntimeError("desktop bundle score support record is missing")
    expected = {
        "schema_version": SCORE_SUPPORT_SCHEMA,
        "support_layer_id": SCORE_SUPPORT_LAYER_ID,
        "platform": "macos",
        "architecture": "arm64",
        "execution_backend": "cpu",
        "python_version": SCORE_PYTHON_VERSION,
        "requirements_sha256": sha256_file(
            repository / "desktop-score" / "support-requirements.lock"
        ),
        "vcs_requirements_sha256": sha256_file(
            repository / "desktop-score" / "support-vcs-requirements.txt"
        ),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("desktop score support identity differs from its contract")
    if any(bundle_score_support.get(key) != value for key, value in manifest.items()):
        raise RuntimeError("desktop bundle score support record changed")
    if bundle_score_support.get("manifest_sha256") != sha256_file(manifest_path):
        raise RuntimeError("desktop bundle score support manifest hash changed")
    if manifest.get("packages_sha256") != sha256_file(packages_path):
        raise RuntimeError("desktop score support package inventory changed")
    if manifest.get("payload_sha256") != _sha256_tree_without(
        score_root,
        {"support-manifest.json"},
    ):
        raise RuntimeError("desktop score support payload changed")
    if manifest.get("payload_bytes") != _score_support_payload_bytes(score_root):
        raise RuntimeError("desktop score support byte count changed")
    if _audit_symlinks(score_root):
        raise RuntimeError("desktop score support contains a symbolic link")
    python = score_root / ".venv" / "bin" / "python"
    packages = _package_inventory(score_root / ".venv", python=python)
    _audit_distributions(score_root, packages)
    packages_document = json.loads(packages_path.read_text(encoding="utf-8"))
    recorded = packages_document.get("packages")
    recorded_identities = {
        (str(package.get("name")), str(package.get("version")))
        for package in recorded
        if isinstance(package, dict)
    } if isinstance(recorded, list) else set()
    actual_identities = {
        (str(package["name"]), str(package["version"])) for package in packages
    }
    if recorded_identities != actual_identities:
        raise RuntimeError("desktop score support package identities changed")
    if manifest.get("package_count") != len(packages):
        raise RuntimeError("desktop score support package count changed")
    return {
        "status": "passed",
        "relative_path": SCORE_SUPPORT_RUNTIME_NAME,
        "manifest_sha256": sha256_file(manifest_path),
        "payload_sha256": manifest["payload_sha256"],
        "installed_bytes": _path_size(score_root),
        "package_count": len(packages),
        "largest_packages": sorted(
            (
                {
                    "name": package["name"],
                    "version": package["version"],
                    "installed_bytes": package["installed_bytes"],
                }
                for package in packages
            ),
            key=lambda item: item["installed_bytes"],
            reverse=True,
        )[:10],
    }


def _audit_native(root: Path) -> list[dict[str, Any]]:
    native = []
    for path in _native_candidates(root):
        description = _run(
            ["file", "-b", path],
            capture_output=True,
        ).stdout.strip()
        if "arm64" not in description or "x86_64" in description:
            raise RuntimeError(f"native file is not arm64-only: {path}")
        dependencies = _otool_dependencies(path)
        install_id = _otool_id(path)
        for dependency in dependencies:
            if dependency == install_id:
                continue
            if dependency.startswith(
                ("@loader_path/", "@rpath/", "@executable_path/")
            ) or _is_system_load_path(dependency):
                continue
            candidate = Path(dependency)
            if candidate == root.resolve() or root.resolve() in candidate.parents:
                continue
            raise RuntimeError(f"native dependency escapes the bundle: {dependency}")
        native.append(
            {
                "path": path.relative_to(root).as_posix(),
                "description": description,
                "dependencies": dependencies,
            }
        )
    return native


def component_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    runtime_root = (
        root / "Contents" / "Resources" / "desktop-runtime" if root.suffix == ".app" else root
    )
    categories: dict[str, dict[str, int]] = {}

    def record(category: str, path: Path) -> None:
        entry = categories.setdefault(
            category,
            {"bytes": 0, "file_count": 0},
        )
        entry["bytes"] += path.lstat().st_size
        entry["file_count"] += 1

    test_material = []
    runtime_required_testing = []
    for path in root.rglob("*"):
        if not (path.is_file() or path.is_symlink()):
            continue
        try:
            runtime_relative = path.relative_to(runtime_root)
        except ValueError:
            relative = path.relative_to(root)
            if relative.parts[:2] == ("Contents", "MacOS"):
                category = "rust_shell_and_embedded_frontend"
            elif relative.parts[:2] == ("Contents", "Resources"):
                category = "app_resources"
            else:
                category = "app_metadata"
        else:
            category = _runtime_component_category(runtime_relative.parts)
            if category == "python_packages":
                parts = runtime_relative.parts
                lowered = {part.lower() for part in parts[3:]}
                if lowered & FORBIDDEN_TEST_NAMESPACES:
                    package_parts = parts[3:]
                    if package_parts[:2] in REQUIRED_RUNTIME_TEST_NAMESPACES:
                        runtime_required_testing.append(path)
                    else:
                        test_material.append(path)
        record(category, path)

    installed_bytes = sum(entry["bytes"] for entry in categories.values())
    native = _native_candidates(root)
    test_largest = sorted(
        (
            {
                "path": path.relative_to(runtime_root).as_posix(),
                "bytes": path.lstat().st_size,
            }
            for path in test_material
        ),
        key=lambda item: item["bytes"],
        reverse=True,
    )[:10]
    return {
        "installed_bytes": installed_bytes,
        "categories": categories,
        "native_files": {
            "bytes": sum(path.lstat().st_size for path in native),
            "file_count": len(native),
            "overlaps_reconciled_categories": True,
        },
        "distribution_test_material": {
            "bytes": sum(path.lstat().st_size for path in test_material),
            "file_count": len(test_material),
            "largest_files": test_largest,
            "policy": ("test namespaces and development distributions excluded"),
        },
        "runtime_required_testing": {
            "bytes": sum(path.lstat().st_size for path in runtime_required_testing),
            "file_count": len(runtime_required_testing),
            "namespaces": [
                "/".join(namespace) for namespace in sorted(REQUIRED_RUNTIME_TEST_NAMESPACES)
            ],
            "policy": (
                "retained only where the package imports its public "
                "or private testing namespace during ordinary runtime "
                "startup"
            ),
        },
    }


def _runtime_component_category(parts: tuple[str, ...]) -> str:
    if parts[:1] == (INTERNAL_SCORE_RUNTIME_NAME,):
        return "internal_score_runtime"
    if parts[:1] == (SCORE_SUPPORT_RUNTIME_NAME,):
        return "score_support"
    if parts[:1] == ("model-pack",):
        return "model_pack"
    if parts[:1] == ("fixture",):
        return "golden_replay_fixture"
    if parts[:3] == (
        "lib",
        "python3.10",
        "site-packages",
    ):
        return "python_packages"
    if parts[:2] == ("lib", "media") or parts[:3] == (
        "share",
        "licenses",
        "media",
    ) or parts in {
        ("bin", "ffmpeg"),
        ("bin", "ffprobe"),
        ("media-build-manifest.json",),
    }:
        return "media_tools"
    return "python_runtime_and_manifest"


def archive_component_inventory(archive: Path) -> dict[str, Any]:
    categories: dict[str, dict[str, int]] = {}
    entry_count = 0
    payload_compressed_bytes = 0
    payload_uncompressed_bytes = 0
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            entry_count += 1
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            if not parts or parts[0] == "__MACOSX":
                category = "archive_metadata"
            else:
                try:
                    app_index = parts.index("Atpiano.app")
                except ValueError:
                    category = "archive_metadata"
                else:
                    relative = parts[app_index + 1 :]
                    runtime_prefix = (
                        "Contents",
                        "Resources",
                        "desktop-runtime",
                    )
                    if relative[:3] == runtime_prefix:
                        category = _runtime_component_category(relative[3:])
                    elif relative[:2] == ("Contents", "MacOS"):
                        category = "rust_shell_and_embedded_frontend"
                    elif relative[:2] == ("Contents", "Resources"):
                        category = "app_resources"
                    else:
                        category = "app_metadata"
            entry = categories.setdefault(
                category,
                {
                    "compressed_bytes": 0,
                    "uncompressed_bytes": 0,
                    "file_count": 0,
                },
            )
            entry["compressed_bytes"] += info.compress_size
            entry["uncompressed_bytes"] += info.file_size
            entry["file_count"] += 1
            payload_compressed_bytes += info.compress_size
            payload_uncompressed_bytes += info.file_size
    archive_bytes = archive.stat().st_size
    return {
        "archive_bytes": archive_bytes,
        "entry_count": entry_count,
        "payload_compressed_bytes": payload_compressed_bytes,
        "payload_uncompressed_bytes": payload_uncompressed_bytes,
        "container_overhead_bytes": (archive_bytes - payload_compressed_bytes),
        "categories": categories,
    }


def _audit_anonymous_caches(root: Path) -> list[str]:
    forbidden = {"__pycache__", ".cache", "pip-cache", "uv-cache"}
    found = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir() and path.name in forbidden
    ]
    if found:
        raise RuntimeError(f"anonymous cache directory is bundled: {found[0]}")
    return found


def _audit_media_runtime(
    runtime_root: Path,
    bundle_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    media = bundle_manifest.get("media")
    if not isinstance(media, dict) or media.get("license") != "LGPL-only":
        raise RuntimeError("desktop media bundle is not marked LGPL-only")
    configuration = str(media.get("configuration") or "")
    if "--enable-gpl" in configuration or "--enable-nonfree" in configuration:
        raise RuntimeError("desktop media bundle enables GPL/nonfree FFmpeg mode")
    for key in ("build_manifest", "notices"):
        relative = Path(str(media.get(key) or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"desktop media {key} path is unsafe")
        if not (runtime_root / relative).is_file():
            raise RuntimeError(f"desktop media {key} is missing")
    build_manifest = json.loads(
        (runtime_root / str(media["build_manifest"])).read_text(encoding="utf-8")
    )
    for key in ("build_identity", "configuration", "license", "sources"):
        if build_manifest.get(key) != media.get(key):
            raise RuntimeError(f"desktop media {key} does not match its build manifest")
    if build_manifest.get("file_hash_scope") != (
        "relocated ad-hoc media output before product distribution signing"
    ):
        raise RuntimeError("desktop media file-hash scope is missing")
    if not (runtime_root / "bin" / "ffmpeg").is_file() or not (
        runtime_root / "bin" / "ffprobe"
    ).is_file():
        raise RuntimeError("desktop media binaries are missing")
    library_count = len(list((runtime_root / "lib" / "media").glob("*.dylib")))
    if library_count != media.get("bundled_library_count") or library_count != 6:
        raise RuntimeError("desktop media shared-library inventory changed")
    return {
        "build_identity": media["build_identity"],
        "ffmpeg_version": media["ffmpeg_version"],
        "license": media["license"],
        "bundled_library_count": library_count,
        "notices": media["notices"],
    }


def audit_root(
    root: Path,
    archive: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"bundle root does not exist: {root}")
    runtime_root = (
        root / "Contents" / "Resources" / "desktop-runtime" if root.suffix == ".app" else root
    )
    if not (runtime_root / "bundle-manifest.json").is_file():
        raise RuntimeError("desktop runtime manifest is missing")
    bundle_manifest = json.loads(
        (runtime_root / "bundle-manifest.json").read_text(encoding="utf-8")
    )
    score_policy = _internal_score_policy(bundle_manifest)
    if score_policy["enabled"] and archive is not None:
        raise RuntimeError("internal score runtime cannot enter a review archive")
    packages = _package_inventory(runtime_root)
    _audit_distributions(
        runtime_root,
        packages,
        allow_internal_score_runtime=score_policy["enabled"],
    )
    internal_score_audit = (
        _audit_internal_score_runtime(runtime_root) if score_policy["enabled"] else None
    )
    score_support_audit = _audit_score_support(runtime_root)
    symlinks = _audit_symlinks(root)
    anonymous_caches = _audit_anonymous_caches(root)
    native = _audit_native(root)
    media = _audit_media_runtime(runtime_root, bundle_manifest)
    complete_inventory = inventory(root)
    components = component_inventory(root)
    if components["installed_bytes"] != complete_inventory["total_bytes"]:
        raise RuntimeError("component inventory does not reconcile")
    if components["distribution_test_material"]["file_count"]:
        raise RuntimeError("distribution test material is bundled")
    largest_packages = sorted(
        (
            {
                "name": package["name"],
                "version": package["version"],
                "installed_bytes": package["installed_bytes"],
            }
            for package in packages
        ),
        key=lambda item: item["installed_bytes"],
        reverse=True,
    )[:10]
    result = {
        "schema_version": BUNDLE_AUDIT_SCHEMA,
        "created_at": utc_now(),
        "root": str(root),
        "runtime_relative_path": runtime_root.relative_to(root).as_posix(),
        "inventory": complete_inventory,
        "components": components,
        "package_count": len(packages),
        "largest_packages": largest_packages,
        "symlinks": symlinks,
        "native_files": native,
        "media": media,
        "forbidden_accelerator_packages": [],
        "forbidden_development_packages": [],
        "forbidden_score_runtime_assets": [],
        "internal_score_runtime": internal_score_audit
        or {
            "status": "not-included",
            "public_distribution": False,
        },
        "score_support": score_support_audit,
        "anonymous_cache_directories": anonymous_caches,
        "status": "passed",
    }
    if archive is not None:
        archive = archive.resolve()
        if not archive.is_file():
            raise RuntimeError("desktop review archive is missing")
        compressed_bytes = archive.stat().st_size
        compressed_components = archive_component_inventory(archive)
        result["archive"] = {
            "path": str(archive),
            "format": "zip",
            "compressed_bytes": compressed_bytes,
            "installed_bytes": components["installed_bytes"],
            "compression_ratio": (compressed_bytes / components["installed_bytes"]),
            "components": compressed_components,
        }
    return result


def smoke_sidecar(
    runtime_root: Path,
    working_directory: Path,
    *,
    score_runtime: Path | None = None,
) -> dict[str, Any]:
    token = secrets.token_hex(32)
    environment = os.environ.copy()
    environment["ATPIANO_DESKTOP_TOKEN"] = token
    environment.update(desktop_runtime_environment(working_directory / "workspace"))
    command: list[str | Path] = [
        runtime_root / "bin" / "python3",
        "-I",
        "-B",
        "-m",
        "atpiano.desktop_sidecar",
        "--workspace",
        working_directory / "workspace",
        "--replay-manifest",
        runtime_root / "fixture" / "input.json",
        "--model-pack",
        runtime_root / "model-pack" / "model-pack.json",
        "--expected-model-pack",
        MODEL_PACK_ID,
        "--minimum-free-gib",
        "0",
    ]
    if score_runtime is not None:
        command.extend(["--score-runtime", score_runtime])
    process = subprocess.Popen(
        [str(argument) for argument in command],
        cwd=working_directory,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.terminate()
        raise RuntimeError("desktop sidecar pipes are unavailable")
    try:
        readable, _, _ = select.select([process.stdout], [], [], 20)
        if not readable:
            process.terminate()
            process.wait(timeout=5)
            raise RuntimeError("staged desktop sidecar did not become ready")
        ready_line = process.stdout.readline()
        ready = json.loads(ready_line)
        base_url = f"http://127.0.0.1:{ready['port']}"
        try:
            urllib.request.urlopen(
                f"{base_url}/desktop/v1/handshake",
                timeout=2,
            )
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise RuntimeError("desktop sidecar returned an unexpected auth status") from error
        else:
            raise RuntimeError("desktop sidecar accepted an unauthenticated request")
        request = urllib.request.Request(
            f"{base_url}/desktop/v1/handshake",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": "tauri://localhost",
            },
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            handshake = json.load(response)
        if handshake["protocol_version"] != ready["protocol_version"]:
            raise RuntimeError("desktop sidecar protocol changed after ready")
        if handshake["model_pack_sha256"] != ready["model_pack_sha256"]:
            raise RuntimeError("desktop sidecar model identity changed")
        process.stdin.close()
        if process.wait(timeout=10) != 0:
            raise RuntimeError("desktop sidecar did not stop cleanly")
        stderr = process.stderr.read()
        if token in ready_line or token in stderr:
            raise RuntimeError("desktop sidecar leaked its bearer token")
        return {
            "status": "passed",
            "protocol_version": ready["protocol_version"],
            "contract_schema_version": ready["contract_schema_version"],
            "model_pack_id": ready["model_pack_id"],
            "score_available": handshake["score_available"],
            "unauthenticated_status": 401,
            "parent_eof_shutdown": True,
        }
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def stage_runtime(
    output: Path,
    report: Path,
    *,
    include_internal_score_runtime: bool = False,
    score_runtime_source: Path | None = None,
) -> dict[str, Any]:
    _require_macos_arm64()
    repository = _repository_root()
    output = output.resolve()
    if output != _expected_stage_root():
        raise RuntimeError(f"refusing unexpected desktop stage target: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".desktop-runtime-stage-",
        dir=output.parent,
    ) as temporary_directory:
        staged = Path(temporary_directory) / "desktop-runtime"
        python_source, python_provenance = _managed_python()
        shutil.copytree(python_source, staged, symlinks=True)
        _stage_dependencies(staged, repository)
        model_pack = stage_model_pack(_site_packages(staged), staged)
        _stage_fixture(staged)
        media = bundle_media_tools(staged)
        _prune_runtime(staged)
        relocated_native = relocate_runtime_native(
            staged,
            python_source,
        )
        score_support = stage_score_support(staged, repository)
        internal_score_runtime = (
            stage_internal_score_runtime(
                staged,
                score_runtime_source or repository / "results" / "midi2score-runtime",
            )
            if include_internal_score_runtime
            else {
                "enabled": False,
                "internal_only": False,
                "public_distribution": False,
            }
        )
        packages = _package_inventory(staged)
        _audit_distributions(
            staged,
            packages,
            allow_internal_score_runtime=(include_internal_score_runtime),
        )
        _audit_symlinks(staged)
        _audit_native(staged)
        for imports in (
            "import atpiano.desktop_sidecar, coremltools",
            "import torch; assert not torch.cuda.is_available()",
        ):
            _run(
                [
                    staged / "bin" / "python3",
                    "-I",
                    "-B",
                    "-c",
                    imports,
                ],
                cwd=Path(temporary_directory),
            )
        sidecar_smoke = smoke_sidecar(
            staged,
            Path(temporary_directory),
            score_runtime=(
                staged / INTERNAL_SCORE_RUNTIME_NAME if include_internal_score_runtime else None
            ),
        )
        manifest = {
            "schema_version": BUNDLE_MANIFEST_SCHEMA,
            "created_at": utc_now(),
            "platform": "macos",
            "architecture": "arm64",
            "execution_backend": "cpu",
            "python": python_provenance,
            "uv_lock_sha256": sha256_file(repository / "uv.lock"),
            "model_pack_id": model_pack.model_pack_id,
            "model_pack_sha256": hashlib.sha256(
                model_pack.model_dump_json().encode("utf-8")
            ).hexdigest(),
            "media": media,
            "sidecar_smoke": sidecar_smoke,
            "relocated_native_files": relocated_native,
            "score_support": score_support,
            "internal_score_runtime": internal_score_runtime,
            "packages": packages,
            "inventory_before_manifest": inventory(staged),
        }
        write_json(staged / "bundle-manifest.json", manifest)
        if output.exists():
            shutil.rmtree(output)
        staged.replace(output)

    result = audit_root(output)
    write_json(report, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m atpiano.desktop_packaging",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--output", type=Path, required=True)
    stage.add_argument("--report", type=Path, required=True)
    stage.add_argument(
        "--include-internal-score-runtime",
        action="store_true",
    )
    stage.add_argument("--score-runtime-source", type=Path)
    audit = commands.add_parser("audit")
    audit.add_argument("--root", type=Path, required=True)
    audit.add_argument("--report", type=Path, required=True)
    audit.add_argument("--archive", type=Path)
    refresh_support = commands.add_parser("refresh-score-support-manifest")
    refresh_support.add_argument("--root", type=Path, required=True)
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    if args.command == "stage":
        result = stage_runtime(
            args.output,
            args.report,
            include_internal_score_runtime=(args.include_internal_score_runtime),
            score_runtime_source=args.score_runtime_source,
        )
    elif args.command == "audit":
        result = audit_root(args.root, args.archive)
        write_json(args.report, result)
    else:
        result = refresh_score_support_manifest(args.root)
    print(json.dumps(result.get("inventory", result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
