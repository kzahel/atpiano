from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_score_support_uses_a_short_independent_workspace(tmp_path: Path) -> None:
    destination = tmp_path / "deep" / "desktop-runtime" / "score-support"
    destination.parent.mkdir(parents=True)
    repository = tmp_path / "repository"
    repository.mkdir()

    def stage(output: Path, _: Path) -> None:
        output.mkdir(parents=True)
        (output / "support-manifest.json").write_text("{}", encoding="utf-8")

    build_root = tmp_path / "short"
    build_root.mkdir()
    with (
        patch(
            "atpiano.windows_desktop_packaging._score_build_root",
            return_value=build_root,
        ),
        patch(
            "atpiano.windows_desktop_packaging.stage_windows_score_support",
            side_effect=stage,
        ) as mocked,
    ):
        windows_desktop_packaging._stage_score_support(destination, repository)

    working_output = mocked.call_args.args[0]
    assert destination.is_dir()
    assert working_output.parent == build_root.resolve()


def test_score_build_root_fails_with_actionable_long_path(tmp_path: Path) -> None:
    long_root = Path("C:/") / ("a" * 61)

    with pytest.raises(RuntimeError, match="ATPIANO_WINDOWS_BUILD_ROOT"):
        windows_desktop_packaging._validate_score_build_root(long_root)


def test_windows_tauri_package_is_current_user_nsis() -> None:
    repository = Path(__file__).resolve().parents[1]
    config = json.loads(
        (repository / "app" / "src-tauri" / "tauri.windows.conf.json").read_text(
            encoding="utf-8"
        )
    )

    assert config["bundle"]["targets"] == ["nsis"]
    assert config["bundle"]["windows"] == {
        "allowDowngrades": False,
        "webviewInstallMode": {"type": "embedBootstrapper", "silent": False},
        "nsis": {
            "installMode": "currentUser",
            "languages": ["English"],
            "displayLanguageSelector": False,
            "compression": "lzma",
        },
    }
    assert config["plugins"]["updater"]["windows"]["installMode"] == "passive"
