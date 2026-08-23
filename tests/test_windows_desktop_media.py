from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from atpiano import windows_desktop_media


def test_tracked_windows_media_contract_is_exact() -> None:
    contract = windows_desktop_media.load_contract()

    assert contract["target"] == "windows-x86_64"
    assert contract["license"] == {
        "mode": "LGPL",
        "variant": "shared",
        "bundled_file": "LICENSE.txt",
    }
    assert contract["payload"]["executables"] == ["ffmpeg.exe", "ffprobe.exe"]


def test_windows_media_contract_rejects_a_gpl_variant() -> None:
    contract = copy.deepcopy(windows_desktop_media.load_contract())
    contract["license"]["mode"] = "GPL"

    with pytest.raises(RuntimeError, match="shared LGPL"):
        windows_desktop_media.validate_contract(contract)


def test_windows_media_archive_hash_is_enforced(tmp_path: Path) -> None:
    archive = tmp_path / "ffmpeg.zip"
    archive.write_bytes(b"unexpected")

    with pytest.raises(RuntimeError, match="SHA-256"):
        windows_desktop_media.validate_archive(
            archive,
            windows_desktop_media.load_contract(),
        )


def _write_test_archive(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    contract = copy.deepcopy(windows_desktop_media.load_contract())
    archive = tmp_path / "media.zip"
    root = str(contract["archive"]["payload_root"])
    names = [
        *contract["payload"]["executables"],
        *contract["payload"]["libraries"],
    ]
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in names:
            bundle.writestr(f"{root}/bin/{name}", f"native:{name}".encode())
        bundle.writestr(f"{root}/LICENSE.txt", b"LGPL test license")
    contract["archive"]["name"] = archive.name
    contract["archive"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, contract


def test_stages_only_the_declared_windows_media_payload(tmp_path: Path) -> None:
    archive, contract = _write_test_archive(tmp_path)
    runtime = tmp_path / "runtime"

    result = windows_desktop_media.stage_runtime(
        runtime,
        archive_path=archive,
        contract=contract,
        exercise=False,
    )

    assert result["status"] == "passed"
    assert result["file_count"] == 10
    assert not (runtime / "bin" / "ffplay.exe").exists()
    manifest = json.loads(
        (runtime / "media-build-manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["files"]) == 10


def test_runtime_validation_detects_media_mutation(tmp_path: Path) -> None:
    archive, contract = _write_test_archive(tmp_path)
    runtime = tmp_path / "runtime"
    windows_desktop_media.stage_runtime(
        runtime,
        archive_path=archive,
        contract=contract,
        exercise=False,
    )
    (runtime / "bin" / "ffmpeg.exe").write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="inventory changed"):
        windows_desktop_media.validate_runtime(
            runtime,
            contract=contract,
            exercise=False,
        )
