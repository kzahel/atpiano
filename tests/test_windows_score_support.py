from __future__ import annotations

import hashlib
import json
import stat
import struct
from pathlib import Path

import pytest

from atpiano import windows_score_support


def test_resolves_relative_managed_python_against_home(tmp_path: Path) -> None:
    executable = tmp_path / "managed" / "python.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"python")

    assert windows_score_support._resolve_managed_python_path(
        "managed/python.exe",
        home=tmp_path,
    ) == executable.resolve()


def test_tree_hash_uses_platform_independent_string_order(tmp_path: Path) -> None:
    first = tmp_path / "package-1.dist-info" / "METADATA"
    second = tmp_path / "package" / "module.py"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"metadata")
    second.write_bytes(b"module")
    expected = hashlib.sha256()
    for relative, contents in (
        ("package-1.dist-info/METADATA", b"metadata"),
        ("package/module.py", b"module"),
    ):
        expected.update(relative.encode("utf-8"))
        expected.update(b"\0")
        expected.update(hashlib.sha256(contents).digest())

    assert windows_score_support._tree_sha256_without(tmp_path, set()) == (
        expected.hexdigest()
    )


def _write_pe(path: Path, machine: int) -> None:
    header = bytearray(128)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 64)
    header[64:68] = b"PE\0\0"
    struct.pack_into("<H", header, 68, machine)
    path.write_bytes(header)


def test_pe_audit_accepts_only_x64_native_files(tmp_path: Path) -> None:
    native = tmp_path / "python.exe"
    _write_pe(native, windows_score_support.PE_X86_64_MACHINE)

    assert windows_score_support._audit_native(tmp_path) == [
        {
            "path": "python.exe",
            "bytes": 128,
            "machine": "x86_64",
        }
    ]

    _write_pe(native, 0xAA64)
    with pytest.raises(RuntimeError, match="non-x64 PE"):
        windows_score_support._audit_native(tmp_path)


def test_acquisition_contract_matches_windows_support_inputs() -> None:
    repository = Path(__file__).resolve().parents[1]

    contract = windows_score_support._read_acquisition_contract(repository)

    assert contract["support_layer_id"] == windows_score_support.SUPPORT_LAYER_ID


def test_vcs_requirements_are_exact(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text(
        "\n".join(
            (
                "music21 @ git+https://example.test/music21@commit",
                "muster @ git+https://example.test/muster@commit",
                "score-transformer @ git+https://example.test/score@commit",
            )
        ),
        encoding="utf-8",
    )

    requirements = windows_score_support._vcs_requirements(path)

    assert set(requirements) == {"music21", "muster", "score-transformer"}


def test_cleanup_handles_read_only_build_files(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    read_only = root / "runtime.dll"
    read_only.write_bytes(b"native")
    read_only.chmod(stat.S_IREAD)

    windows_score_support._remove_tree(root)

    assert not root.exists()


def test_pruning_preserves_license_material_named_testing(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    package_tests = site_packages / "example" / "tests"
    license_tests = (
        site_packages / "example-1.0.dist-info" / "licenses" / "vendor" / "testing"
    )
    package_tests.mkdir(parents=True)
    license_tests.mkdir(parents=True)

    windows_score_support._prune_distribution_test_material(site_packages)

    assert not package_tests.exists()
    assert license_tests.is_dir()


def test_pruning_removes_build_only_windows_launchers(tmp_path: Path) -> None:
    python_root = tmp_path / ".venv"
    setuptools = python_root / "Lib" / "site-packages" / "setuptools"
    launcher = setuptools / "cli-32.exe"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes(b"launcher")
    venv = python_root / "Lib" / "venv" / "scripts" / "nt"
    venv.mkdir(parents=True)
    (venv / "redirector.exe").write_bytes(b"launcher")
    license_file = (
        python_root
        / "Lib"
        / "site-packages"
        / "setuptools-80.dist-info"
        / "licenses"
        / "LICENSE"
    )
    license_file.parent.mkdir(parents=True)
    license_file.write_bytes(b"license")

    windows_score_support._prune_python(python_root)

    assert not launcher.exists()
    assert not venv.exists()


def test_distribution_licenses_are_flattened_with_provenance(tmp_path: Path) -> None:
    python_root = tmp_path / ".venv"
    license_file = (
        python_root
        / "Lib"
        / "site-packages"
        / "torch-2.13.0.dist-info"
        / "licenses"
        / "third_party"
        / "deep"
        / "testing"
        / "LICENSE"
    )
    license_file.parent.mkdir(parents=True)
    license_file.write_bytes(b"retained license")

    windows_score_support._flatten_distribution_licenses(
        python_root / "Lib" / "site-packages",
        python_root,
    )

    assert not license_file.exists()
    result = windows_score_support._audit_flattened_licenses(python_root)
    assert result["file_count"] == 1
    manifest = json.loads(
        (
            python_root
            / "share"
            / "licenses"
            / "python"
            / "license-material.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["files"][0]["original_path"] == (
        "third_party/deep/testing/LICENSE"
    )
