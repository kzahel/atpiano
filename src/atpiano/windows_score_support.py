"""Build and audit the publication-safe Windows x64 score-support layer."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from atpiano.util import sha256_file, utc_now, write_json

SUPPORT_SCHEMA = "atpiano.score-support.v1"
SUPPORT_AUDIT_SCHEMA = "atpiano.score-support-audit.v1"
SUPPORT_PACKAGES_SCHEMA = "atpiano.score-support-packages.v1"
SUPPORT_LAYER_ID = "atpiano-midi2score-support-py311-2026.08"
PYTHON_VERSION = "3.11.14"
PYTHON_KEY = "cpython-3.11.14-windows-x86_64-none"
PLATFORM = "windows"
ARCHITECTURE = "x86_64"
EXECUTION_BACKEND = "cpu"
PE_X86_64_MACHINE = 0x8664
EXPECTED_PACKAGE_COUNT = 64
EXPECTED_VCS_SOURCES = {
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
MUSTER_REPOSITORY = "https://github.com/TimFelixBeyer/amtevaluation.github.io"
MUSTER_COMMIT = "4ef1165edda1f719068c4c699bd8ab2076e4d7ec"
FORBIDDEN_DISTRIBUTION_PREFIXES = (
    "cuda-",
    "nvidia-",
    "nvidia_",
    "rocm-",
    "triton",
)
FORBIDDEN_DEVELOPMENT_DISTRIBUTIONS = {
    "hypothesis",
    "mypy",
    "pytest",
    "ruff",
}
FORBIDDEN_MODEL_BASENAMES = {
    "MIDI2ScoreTF.ckpt",
    "MIDI2ScoreTransformer",
    "score-runtime",
}
FORBIDDEN_NATIVE_FRAGMENTS = (
    "cublas",
    "cuda",
    "cudnn",
    "cufft",
    "curand",
    "cusolver",
    "cusparse",
    "hipblas",
    "nvrtc",
    "rocm",
)
FORBIDDEN_TEST_NAMESPACES = {"test", "tests", "testing"}
REQUIRED_SCORE_TEST_NAMESPACES = {
    ("music21", "test"),
    ("torch", "testing"),
}
PRUNABLE_PACKAGE_DIRECTORIES = (
    Path("torch/include"),
    Path("torch/share"),
    Path("pandas/tests"),
    Path("numba/tests"),
    Path("matplotlib/tests"),
    Path("setuptools/tests"),
    Path("joblib/test"),
    Path("mpmath/tests"),
    Path("llvmlite/tests"),
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


def _require_windows_builder() -> None:
    machine = platform.machine().upper()
    if platform.system() != "Windows" or machine not in {"AMD64", "ARM64"}:
        raise RuntimeError("Windows x64 score support requires a Windows build host")


def _uv_command() -> list[str]:
    executable = shutil.which("uv")
    if executable:
        return [executable]
    if importlib.util.find_spec("uv") is not None:
        return [sys.executable, "-m", "uv"]
    raise RuntimeError("uv 0.9.26 or newer is required to build score support")


def _canonical_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _tree_sha256_without(root: Path, excluded: set[str]) -> str:
    digest = hashlib.sha256()
    for child in _canonical_files(root):
        relative = child.relative_to(root).as_posix()
        if relative in excluded:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(child)))
    return digest.hexdigest()


def _payload_bytes(root: Path, excluded: set[str] | None = None) -> int:
    omitted = excluded or set()
    return sum(
        path.stat().st_size
        for path in _canonical_files(root)
        if path.relative_to(root).as_posix() not in omitted
    )


def _inventory(root: Path) -> dict[str, Any]:
    files = _canonical_files(root)
    largest = sorted(
        (
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
            }
            for path in files
        ),
        key=lambda item: int(item["bytes"]),
        reverse=True,
    )[:10]
    return {
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "largest_files": largest,
    }


def _read_acquisition_contract(repository: Path) -> dict[str, Any]:
    path = repository / "desktop-score" / "acquisition.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    targets = {
        (target.get("platform"), target.get("architecture"))
        for target in document.get("supported_targets", [])
        if isinstance(target, dict)
    }
    registry_lock = repository / "desktop-score" / "support-requirements.lock"
    vcs_lock = repository / "desktop-score" / "support-vcs-requirements.txt"
    if (
        document.get("schema_version") != "atpiano.score-acquisition.v1"
        or document.get("support_layer_id") != SUPPORT_LAYER_ID
        or document.get("support_python_version") != PYTHON_VERSION
        or (PLATFORM, ARCHITECTURE) not in targets
        or document.get("execution_backend") != EXECUTION_BACKEND
        or document.get("support_requirements_sha256")
        != sha256_file(registry_lock)
        or document.get("support_vcs_requirements_sha256")
        != sha256_file(vcs_lock)
    ):
        raise RuntimeError("score acquisition contract and support inputs differ")
    return document


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
    root = executable.parent
    build = (root / "BUILD").read_text(encoding="utf-8").strip()
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
        raise RuntimeError("managed score-support Python is not Windows x64")
    acquisition_url = (
        "https://github.com/astral-sh/python-build-standalone/"
        f"releases/download/{build}/cpython-{PYTHON_VERSION}%2B{build}-"
        "x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
    )
    return root, {
        "key": PYTHON_KEY,
        "version": PYTHON_VERSION,
        "build": build,
        "acquisition_url": acquisition_url,
        "source_tree_sha256": _tree_sha256_without(root, set()),
    }


def _site_packages(python_root: Path) -> Path:
    return python_root / "Lib" / "site-packages"


def _direct_url_inventory(site_packages: Path) -> list[dict[str, Any]]:
    sources = []
    for path in sorted(
        site_packages.glob("*.dist-info/direct_url.json"),
        key=lambda item: item.as_posix(),
    ):
        sources.append(
            {
                "distribution": path.parent.name.removesuffix(".dist-info"),
                "source": json.loads(path.read_text(encoding="utf-8")),
            }
        )
    return sources


def _vcs_requirements(path: Path) -> dict[str, str]:
    requirements = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, requirement = stripped.partition(" @ ")
        if not separator:
            raise RuntimeError("score support VCS requirement is malformed")
        requirements[name] = f"{name} @ {requirement}"
    if set(requirements) != {"music21", "muster", "score-transformer"}:
        raise RuntimeError("score support VCS requirement set changed")
    return requirements


def _validate_vcs_sources(sources: list[dict[str, Any]]) -> None:
    observed: dict[str, str] = {}
    for source in sources:
        document = source.get("source")
        if not isinstance(document, dict):
            continue
        vcs = document.get("vcs_info")
        if isinstance(vcs, dict) and vcs.get("vcs") == "git":
            observed[str(document.get("url"))] = str(vcs.get("commit_id"))
    if observed != EXPECTED_VCS_SOURCES:
        raise RuntimeError("score support VCS provenance differs from its pins")


def _remove_tree(path: Path) -> None:
    def make_writable_and_retry(
        function: Any,
        value: str,
        _: tuple[type[BaseException], BaseException, Any],
    ) -> None:
        os.chmod(value, stat.S_IWRITE)
        function(value)

    candidate = path
    if os.name == "nt":
        candidate = Path(f"\\\\?\\{path.resolve()}")
    if candidate.exists():
        shutil.rmtree(candidate, onerror=make_writable_and_retry)


def _install_windows_vcs_dependencies(
    uv: Sequence[str],
    python: Path,
    vcs_lock: Path,
    working_root: Path,
    repository: Path,
) -> list[dict[str, Any]]:
    requirements = _vcs_requirements(vcs_lock)
    for name in ("music21", "score-transformer"):
        _run(
            [
                *uv,
                "pip",
                "install",
                "--python",
                python,
                "--no-deps",
                "--strict",
                "--link-mode",
                "copy",
                requirements[name],
            ],
            cwd=repository,
        )
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required on the Windows score-support build host")
    source = working_root / "muster-source"
    source.mkdir()
    _run([git, "init", "--quiet"], cwd=source)
    _run([git, "remote", "add", "origin", MUSTER_REPOSITORY], cwd=source)
    _run([git, "fetch", "--quiet", "--depth", "1", "origin", MUSTER_COMMIT], cwd=source)
    _run([git, "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=source)
    observed_commit = _run(
        [git, "rev-parse", "HEAD"],
        cwd=source,
        capture_output=True,
    ).stdout.strip()
    if observed_commit != MUSTER_COMMIT:
        raise RuntimeError("MUSTER source commit changed during Windows packaging")
    (source / "setup.py").write_text(
        """from setuptools import find_packages, setup

setup(
    name="muster",
    version="0.0.1",
    description="A simple wrapper for MUSTER",
    packages=find_packages(),
    package_data={"muster": ["evaluate_XML_voicePlus.sh"]},
    include_package_data=True,
)
""",
        encoding="utf-8",
        newline="\n",
    )
    _run(
        [
            *uv,
            "pip",
            "install",
            "--python",
            python,
            "--no-deps",
            "--strict",
            "--link-mode",
            "copy",
            source,
        ],
        cwd=repository,
    )
    site_packages = _site_packages(python.parent)
    sources = [
        item
        for item in _direct_url_inventory(site_packages)
        if not str(item.get("distribution", "")).lower().startswith("muster-")
    ]
    sources.append(
        {
            "distribution": "muster-0.0.1",
            "source": {
                "url": MUSTER_REPOSITORY,
                "vcs_info": {
                    "vcs": "git",
                    "commit_id": MUSTER_COMMIT,
                    "requested_revision": MUSTER_COMMIT,
                },
            },
            "packaging_override": {
                "reason": "evaluation-only Unix native tools are not used by inference",
                "retained": "Python wrapper and evaluate_XML_voicePlus.sh",
                "omitted": "compile.sh, Code, Programs, and demo",
            },
        }
    )
    sources.sort(key=lambda item: str(item.get("distribution", "")).lower())
    _validate_vcs_sources(sources)
    _remove_tree(source)
    return sources


def _remove_runtime_caches(root: Path) -> None:
    for cache in sorted(
        root.rglob("__pycache__"),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if cache.is_dir():
            _remove_tree(cache)
    for bytecode in root.rglob("*.py[co]"):
        bytecode.unlink()


def _prune_distribution_test_material(site_packages: Path) -> None:
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
        if any(part.endswith((".dist-info", ".egg-info")) for part in relative.parts):
            continue
        if relative.parts in REQUIRED_SCORE_TEST_NAMESPACES:
            continue
        if candidate.is_dir():
            _remove_tree(candidate)


def _prune_python(python_root: Path) -> None:
    site_packages = _site_packages(python_root)
    for relative in (
        Path("include"),
        Path("libs"),
        Path("Lib/test"),
        Path("Lib/idlelib"),
        Path("Lib/tkinter"),
        Path("Lib/turtledemo"),
    ):
        target = python_root / relative
        if target.is_dir():
            _remove_tree(target)
    for relative in PRUNABLE_PACKAGE_DIRECTORIES:
        target = site_packages / relative
        if target.is_dir():
            _remove_tree(target)
    _prune_distribution_test_material(site_packages)
    for direct_url in site_packages.rglob("direct_url.json"):
        direct_url.unlink()
    scripts = python_root / "Scripts"
    if scripts.is_dir():
        _remove_tree(scripts)
    (python_root / "pythonw.exe").unlink(missing_ok=True)
    _remove_runtime_caches(python_root)


def _materialize_runtime_symlinks(root: Path) -> None:
    resolved_root = root.resolve()
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_symlink():
            continue
        target = path.resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise RuntimeError("score support contains an escaping symbolic link")
        if not target.is_file():
            raise RuntimeError("score support link does not target a regular file")
        materialized = path.with_name(f".{path.name}.materialized")
        shutil.copy2(target, materialized)
        path.unlink()
        materialized.replace(path)


def _package_inventory(python: Path) -> list[dict[str, Any]]:
    script = """
import importlib.metadata as metadata
import json
items = []
for distribution in metadata.distributions():
    value = distribution.metadata
    classifiers = value.get_all("Classifier") or []
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
        "license_classifiers": [
            item for item in classifiers if item.startswith("License ::")
        ],
        "installed_bytes": sum(installed),
        "installed_file_count": len(installed),
    })
print(json.dumps(sorted(items, key=lambda item: item["name"].lower())))
"""
    return json.loads(
        _run([python, "-I", "-B", "-c", script], capture_output=True).stdout
    )


def _validate_distributions(root: Path, packages: list[dict[str, Any]]) -> None:
    for package in packages:
        normalized = str(package["name"]).lower().replace("_", "-")
        if normalized.startswith(FORBIDDEN_DISTRIBUTION_PREFIXES):
            raise RuntimeError(f"forbidden accelerator package: {package['name']}")
        if normalized in FORBIDDEN_DEVELOPMENT_DISTRIBUTIONS:
            raise RuntimeError(f"forbidden development package: {package['name']}")
    for path in root.rglob("*"):
        if path.name in FORBIDDEN_MODEL_BASENAMES:
            raise RuntimeError(f"forbidden model asset: {path.name}")
        if path.is_symlink():
            raise RuntimeError("score support contains a symbolic link")


def _pe_machine(path: Path) -> int:
    with path.open("rb") as handle:
        header = handle.read(64)
        if len(header) < 64 or header[:2] != b"MZ":
            raise RuntimeError(f"Windows native file lacks a DOS header: {path.name}")
        offset = struct.unpack_from("<I", header, 0x3C)[0]
        handle.seek(offset)
        pe_header = handle.read(6)
    if len(pe_header) != 6 or pe_header[:4] != b"PE\0\0":
        raise RuntimeError(f"Windows native file lacks a PE header: {path.name}")
    return struct.unpack_from("<H", pe_header, 4)[0]


def _audit_native(root: Path) -> list[dict[str, Any]]:
    native = []
    for path in _canonical_files(root):
        suffix = path.suffix.lower()
        if suffix in {".dylib", ".so"}:
            raise RuntimeError(f"foreign native file in Windows support: {path.name}")
        if suffix not in {".dll", ".exe", ".pyd"}:
            continue
        relative = path.relative_to(root).as_posix()
        lowered = path.name.lower()
        if any(fragment in lowered for fragment in FORBIDDEN_NATIVE_FRAGMENTS):
            raise RuntimeError(f"accelerator native file in CPU support: {path.name}")
        machine = _pe_machine(path)
        if machine != PE_X86_64_MACHINE:
            raise RuntimeError(f"non-x64 PE file in Windows support: {relative}")
        native.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "machine": "x86_64",
            }
        )
    if not native:
        raise RuntimeError("Windows score support has no native files")
    return native


def _run_import_smoke(python: Path) -> None:
    for imports in (
        "import torch, transformers, lightning, music21",
        "import numba, pretty_midi, score_transformer, muster",
    ):
        _run([python, "-I", "-B", "-c", imports])


def _validate_manifest_identity(
    manifest: dict[str, Any],
    repository: Path,
) -> None:
    contract = _read_acquisition_contract(repository)
    expected = {
        "schema_version": SUPPORT_SCHEMA,
        "support_layer_id": SUPPORT_LAYER_ID,
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "execution_backend": EXECUTION_BACKEND,
        "python_version": PYTHON_VERSION,
        "requirements_sha256": contract["support_requirements_sha256"],
        "vcs_requirements_sha256": contract["support_vcs_requirements_sha256"],
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Windows score support identity differs from its contract")
    if manifest.get("package_count") != EXPECTED_PACKAGE_COUNT:
        raise RuntimeError("Windows score support package count changed")


def audit_windows_score_support(root: Path, repository: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "support-manifest.json"
    packages_path = root / "packages.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packages_document = json.loads(packages_path.read_text(encoding="utf-8"))
    _validate_manifest_identity(manifest, repository)
    if manifest.get("packages_sha256") != sha256_file(packages_path):
        raise RuntimeError("Windows score support package inventory changed")
    if manifest.get("payload_sha256") != _tree_sha256_without(
        root,
        {"support-manifest.json"},
    ):
        raise RuntimeError("Windows score support payload changed")
    if manifest.get("payload_bytes") != _payload_bytes(
        root,
        {"support-manifest.json"},
    ):
        raise RuntimeError("Windows score support byte count changed")
    python = root / ".venv" / "python.exe"
    if not python.is_file():
        raise RuntimeError("Windows score support Python is missing")
    packages = _package_inventory(python)
    _validate_distributions(root, packages)
    recorded = packages_document.get("packages")
    if not isinstance(recorded, list):
        raise RuntimeError("Windows score support package inventory is invalid")
    recorded_identities = {
        (str(package.get("name")), str(package.get("version")))
        for package in recorded
        if isinstance(package, dict)
    }
    actual_identities = {
        (str(package["name"]), str(package["version"])) for package in packages
    }
    if recorded_identities != actual_identities:
        raise RuntimeError("Windows score support distributions changed")
    if len(packages) != EXPECTED_PACKAGE_COUNT:
        raise RuntimeError("Windows score support distribution count changed")
    vcs_sources = packages_document.get("vcs_sources")
    if not isinstance(vcs_sources, list):
        raise RuntimeError("Windows score support VCS inventory is invalid")
    _validate_vcs_sources(vcs_sources)
    _run_import_smoke(python)
    native = _audit_native(root)
    return {
        "schema_version": SUPPORT_AUDIT_SCHEMA,
        "created_at": utc_now(),
        "status": "passed",
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "execution_backend": EXECUTION_BACKEND,
        "support_layer_id": SUPPORT_LAYER_ID,
        "manifest_sha256": sha256_file(manifest_path),
        "payload_sha256": manifest["payload_sha256"],
        "package_count": len(packages),
        "native_file_count": len(native),
        "native_files": native,
        "inventory": _inventory(root),
    }


def stage_windows_score_support(output: Path, repository: Path) -> dict[str, Any]:
    _require_windows_builder()
    output = output.resolve()
    repository = repository.resolve()
    if output.exists():
        raise RuntimeError("Windows score-support output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    contract = _read_acquisition_contract(repository)
    uv = _uv_command()
    python_source, python_provenance = _managed_python(uv)
    temporary = Path(
        tempfile.mkdtemp(prefix=".score-support-", dir=output.parent)
    ).resolve()
    root = temporary / "score-support"
    try:
        python_root = root / ".venv"
        shutil.copytree(python_source, python_root, symlinks=True)
        site_packages = _site_packages(python_root)
        if site_packages.exists():
            _remove_tree(site_packages)
        (python_root / "Lib" / "EXTERNALLY-MANAGED").unlink(missing_ok=True)
        python = python_root / "python.exe"
        registry_lock = repository / "desktop-score" / "support-requirements.lock"
        vcs_lock = repository / "desktop-score" / "support-vcs-requirements.txt"
        _run(
            [
                *uv,
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
            [python, "-I", "-B", "-c", "import sys; assert sys.maxsize > 2**32"],
        )
        vcs_sources = _install_windows_vcs_dependencies(
            uv,
            python,
            vcs_lock,
            temporary,
            repository,
        )
        _prune_python(python_root)
        _materialize_runtime_symlinks(root)
        packages = _package_inventory(python)
        if len(packages) != EXPECTED_PACKAGE_COUNT:
            raise RuntimeError("Windows score support package count is not exact")
        _validate_distributions(root, packages)
        _run_import_smoke(python)
        native = _audit_native(root)
        packages_document = {
            "schema_version": SUPPORT_PACKAGES_SCHEMA,
            "support_layer_id": SUPPORT_LAYER_ID,
            "python": f"Python {PYTHON_VERSION}",
            "python_provenance": python_provenance,
            "registry_requirements": {
                "path": "desktop-score/support-requirements.lock",
                "sha256": contract["support_requirements_sha256"],
            },
            "vcs_requirements": {
                "path": "desktop-score/support-vcs-requirements.txt",
                "sha256": contract["support_vcs_requirements_sha256"],
            },
            "vcs_sources": vcs_sources,
            "native_files": native,
            "packages": packages,
        }
        packages_path = root / "packages.json"
        write_json(packages_path, packages_document)
        manifest = {
            "schema_version": SUPPORT_SCHEMA,
            "support_layer_id": SUPPORT_LAYER_ID,
            "platform": PLATFORM,
            "architecture": ARCHITECTURE,
            "execution_backend": EXECUTION_BACKEND,
            "python_version": PYTHON_VERSION,
            "requirements_sha256": contract["support_requirements_sha256"],
            "vcs_requirements_sha256": contract[
                "support_vcs_requirements_sha256"
            ],
            "packages_sha256": sha256_file(packages_path),
            "payload_sha256": _tree_sha256_without(
                root,
                {"support-manifest.json"},
            ),
            "package_count": len(packages),
            "payload_bytes": _payload_bytes(root),
        }
        write_json(root / "support-manifest.json", manifest)
        os.replace(root, output)
        temporary.rmdir()
        return audit_windows_score_support(output, repository)
    finally:
        if temporary.exists():
            _remove_tree(temporary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m atpiano.windows_score_support",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--output", type=Path, required=True)
    stage.add_argument("--repository", type=Path, default=_repository_root())
    stage.add_argument("--report", type=Path)
    audit = commands.add_parser("audit")
    audit.add_argument("--root", type=Path, required=True)
    audit.add_argument("--repository", type=Path, default=_repository_root())
    audit.add_argument("--report", type=Path)
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    if args.command == "stage":
        result = stage_windows_score_support(args.output, args.repository)
    else:
        result = audit_windows_score_support(args.root, args.repository)
    if args.report is not None:
        write_json(args.report, result)
    print(json.dumps(result["inventory"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
