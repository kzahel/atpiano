"""Pinned Windows x64 FFmpeg payload used by the desktop package."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import wave
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from atpiano.util import sha256_file, utc_now, write_json

MEDIA_SCHEMA = "atpiano.windows-desktop-media.v1"
MEDIA_TARGET = "windows-x86_64"
RUNTIME_SCHEMA = "atpiano.windows-desktop-media-runtime.v1"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def contract_path() -> Path:
    return repository_root() / "desktop-media" / "windows-x86_64.json"


def default_archive_path(contract: Mapping[str, Any]) -> Path:
    archive = contract["archive"]
    assert isinstance(archive, Mapping)
    return (
        repository_root()
        / "results"
        / "desktop-media"
        / MEDIA_TARGET
        / "sources"
        / str(archive["name"])
    )


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


def _run(
    arguments: Sequence[str | Path],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(argument) for argument in arguments],
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _download_archive(contract: Mapping[str, Any], destination: Path) -> Path:
    archive = contract["archive"]
    assert isinstance(archive, Mapping)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        try:
            validate_archive(destination, contract)
        except RuntimeError:
            destination.unlink()
        else:
            return destination
    temporary = destination.with_name(f".{destination.name}.download")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(
        str(archive["url"]),
        headers={"User-Agent": "Atpiano Windows desktop media builder"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            validate_archive(temporary, contract)
            os.replace(temporary, destination)
            return destination
        except Exception as error:  # pragma: no cover - network retry boundary
            last_error = error
            temporary.unlink(missing_ok=True)
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError("could not download pinned Windows desktop media") from last_error


def _archive_member(payload_root: str, relative: str) -> str:
    root = PurePosixPath(payload_root)
    path = root / PurePosixPath(relative)
    if (
        root.is_absolute()
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in payload_root
        or "\\" in relative
    ):
        raise RuntimeError("Windows desktop media archive path is unsafe")
    return path.as_posix()


def _copy_member(bundle: zipfile.ZipFile, member: str, destination: Path) -> None:
    try:
        info = bundle.getinfo(member)
    except KeyError as error:
        raise RuntimeError(f"Windows desktop media archive is missing: {member}") from error
    if info.is_dir():
        raise RuntimeError(f"Windows desktop media archive member is not a file: {member}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with bundle.open(info) as source, destination.open("wb") as output:
        shutil.copyfileobj(source, output)


def _payload_names(contract: Mapping[str, Any]) -> list[str]:
    payload = contract["payload"]
    assert isinstance(payload, Mapping)
    return [*payload["executables"], *payload["libraries"]]


def _file_records(root: Path, relative_paths: Sequence[str]) -> list[dict[str, Any]]:
    records = []
    for relative in relative_paths:
        path = root / Path(relative)
        if not path.is_file():
            raise RuntimeError(f"Windows desktop media payload is missing: {relative}")
        records.append(
            {
                "path": Path(relative).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records


def _exercise_runtime(runtime_root: Path) -> None:
    ffmpeg = runtime_root / "bin" / "ffmpeg.exe"
    ffprobe = runtime_root / "bin" / "ffprobe.exe"
    version = _run([ffmpeg, "-version"], capture_output=True).stdout.splitlines()[0]
    if "n8.1.2-44-g7c533d0f86" not in version:
        raise RuntimeError("Windows desktop FFmpeg revision changed")
    license_output = _run([ffmpeg, "-L"], capture_output=True).stdout
    if "GNU Lesser General Public License" not in license_output:
        raise RuntimeError("Windows desktop FFmpeg does not report an LGPL license")
    with tempfile.TemporaryDirectory(prefix="atpiano-windows-media-smoke-") as temporary:
        root = Path(temporary)
        wav = root / "source.wav"
        frames = bytearray()
        for index in range(800):
            value = (index % 200 - 100) * 100
            frames.extend(value.to_bytes(2, "little", signed=True))
            frames.extend((-value).to_bytes(2, "little", signed=True))
        with wave.open(str(wav), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(8_000)
            output.writeframes(bytes(frames))
        mp3 = root / "playback.mp3"
        _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                wav,
                "-map_metadata",
                "-1",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                mp3,
            ]
        )
        probe = _run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate,channels",
                "-of",
                "json",
                mp3,
            ],
            capture_output=True,
        )
        stream = json.loads(probe.stdout)["streams"][0]
        if stream != {"codec_name": "mp3", "sample_rate": "8000", "channels": 2}:
            raise RuntimeError(f"Windows desktop media probe changed: {stream}")


def stage_runtime(
    runtime_root: Path,
    *,
    archive_path: Path | None = None,
    contract: Mapping[str, Any] | None = None,
    exercise: bool = True,
) -> dict[str, Any]:
    contract_document = dict(contract or load_contract())
    validate_contract(contract_document)
    runtime_root = runtime_root.resolve()
    manifest_path = runtime_root / "media-build-manifest.json"
    if manifest_path.exists():
        raise RuntimeError("Windows desktop media is already staged")
    archive = archive_path or default_archive_path(contract_document)
    if archive_path is None:
        archive = _download_archive(contract_document, archive)
    else:
        validate_archive(archive, contract_document)
    archive_record = contract_document["archive"]
    license_record = contract_document["license"]
    assert isinstance(archive_record, Mapping)
    assert isinstance(license_record, Mapping)
    payload_root = str(archive_record["payload_root"])
    payload_names = _payload_names(contract_document)
    relative_files = [f"bin/{name}" for name in payload_names]
    license_relative = "share/licenses/media/FFmpeg-BtbN-LICENSE.txt"
    with zipfile.ZipFile(archive) as bundle:
        for name, relative in zip(payload_names, relative_files, strict=True):
            _copy_member(
                bundle,
                _archive_member(payload_root, f"bin/{name}"),
                runtime_root / relative,
            )
        _copy_member(
            bundle,
            _archive_member(payload_root, str(license_record["bundled_file"])),
            runtime_root / license_relative,
        )
    records = _file_records(runtime_root, [*relative_files, license_relative])
    manifest = {
        "schema_version": RUNTIME_SCHEMA,
        "created_at": utc_now(),
        "target": MEDIA_TARGET,
        "archive": dict(archive_record),
        "build": dict(contract_document["build"]),
        "ffmpeg": dict(contract_document["ffmpeg"]),
        "license": dict(license_record),
        "files": records,
    }
    write_json(manifest_path, manifest)
    return validate_runtime(runtime_root, contract=contract_document, exercise=exercise)


def validate_runtime(
    runtime_root: Path,
    *,
    contract: Mapping[str, Any] | None = None,
    exercise: bool = True,
) -> dict[str, Any]:
    contract_document = dict(contract or load_contract())
    validate_contract(contract_document)
    manifest_path = runtime_root / "media-build-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("archive", "build", "ffmpeg", "license"):
        if manifest.get(key) != contract_document[key]:
            raise RuntimeError(f"Windows desktop media {key} identity changed")
    if manifest.get("schema_version") != RUNTIME_SCHEMA or manifest.get("target") != MEDIA_TARGET:
        raise RuntimeError("Windows desktop media runtime identity changed")
    expected_paths = [
        *(f"bin/{name}" for name in _payload_names(contract_document)),
        "share/licenses/media/FFmpeg-BtbN-LICENSE.txt",
    ]
    actual_records = manifest.get("files")
    if not isinstance(actual_records, list):
        raise RuntimeError("Windows desktop media file inventory is invalid")
    expected_records = _file_records(runtime_root, expected_paths)
    if actual_records != expected_records:
        raise RuntimeError("Windows desktop media file inventory changed")
    if exercise:
        _exercise_runtime(runtime_root)
    return {
        "status": "passed",
        "target": MEDIA_TARGET,
        "ffmpeg_revision": contract_document["ffmpeg"]["revision"],
        "archive_sha256": contract_document["archive"]["sha256"],
        "file_count": len(expected_records),
        "total_bytes": sum(int(item["bytes"]) for item in expected_records),
        "files": expected_records,
    }
