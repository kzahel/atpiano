from __future__ import annotations

from pathlib import Path

from atpiano.util import (
    process_rss_high_water_bytes,
    resolve_command,
    write_json,
    write_jsonl,
)


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
