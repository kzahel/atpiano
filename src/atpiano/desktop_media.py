"""Build and validate Atpiano's minimal LGPL macOS media runtime."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import wave
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from atpiano.util import sha256_file

BUILD_SCHEMA = "atpiano.desktop-media-build.v1"
RUNTIME_SCHEMA = "atpiano.desktop-media-runtime.v1"
SOURCE_ARCHIVE_SCHEMA = "atpiano.desktop-media-sources.v1"
MEDIA_RUNTIME_ENV = "ATPIANO_MEDIA_RUNTIME_ROOT"
SYSTEM_LOAD_PREFIXES = ("/System/Library/", "/usr/lib/")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_contract_path() -> Path:
    return repository_root() / "desktop-media" / "manifest.json"


def default_results_root() -> Path:
    return repository_root() / "results" / "desktop-media"


def default_runtime_root() -> Path:
    configured = os.environ.get(MEDIA_RUNTIME_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return default_results_root() / "macos-arm64" / "runtime"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON document is not an object: {path}")
    return value


def load_build_contract(path: Path | None = None) -> dict[str, Any]:
    document = _read_json(path or build_contract_path())
    validate_build_contract(document)
    return document


def validate_build_contract(document: Mapping[str, Any]) -> None:
    if document.get("schema_version") != BUILD_SCHEMA:
        raise RuntimeError("desktop media build schema is unsupported")
    if document.get("target") != "macos-arm64":
        raise RuntimeError("desktop media build target must be macos-arm64")
    install_prefix = document.get("install_prefix")
    if not isinstance(install_prefix, str) or not install_prefix.startswith("/"):
        raise RuntimeError("desktop media install prefix must be absolute")
    if document.get("runtime_library_directory") != "lib/media":
        raise RuntimeError("desktop media libraries must be isolated under lib/media")
    sources = document.get("sources")
    if not isinstance(sources, list) or {
        source.get("name") for source in sources if isinstance(source, dict)
    } != {"ffmpeg", "lame"}:
        raise RuntimeError("desktop media sources must be exactly FFmpeg and LAME")
    for source in sources:
        if not isinstance(source, dict):
            raise RuntimeError("desktop media source entry is invalid")
        for key in ("version", "archive", "url", "license"):
            if not isinstance(source.get(key), str) or not source[key]:
                raise RuntimeError(f"desktop media source has no {key}")
        if not isinstance(source.get("sha256"), str) or len(source["sha256"]) != 64:
            raise RuntimeError("desktop media source has no SHA-256")
        if not str(source["license"]).startswith("LGPL-"):
            raise RuntimeError("desktop media source is not LGPL licensed")
        if not isinstance(source.get("license_files"), list) or not source[
            "license_files"
        ]:
            raise RuntimeError("desktop media source has no license files")
    lame_flags = document.get("lame_configure")
    ffmpeg_flags = document.get("ffmpeg_configure")
    if not isinstance(lame_flags, list) or not isinstance(ffmpeg_flags, list):
        raise RuntimeError("desktop media configure flags are missing")
    joined = " ".join(str(flag) for flag in ffmpeg_flags)
    if "--enable-gpl" in joined or "--enable-nonfree" in joined:
        raise RuntimeError("desktop FFmpeg must exclude GPL and nonfree modes")
    for required in (
        "--enable-shared",
        "--disable-static",
        "--disable-autodetect",
        "--disable-everything",
        "--enable-libmp3lame",
    ):
        if required not in ffmpeg_flags:
            raise RuntimeError(f"desktop FFmpeg flag is missing: {required}")
    for required in ("--enable-shared", "--disable-static", "--disable-frontend"):
        if required not in lame_flags:
            raise RuntimeError(f"desktop LAME flag is missing: {required}")


def _run(
    arguments: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(argument) for argument in arguments],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _require_macos_arm64() -> None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("desktop media runtime builds require macOS arm64")
    for executable in ("make", "clang", "otool", "install_name_tool", "codesign"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"desktop media build tool is missing: {executable}")


def _source(contract: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return next(source for source in contract["sources"] if source["name"] == name)


def _download_source(source: Mapping[str, Any], source_root: Path) -> Path:
    source_root.mkdir(parents=True, exist_ok=True)
    destination = source_root / str(source["archive"])
    expected = str(source["sha256"])
    if destination.is_file() and sha256_file(destination) == expected:
        return destination
    temporary = destination.with_suffix(f"{destination.suffix}.download")
    if temporary.exists():
        temporary.unlink()
    request = urllib.request.Request(
        str(source["url"]),
        headers={"User-Agent": "Atpiano desktop media builder"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            if sha256_file(temporary) != expected:
                raise RuntimeError(
                    f"downloaded {source['archive']} failed SHA-256 verification"
                )
            os.replace(temporary, destination)
            return destination
        except Exception as error:  # pragma: no cover - network retry boundary
            last_error = error
            if temporary.exists():
                temporary.unlink()
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"could not download {source['archive']}") from last_error


def _extract_source(archive: Path, build_root: Path) -> Path:
    _run(["tar", "-xf", archive, "-C", build_root])
    name = archive.name
    for suffix in (".tar.xz", ".tar.gz", ".tgz"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    extracted = build_root / name
    if not extracted.is_dir():
        raise RuntimeError(f"source archive has unexpected root: {archive.name}")
    return extracted


def _otool_dependencies(path: Path) -> list[str]:
    output = _run(["otool", "-L", path], capture_output=True).stdout
    return [
        line.strip().split(" (compatibility version", 1)[0]
        for line in output.splitlines()[1:]
        if line.strip()
    ]


def _is_system_load_path(path: str) -> bool:
    return path.startswith(SYSTEM_LOAD_PREFIXES)


def _relocate_runtime(prefix_root: Path, runtime_root: Path) -> None:
    binaries = runtime_root / "bin"
    libraries = runtime_root / "lib" / "media"
    binaries.mkdir(parents=True)
    libraries.mkdir(parents=True)
    staged: dict[str, Path] = {}
    for name in ("ffmpeg", "ffprobe"):
        source = prefix_root / "bin" / name
        destination = binaries / name
        shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
        staged[name] = destination

    install_prefix = PurePosixPath("/") / prefix_root.name
    queue = deque(staged.values())
    visited: set[Path] = set()
    dependency_changes: dict[Path, list[tuple[str, Path]]] = {}
    copied: dict[str, Path] = {}
    while queue:
        binary = queue.popleft()
        if binary in visited:
            continue
        visited.add(binary)
        changes = []
        for load_path in _otool_dependencies(binary):
            if _is_system_load_path(load_path):
                continue
            if load_path.startswith(("@loader_path/", "@rpath/", "@executable_path/")):
                raise RuntimeError(f"unexpected pre-relocated media load path: {load_path}")
            pure = PurePosixPath(load_path)
            try:
                relative = pure.relative_to(install_prefix)
            except ValueError as error:
                raise RuntimeError(f"media dependency escapes build prefix: {load_path}") from error
            source = prefix_root / Path(*relative.parts)
            if not source.is_file():
                raise RuntimeError(f"media dependency is missing: {load_path}")
            name = pure.name
            destination = libraries / name
            if name not in copied:
                shutil.copy2(source.resolve(), destination)
                destination.chmod(
                    destination.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR
                )
                copied[name] = destination
                queue.append(destination)
            elif sha256_file(copied[name]) != sha256_file(source.resolve()):
                raise RuntimeError(f"media dependency basename collision: {name}")
            changes.append((load_path, copied[name]))
        dependency_changes[binary] = changes

    for binary, changes in dependency_changes.items():
        is_library = binary.parent == libraries
        for original, destination in changes:
            replacement = (
                f"@loader_path/{destination.name}"
                if is_library
                else f"@loader_path/../lib/media/{destination.name}"
            )
            _run(["install_name_tool", "-change", original, replacement, binary])
        if is_library:
            _run(["install_name_tool", "-id", f"@loader_path/{binary.name}", binary])
        _run(["codesign", "--force", "--sign", "-", binary])


def _copy_notices(
    contract: Mapping[str, Any],
    source_trees: Mapping[str, Path],
    runtime_root: Path,
) -> None:
    destination = runtime_root / "share" / "licenses" / "media"
    destination.mkdir(parents=True)
    shutil.copy2(repository_root() / "THIRD_PARTY_NOTICES.md", destination)
    for source in contract["sources"]:
        source_name = str(source["name"])
        for license_file in source["license_files"]:
            original = source_trees[source_name] / str(license_file)
            target = destination / f"{source_name}-{Path(str(license_file)).name}"
            shutil.copy2(original, target)


def _contract_identity(contract: Mapping[str, Any]) -> str:
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _runtime_files(runtime_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(runtime_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(runtime_root.rglob("*"))
        if path.is_file() and path.name != "build-manifest.json"
    ]


def _exercise_runtime(runtime_root: Path) -> None:
    ffmpeg = runtime_root / "bin" / "ffmpeg"
    ffprobe = runtime_root / "bin" / "ffprobe"
    with tempfile.TemporaryDirectory(prefix="atpiano-media-smoke-") as temporary:
        root = Path(temporary)
        audio = root / "audio"
        audio.mkdir()
        frames = bytearray()
        for index in range(800):
            left = (index % 200 - 100) * 100
            right = -left
            frames.extend(left.to_bytes(2, "little", signed=True))
            frames.extend(right.to_bytes(2, "little", signed=True))
        for name in ("000000.wav", "000001.wav"):
            with wave.open(str(audio / name), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(8_000)
                output.writeframes(bytes(frames))
        concat = audio / "concat.txt"
        concat.write_text("file '000000.wav'\nfile '000001.wav'\n", encoding="utf-8")
        mp3 = root / "playback.mp3"
        _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                concat,
                "-map_metadata",
                "-1",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-write_xing",
                "1",
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
            raise RuntimeError(f"desktop media probe returned unexpected stream: {stream}")
        decoded = root / "decoded.pcm"
        _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-xerror",
                "-nostdin",
                "-i",
                mp3,
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "8000",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                decoded,
            ]
        )
        if not decoded.is_file() or decoded.stat().st_size == 0:
            raise RuntimeError("desktop media MP3 decode produced no PCM")
        _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-xerror",
                "-nostdin",
                "-i",
                mp3,
                "-f",
                "null",
                "-",
            ]
        )


def validate_runtime(
    runtime_root: Path | None = None,
    *,
    exercise: bool = True,
) -> dict[str, Any]:
    root = (runtime_root or default_runtime_root()).resolve()
    manifest_path = root / "build-manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"desktop media runtime manifest is missing: {manifest_path}")
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != RUNTIME_SCHEMA:
        raise RuntimeError("desktop media runtime schema is unsupported")
    contract = load_build_contract()
    if manifest.get("build_identity") != _contract_identity(contract):
        raise RuntimeError("desktop media runtime does not match the build contract")
    configuration = str(manifest.get("configuration") or "")
    if "--enable-gpl" in configuration or "--enable-nonfree" in configuration:
        raise RuntimeError("desktop media runtime unexpectedly enables GPL/nonfree mode")
    if manifest.get("license") != "LGPL-only":
        raise RuntimeError("desktop media runtime is not marked LGPL-only")
    if manifest.get("file_hash_scope") != (
        "relocated ad-hoc media output before product distribution signing"
    ):
        raise RuntimeError("desktop media runtime file-hash scope is missing")
    expected_paths = set()
    for item in manifest.get("files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise RuntimeError("desktop media runtime file inventory is invalid")
        path = root / item["path"]
        expected_paths.add(path.resolve())
        if not path.is_file() or path.stat().st_size != item.get("bytes"):
            raise RuntimeError(f"desktop media runtime file is missing or changed: {path}")
        if sha256_file(path) != item.get("sha256"):
            raise RuntimeError(f"desktop media runtime file hash changed: {path}")
    actual_paths = {
        path.resolve()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_paths != expected_paths:
        raise RuntimeError("desktop media runtime has unexpected or untracked files")
    for binary in (root / "bin" / "ffmpeg", root / "bin" / "ffprobe"):
        for dependency in _otool_dependencies(binary):
            if not (
                _is_system_load_path(dependency)
                or dependency.startswith("@loader_path/../lib/media/")
            ):
                raise RuntimeError(f"desktop media load path is not relocatable: {dependency}")
    version = _run([root / "bin" / "ffmpeg", "-version"], capture_output=True).stdout
    if "License: GPL" in version or "--enable-gpl" in version or "--enable-nonfree" in version:
        raise RuntimeError("desktop FFmpeg version output is not LGPL-only")
    if exercise:
        _exercise_runtime(root)
    return manifest


def build_runtime(*, force: bool = False) -> dict[str, Any]:
    _require_macos_arm64()
    output = default_runtime_root()
    if not force:
        try:
            return validate_runtime(output)
        except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError):
            pass
    contract = load_build_contract()
    results = default_results_root()
    sources = results / "sources"
    archives = {
        str(source["name"]): _download_source(source, sources)
        for source in contract["sources"]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".desktop-media-build-",
        dir=output.parent,
    ) as temporary:
        temporary_root = Path(temporary)
        build_root = temporary_root / "build"
        build_root.mkdir()
        source_trees = {
            name: _extract_source(archive, build_root)
            for name, archive in archives.items()
        }
        sysroot = temporary_root / "sysroot"
        prefix = str(contract["install_prefix"])
        prefix_root = sysroot / prefix.removeprefix("/")
        jobs = str(min(os.cpu_count() or 2, 14))
        lame_root = source_trees["lame"]
        _run(
            ["./configure", f"--prefix={prefix}", *contract["lame_configure"]],
            cwd=lame_root,
        )
        _run(["make", f"-j{jobs}"], cwd=lame_root)
        _run(["make", "install", f"DESTDIR={sysroot}"], cwd=lame_root)
        ffmpeg_root = source_trees["ffmpeg"]
        build_env = dict(os.environ)
        build_env["CFLAGS"] = f"-I{prefix_root / 'include'}"
        build_env["LDFLAGS"] = f"-L{prefix_root / 'lib'}"
        _run(
            ["./configure", f"--prefix={prefix}", *contract["ffmpeg_configure"]],
            cwd=ffmpeg_root,
            env=build_env,
        )
        _run(["make", f"-j{jobs}"], cwd=ffmpeg_root, env=build_env)
        _run(
            ["make", "install", f"DESTDIR={sysroot}"],
            cwd=ffmpeg_root,
            env=build_env,
        )
        runtime = temporary_root / "runtime"
        _relocate_runtime(prefix_root, runtime)
        _copy_notices(contract, source_trees, runtime)
        version_lines = _run(
            [runtime / "bin" / "ffmpeg", "-version"],
            capture_output=True,
        ).stdout.splitlines()
        configuration = next(
            line.removeprefix("configuration: ")
            for line in version_lines
            if line.startswith("configuration: ")
        )
        manifest = {
            "schema_version": RUNTIME_SCHEMA,
            "target": contract["target"],
            "build_identity": _contract_identity(contract),
            "ffmpeg_version": version_lines[0],
            "configuration": configuration,
            "license": "LGPL-only",
            "file_hash_scope": (
                "relocated ad-hoc media output before product distribution signing"
            ),
            "sources": contract["sources"],
            "files": _runtime_files(runtime),
        }
        (runtime / "build-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validate_runtime(runtime)
        if output.exists():
            shutil.rmtree(output)
        runtime.replace(output)
    return validate_runtime(output)


def _tar_info(name: str, contents: bytes, mode: int = 0o644) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(contents)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "wheel"
    return info, contents


def _validate_version(version: str) -> None:
    if len(version.split(".")) != 3 or not all(
        part.isdigit() for part in version.split(".")
    ):
        raise RuntimeError(f"invalid desktop media source version: {version}")


def _tracked_source_archive_files() -> dict[str, tuple[Path, int]]:
    repository = repository_root()
    return {
        "desktop-media/manifest.json": (
            repository / "desktop-media" / "manifest.json",
            0o644,
        ),
        "desktop-media/README.md": (
            repository / "desktop-media" / "README.md",
            0o644,
        ),
        "THIRD_PARTY_NOTICES.md": (repository / "THIRD_PARTY_NOTICES.md", 0o644),
        "scripts/build-atpiano-media-runtime": (
            repository / "scripts" / "build-atpiano-media-runtime",
            0o755,
        ),
        "src/atpiano/desktop_media.py": (
            repository / "src" / "atpiano" / "desktop_media.py",
            0o644,
        ),
    }


def _source_archive_entries(
    contract: Mapping[str, Any],
) -> dict[str, tuple[bytes, int]]:
    source_root = default_results_root() / "sources"
    prefix = "atpiano-media-sources"
    entries = {}
    for source in contract["sources"]:
        path = _download_source(source, source_root)
        entries[f"{prefix}/upstream/{source['archive']}"] = (path.read_bytes(), 0o644)
    for name, (path, mode) in _tracked_source_archive_files().items():
        entries[f"{prefix}/build/{name}"] = (path.read_bytes(), mode)
    return entries


def write_source_archive(version: str, output: Path) -> Path:
    _validate_version(version)
    contract = load_build_contract()
    entries = _source_archive_entries(contract)
    prefix = "atpiano-media-sources"
    contents_manifest = {
        "schema_version": SOURCE_ARCHIVE_SCHEMA,
        "atpiano_version": version,
        "build_identity": _contract_identity(contract),
        "files": [
            {
                "path": name,
                "bytes": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
            }
            for name, (contents, _mode) in sorted(entries.items())
        ],
    }
    manifest_contents = (
        json.dumps(contents_manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    entries[f"{prefix}/MANIFEST.json"] = (manifest_contents, 0o644)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, (contents, mode) in sorted(entries.items()):
                    info, payload = _tar_info(name, contents, mode)
                    archive.addfile(info, io.BytesIO(payload))
    os.replace(temporary, output)
    return output


def validate_source_archive(version: str, archive: Path) -> dict[str, Any]:
    _validate_version(version)
    expected_name = f"Atpiano_{version}_media-sources.tar.gz"
    if archive.name != expected_name:
        raise RuntimeError(
            f"desktop media source archive must be named {expected_name}"
        )
    prefix = "atpiano-media-sources"
    manifest_name = f"{prefix}/MANIFEST.json"
    with tarfile.open(archive, mode="r:gz") as bundle:
        members = bundle.getmembers()
        if any(
            not member.isfile()
            or PurePosixPath(member.name).is_absolute()
            or ".." in PurePosixPath(member.name).parts
            for member in members
        ):
            raise RuntimeError("desktop media source archive has an unsafe entry")
        by_name = {member.name: member for member in members}
        if len(by_name) != len(members) or manifest_name not in by_name:
            raise RuntimeError("desktop media source archive entries are invalid")
        manifest_handle = bundle.extractfile(by_name[manifest_name])
        if manifest_handle is None:
            raise RuntimeError("desktop media source archive manifest is unreadable")
        manifest = json.loads(manifest_handle.read())
        if manifest.get("schema_version") != SOURCE_ARCHIVE_SCHEMA:
            raise RuntimeError("desktop media source archive schema is unsupported")
        if manifest.get("atpiano_version") != version:
            raise RuntimeError("desktop media source archive version does not match")
        contract = load_build_contract()
        if manifest.get("build_identity") != _contract_identity(contract):
            raise RuntimeError("desktop media source archive build identity changed")
        inventory = manifest.get("files")
        if not isinstance(inventory, list):
            raise RuntimeError("desktop media source archive inventory is missing")
        expected_files = {
            item.get("path"): item for item in inventory if isinstance(item, dict)
        }
        actual_files = set(by_name) - {manifest_name}
        if set(expected_files) != actual_files:
            raise RuntimeError("desktop media source archive inventory does not reconcile")
        for name, item in expected_files.items():
            handle = bundle.extractfile(by_name[name])
            if handle is None:
                raise RuntimeError(f"desktop media source archive entry is unreadable: {name}")
            contents = handle.read()
            changed = len(contents) != item.get("bytes") or (
                hashlib.sha256(contents).hexdigest() != item.get("sha256")
            )
            if changed:
                raise RuntimeError(f"desktop media source archive hash changed: {name}")
        expected_entries = _source_archive_entries(contract)
        if set(expected_entries) != actual_files:
            raise RuntimeError("desktop media source archive content set changed")
        for name, (contents, _mode) in expected_entries.items():
            handle = bundle.extractfile(by_name[name])
            if handle is None or handle.read() != contents:
                raise RuntimeError(f"desktop media source does not match the build: {name}")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scripts/build-atpiano-media-runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ensure")
    commands.add_parser("rebuild")
    commands.add_parser("validate")
    archive = commands.add_parser("source-archive")
    archive.add_argument("--version", required=True)
    archive.add_argument("--output", type=Path, required=True)
    validate_archive = commands.add_parser("validate-source-archive")
    validate_archive.add_argument("--version", required=True)
    validate_archive.add_argument("--archive", type=Path, required=True)
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    if args.command == "ensure":
        result = build_runtime()
        print(f"Validated LGPL media runtime {result['build_identity']}")
    elif args.command == "rebuild":
        result = build_runtime(force=True)
        print(f"Rebuilt LGPL media runtime {result['build_identity']}")
    elif args.command == "validate":
        result = validate_runtime()
        print(f"Validated LGPL media runtime {result['build_identity']}")
    elif args.command == "source-archive":
        output = write_source_archive(args.version, args.output)
        print(output)
    else:
        result = validate_source_archive(args.version, args.archive)
        print(
            "Validated corresponding media sources "
            f"{result['build_identity']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
