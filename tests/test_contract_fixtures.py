from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from atpiano.contracts.schemas import contract_models

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "contracts"
    / "fixtures"
    / "v1"
    / "contract-examples.json"
)


def _fixture_document() -> dict[str, object]:
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_shared_contract_examples_validate_in_python() -> None:
    models: dict[str, type[BaseModel]] = {
        model.__name__: model for model in contract_models()
    }
    document = _fixture_document()

    assert document["schema_version"] == "atpiano.contract-examples.v1"
    objects = document["objects"]
    assert isinstance(objects, list)
    assert len(objects) >= 15
    for fixture in objects:
        assert isinstance(fixture, dict)
        model = models[str(fixture["model"])]
        validated = model.model_validate(fixture["value"])
        assert validated.model_dump(mode="json") == fixture["value"]


def test_shared_contract_examples_reject_incompatible_version() -> None:
    document = _fixture_document()
    objects = document["objects"]
    assert isinstance(objects, list)
    workspace = next(
        fixture
        for fixture in objects
        if isinstance(fixture, dict) and fixture.get("model") == "Workspace"
    )
    value = workspace["value"]
    assert isinstance(value, dict)

    from atpiano.contracts.schemas import Workspace

    with pytest.raises(ValidationError, match="atpiano.contract.v1"):
        Workspace.model_validate(value | {"schema_version": "atpiano.contract.v2"})
