"""Strict contracts for user-acquired desktop score generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atpiano.desktop import require_supported_desktop_identity
from atpiano.util import read_json

SCORE_ACQUISITION_SCHEMA = "atpiano.score-acquisition.v1"
SCORE_ACKNOWLEDGEMENT_SCHEMA = "atpiano.score-acknowledgement.v1"
SCORE_INSTALLATION_SCHEMA = "atpiano.score-runtime-installation.v1"


class ScoreSourceAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_url: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    archive_url: str
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_bytes: int = Field(gt=0)
    archive_root: str
    tree_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    maximum_entry_count: int = Field(gt=0, le=10_000)
    maximum_expanded_bytes: int = Field(gt=0)


class ScoreCheckpointAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_url: str
    download_url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0)


class ScoreTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["macos", "windows"]
    architecture: Literal["arm64", "x86_64"]

    @model_validator(mode="after")
    def require_supported_pair(self) -> ScoreTarget:
        require_supported_desktop_identity(self.platform, self.architecture)
        return self


class ScoreAcquisitionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atpiano.score-acquisition.v1"]
    contract_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]+$")
    notice_version: str
    model_name: str
    purpose: str
    notice: str
    acknowledgement: str
    source: ScoreSourceAsset
    checkpoint: ScoreCheckpointAsset
    paper_url: str
    allowed_https_hosts: tuple[str, ...]
    support_layer_id: str
    supported_targets: tuple[ScoreTarget, ...]
    score_runtime_schema: Literal["atpiano.midi2score-runtime.v2"]
    score_pipeline_revision: Literal[4]
    execution_backend: Literal["cpu"]
    download_bytes: int = Field(gt=0)
    installed_space_estimate_bytes: int = Field(gt=0)
    minimum_free_bytes: int = Field(gt=0)

    @model_validator(mode="after")
    def require_exact_asset_boundaries(self) -> ScoreAcquisitionContract:
        urls = (
            self.source.repository_url,
            self.source.archive_url,
            self.checkpoint.release_url,
            self.checkpoint.download_url,
            self.paper_url,
        )
        allowed_hosts = set(self.allowed_https_hosts)
        if not allowed_hosts or len(allowed_hosts) != len(self.allowed_https_hosts):
            raise ValueError("score acquisition hosts must be unique")
        for value in urls:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port is not None
                or parsed.fragment
            ):
                raise ValueError("score acquisition URLs must be plain HTTPS URLs")
            if parsed.hostname not in allowed_hosts:
                raise ValueError("score acquisition URL host is not allowed")
        expected_targets = {("macos", "arm64"), ("windows", "x86_64")}
        actual_targets = {
            (target.platform, target.architecture)
            for target in self.supported_targets
        }
        if actual_targets != expected_targets or len(self.supported_targets) != 2:
            raise ValueError("score acquisition targets do not match the release")
        if self.download_bytes != (
            self.source.archive_bytes + self.checkpoint.bytes
        ):
            raise ValueError("score acquisition download size is inconsistent")
        if self.minimum_free_bytes <= self.installed_space_estimate_bytes:
            raise ValueError("score acquisition free-space bound is too small")
        return self


class ScoreAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atpiano.score-acknowledgement.v1"]
    contract_id: str
    notice_version: str
    accepted_at: datetime
    application_version: str
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScoreRuntimeInstallation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atpiano.score-runtime-installation.v1"]
    contract_id: str
    notice_version: str
    runtime_relative_path: str
    platform: Literal["macos", "windows"]
    architecture: Literal["arm64", "x86_64"]
    support_layer_id: str
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    installed_bytes: int = Field(gt=0)
    validated_at: datetime

    @model_validator(mode="after")
    def require_safe_installation(self) -> ScoreRuntimeInstallation:
        require_supported_desktop_identity(self.platform, self.architecture)
        relative = Path(self.runtime_relative_path)
        if relative.is_absolute() or relative.parts != (self.contract_id,):
            raise ValueError("score runtime installation path is invalid")
        return self


def load_score_acquisition_contract(path: Path) -> ScoreAcquisitionContract:
    return ScoreAcquisitionContract.model_validate(read_json(path))
