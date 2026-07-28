"""Small filesystem and provenance helpers."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    """Hash a file or directory tree, including relative file names."""
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(child)))
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False))
            handle.write("\n")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def git_revision(*, cwd: Path | None = None) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def git_worktree_dirty(*, cwd: Path | None = None) -> bool | None:
    """Report tracked Git changes without treating untracked evidence as code."""

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return bool(result.stdout.strip())


def runtime_provenance() -> dict[str, Any]:
    return {
        "git_revision": git_revision(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": {
            name: package_version(name)
            for name in (
                "atpiano",
                "basic-pitch",
                "coremltools",
                "librosa",
                "mir_eval",
                "numpy",
                "partitura",
                "pretty_midi",
                "torch",
                "transkun",
            )
        },
    }
