from __future__ import annotations

import copy
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
