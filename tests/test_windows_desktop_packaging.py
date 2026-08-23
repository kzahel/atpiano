from __future__ import annotations

import json
from pathlib import Path

from atpiano import windows_desktop_packaging


def test_resolves_relative_managed_python_against_home(tmp_path: Path) -> None:
    executable = tmp_path / "managed" / "python.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"python")

    assert windows_desktop_packaging._resolve_managed_python_path(
        "managed/python.exe",
        home=tmp_path,
    ) == executable.resolve()


def test_stages_windows_onnx_model_pack(tmp_path: Path) -> None:
    site_packages = tmp_path / "Lib" / "site-packages"
    assets = {
        relative: f"asset:{name}".encode()
        for name, relative in windows_desktop_packaging.MODEL_ASSET_PATHS.items()
    }
    for relative, contents in assets.items():
        path = site_packages / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    pack = windows_desktop_packaging._stage_model_pack(site_packages, tmp_path)

    assert (pack.platform, pack.architecture) == ("windows", "x86_64")
    assert pack.assets[0].path == "basic-pitch/nmp.onnx"
    assert not (site_packages / "basic_pitch" / "saved_models").exists()
    assert not (site_packages / "transkun" / "pretrained").exists()
    assert json.loads(
        (tmp_path / "model-pack" / "model-pack.json").read_text(encoding="utf-8")
    )["platform"] == "windows"


def test_package_identity_is_stable_and_minimal() -> None:
    packages = [
        {"name": "torch", "version": "2.13.0", "installed_bytes": 1},
        {"name": "Atpiano", "version": "0.1.0", "installed_bytes": 2},
    ]

    assert windows_desktop_packaging._package_identities(packages) == [
        {"name": "Atpiano", "version": "0.1.0"},
        {"name": "torch", "version": "2.13.0"},
    ]
