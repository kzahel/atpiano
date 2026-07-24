from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from atpiano.reviewer import create_server


def _write_run(run_directory: Path) -> None:
    values = {
        "run.json": {"run_id": "test"},
        "scores.json": {"schema_version": "atpiano.scores.v1"},
        "reference.json": {"schema_version": "atpiano.note-set.v1", "notes": []},
        "prediction.json": {"schema_version": "atpiano.note-set.v1", "notes": []},
    }
    for name, value in values.items():
        (run_directory / name).write_text(json.dumps(value), encoding="utf-8")


def test_reviewer_serves_assets_and_run_files(tmp_path: Path) -> None:
    _write_run(tmp_path)
    server = create_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            assert response.status == 200
            assert b"Atpiano" in response.read()
        with urllib.request.urlopen(
            f"{base_url}/artifacts/run.json",
            timeout=2,
        ) as response:
            assert json.load(response)["run_id"] == "test"
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(
                f"{base_url}/artifacts/../pyproject.toml",
                timeout=2,
            )
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
