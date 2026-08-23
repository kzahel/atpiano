from __future__ import annotations

import hashlib
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
