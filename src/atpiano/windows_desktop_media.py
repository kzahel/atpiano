"""Pinned Windows x64 FFmpeg payload used by the desktop package."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from atpiano.util import sha256_file

MEDIA_SCHEMA = "atpiano.windows-desktop-media.v1"
MEDIA_TARGET = "windows-x86_64"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def contract_path() -> Path:
    return repository_root() / "desktop-media" / "windows-x86_64.json"


def load_contract(path: Path | None = None) -> dict[str, Any]:
    document = json.loads((path or contract_path()).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RuntimeError("Windows desktop media contract is not an object")
    validate_contract(document)
    return document


def validate_contract(document: Mapping[str, Any]) -> None:
    if document.get("schema_version") != MEDIA_SCHEMA:
        raise RuntimeError("Windows desktop media schema is unsupported")
    if document.get("target") != MEDIA_TARGET:
        raise RuntimeError("Windows desktop media target must be windows-x86_64")
    archive = document.get("archive")
    build = document.get("build")
    ffmpeg = document.get("ffmpeg")
    license_record = document.get("license")
    payload = document.get("payload")
    if not all(
        isinstance(item, Mapping)
        for item in (archive, build, ffmpeg, license_record, payload)
    ):
        raise RuntimeError("Windows desktop media contract records are incomplete")
    assert isinstance(archive, Mapping)
    assert isinstance(build, Mapping)
    assert isinstance(ffmpeg, Mapping)
    assert isinstance(license_record, Mapping)
    assert isinstance(payload, Mapping)
    for record, fields in (
        (archive, ("name", "url", "sha256", "payload_root")),
        (build, ("variant", "release", "repository", "commit")),
        (ffmpeg, ("revision", "repository", "commit")),
        (license_record, ("mode", "variant", "bundled_file")),
    ):
        if any(not isinstance(record.get(field), str) or not record[field] for field in fields):
            raise RuntimeError("Windows desktop media identity is incomplete")
    if len(str(archive["sha256"])) != 64:
        raise RuntimeError("Windows desktop media archive has no exact SHA-256")
    if len(str(build["commit"])) != 40 or len(str(ffmpeg["commit"])) != 40:
        raise RuntimeError("Windows desktop media source commits must be exact")
    if license_record.get("mode") != "LGPL" or license_record.get("variant") != "shared":
        raise RuntimeError("Windows desktop media must use the shared LGPL variant")
    executables = payload.get("executables")
    libraries = payload.get("libraries")
    if executables != ["ffmpeg.exe", "ffprobe.exe"]:
        raise RuntimeError("Windows desktop media executables changed")
    if not isinstance(libraries, list) or not libraries:
        raise RuntimeError("Windows desktop media shared libraries are missing")
    expected = [*executables, *libraries]
    if len(expected) != len(set(expected)) or any(
        not isinstance(name, str)
        or Path(name).name != name
        or Path(name).suffix.lower() not in {".exe", ".dll"}
        for name in expected
    ):
        raise RuntimeError("Windows desktop media payload names are unsafe")


def validate_archive(path: Path, contract: Mapping[str, Any]) -> None:
    archive = contract["archive"]
    assert isinstance(archive, Mapping)
    if sha256_file(path) != archive["sha256"]:
        raise RuntimeError("Windows desktop media archive failed SHA-256 verification")
