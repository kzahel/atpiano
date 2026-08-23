from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from atpiano.desktop_score import (
    ScoreAcknowledgement,
    ScoreAcquisitionContract,
    ScoreRuntimeInstallation,
    load_score_acquisition_contract,
)
from atpiano.util import read_json


def _contract_path() -> Path:
    return Path(__file__).resolve().parents[1] / "desktop-score" / "acquisition.json"


def test_tracked_score_acquisition_contract_is_exact() -> None:
    contract = load_score_acquisition_contract(_contract_path())

    assert contract.contract_id == "midi2score-research-2026.08"
    assert contract.source.archive_bytes == 187_103
    assert contract.checkpoint.bytes == 389_829_880
    assert contract.download_bytes == 390_016_983
    assert {
        (target.platform, target.architecture)
        for target in contract.supported_targets
    } == {("macos", "arm64"), ("windows", "x86_64")}


def test_score_acquisition_contract_rejects_drift() -> None:
    document = read_json(_contract_path())
    for mutate in (
        lambda value: value.update({"unexpected": True}),
        lambda value: value["source"].update({"archive_url": "http://example.com/model.zip"}),
        lambda value: value.update({"download_bytes": 1}),
        lambda value: value["supported_targets"].append(
            {"platform": "windows", "architecture": "x86_64"}
        ),
    ):
        candidate = deepcopy(document)
        mutate(candidate)
        with pytest.raises(ValidationError):
            ScoreAcquisitionContract.model_validate(candidate)


def test_score_receipts_reject_unknown_and_unsafe_paths() -> None:
    now = datetime.now(timezone.utc)
    acknowledgement = {
        "schema_version": "atpiano.score-acknowledgement.v1",
        "contract_id": "midi2score-research-2026.08",
        "notice_version": "midi2score-research-notice-v1",
        "accepted_at": now,
        "application_version": "0.1.0",
        "source_archive_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
    }
    ScoreAcknowledgement.model_validate(acknowledgement)
    with pytest.raises(ValidationError):
        ScoreAcknowledgement.model_validate({**acknowledgement, "identity": "forbidden"})

    installation = {
        "schema_version": "atpiano.score-runtime-installation.v1",
        "contract_id": "midi2score-research-2026.08",
        "notice_version": "midi2score-research-notice-v1",
        "runtime_relative_path": "midi2score-research-2026.08",
        "platform": "windows",
        "architecture": "x86_64",
        "support_layer_id": "atpiano-midi2score-support-py311-2026.08",
        "source_archive_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "installed_bytes": 1_500_000_000,
        "validated_at": now,
    }
    ScoreRuntimeInstallation.model_validate(installation)
    for invalid_path in ("../escape", "nested/runtime", "/absolute"):
        with pytest.raises(ValidationError):
            ScoreRuntimeInstallation.model_validate(
                {**installation, "runtime_relative_path": invalid_path}
            )
