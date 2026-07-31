from __future__ import annotations

import json
from pathlib import Path

import pytest

from atpiano.cli import build_parser
from atpiano.contracts.generation import (
    MIDI_TICK_FIXTURE_RELATIVE_PATH,
    OPENAPI_RELATIVE_PATH,
    TYPESCRIPT_RELATIVE_PATH,
    build_openapi_document,
    generate_contracts,
)


def test_contract_generation_cli_supports_drift_check() -> None:
    args = build_parser().parse_args(["generate-contracts", "--check"])

    assert args.command == "generate-contracts"
    assert args.check is True


def test_openapi_uses_explicit_targets_and_pydantic_components() -> None:
    document = build_openapi_document()

    assert document["openapi"] == "3.1.0"
    assert "Session" in document["components"]["schemas"]
    paths = document["paths"]
    session_path = (
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
    )
    assert paths[session_path]["get"]["operationId"] == "getSession"
    assert (
        paths[session_path]["patch"]["operationId"]
        == "updateSessionAnnotation"
    )
    assert paths[session_path]["delete"]["operationId"] == "deleteSession"
    assert paths[
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/score-jobs"
        )
    ]["post"]["operationId"] == (
        "startScoreJob"
    )
    import_operation = paths[
        "/api/v1/workspaces/{workspace_id}/recording-imports"
    ]["post"]
    assert import_operation["operationId"] == "importRecording"
    assert "audio/wav" in import_operation["requestBody"]["content"]


def test_generation_check_detects_drift(tmp_path: Path) -> None:
    app = tmp_path / "app"
    executable = (
        app
        / "node_modules"
        / "openapi-typescript"
        / "bin"
        / "cli.js"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text(
        'const fs = require("node:fs");\n'
        'const output = process.argv[process.argv.indexOf("-o") + 1];\n'
        'fs.writeFileSync(output, "generated\\n");\n',
        encoding="utf-8",
    )

    openapi, typescript, midi_ticks = generate_contracts(root=tmp_path)

    assert openapi == tmp_path / OPENAPI_RELATIVE_PATH
    assert typescript == tmp_path / TYPESCRIPT_RELATIVE_PATH
    assert json.loads(openapi.read_text(encoding="utf-8"))["openapi"] == "3.1.0"
    assert typescript.read_text(encoding="utf-8") == "generated\n"
    assert midi_ticks == tmp_path / MIDI_TICK_FIXTURE_RELATIVE_PATH
    assert json.loads(midi_ticks.read_text(encoding="utf-8"))[
        "operation_identity"
    ] == "mido-second2tick-float-python-half-even-v1"
    generate_contracts(root=tmp_path, check=True)
    typescript.write_text("drifted\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="generated contracts"):
        generate_contracts(root=tmp_path, check=True)
