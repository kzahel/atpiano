from __future__ import annotations

import json
from pathlib import Path

import pytest

from atpiano.cli import build_parser
from atpiano.product.contract_generation import (
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
        "/api/product/v1/workspaces/{workspace_id}/sessions/{session_id}"
    )
    assert paths[session_path]["get"]["operationId"] == "getSession"
    assert paths[session_path]["delete"]["operationId"] == "deleteSession"
    assert paths["/api/product/v1/captures"]["post"]["operationId"] == (
        "startCapture"
    )


def test_generation_check_detects_drift(tmp_path: Path) -> None:
    product = tmp_path / "product"
    executable = product / "node_modules" / ".bin" / "openapi-typescript"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/bin/sh\n"
        "while [ \"$1\" != \"-o\" ]; do shift; done\n"
        "printf 'generated\\n' > \"$2\"\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    openapi, typescript = generate_contracts(root=tmp_path)

    assert openapi == tmp_path / OPENAPI_RELATIVE_PATH
    assert typescript == tmp_path / TYPESCRIPT_RELATIVE_PATH
    assert json.loads(openapi.read_text(encoding="utf-8"))["openapi"] == "3.1.0"
    assert typescript.read_text(encoding="utf-8") == "generated\n"
    generate_contracts(root=tmp_path, check=True)
    typescript.write_text("drifted\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="generated product contracts"):
        generate_contracts(root=tmp_path, check=True)
