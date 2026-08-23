from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from atpiano.util import (
    process_rss_high_water_bytes,
    resolve_command,
    sha256_file,
    sha256_path,
    write_json,
    write_jsonl,
)


def test_tree_hash_uses_case_sensitive_relative_path_order(tmp_path: Path) -> None:
    files = {
        "README.md": b"upper",
        "midi/model.py": b"lower",
        "Tokenization.pdf": b"mixed",
    }
    for relative, content in files.items():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    expected = hashlib.sha256()
    for relative in sorted(files):
        expected.update(relative.encode("utf-8"))
        expected.update(b"\0")
        expected.update(bytes.fromhex(sha256_file(tmp_path / relative)))

    assert sha256_path(tmp_path) == expected.hexdigest()


def test_atomic_replace_retries_transient_windows_access_denial(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts = 0
    original_replace = __import__("os").replace

    def replace(source: Path, destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("target is briefly open")
        original_replace(source, destination)

    monkeypatch.setattr("atpiano.util.sys.platform", "win32")
    monkeypatch.setattr("atpiano.util.os.replace", replace)
    monkeypatch.setattr("atpiano.util.time.sleep", lambda _seconds: None)

    destination = tmp_path / "destination.json"
    write_json(destination, {"value": 1})

    assert attempts == 3
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "value": 1
    }


def test_resolve_command_uses_path_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        "atpiano.util.shutil.which",
        lambda executable: f"resolved/{executable}.cmd",
    )

    assert resolve_command(("npm", "test")) == [
        "resolved/npm.cmd",
        "test",
    ]


def test_process_rss_high_water_is_positive() -> None:
    assert process_rss_high_water_bytes() > 0


def test_json_writers_use_platform_independent_line_endings(
    tmp_path: Path,
) -> None:
    document = tmp_path / "document.json"
    rows = tmp_path / "rows.jsonl"

    write_json(document, {"value": 1})
    write_jsonl(rows, [{"value": 1}, {"value": 2}])

    assert b"\r\n" not in document.read_bytes()
    assert b"\r\n" not in rows.read_bytes()


def test_json_writer_uses_unique_temporary_files_for_concurrent_writes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    destination = tmp_path / "state.json"
    original_open = Path.open
    fixed_temporary_barrier = threading.Barrier(2)

    def synchronized_open(path: Path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        if path.name == ".state.json.tmp":
            fixed_temporary_barrier.wait(timeout=2)
        return handle

    monkeypatch.setattr(Path, "open", synchronized_open)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(write_json, destination, {"value": value})
            for value in (1, 2)
        ]
        for future in futures:
            future.result()

    assert json.loads(destination.read_text(encoding="utf-8"))["value"] in {
        1,
        2,
    }
    assert list(tmp_path.glob(".state.json.*.tmp")) == []
