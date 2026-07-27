"""Versioned desktop-sidecar handshake and model-pack contracts."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atpiano import __version__
from atpiano.contracts import CONTRACT_SCHEMA_VERSION, PCM_PROTOCOL_VERSION
from atpiano.util import sha256_path

DESKTOP_PROTOCOL_VERSION = "atpiano.desktop.v1"
DESKTOP_READY_SCHEMA = "atpiano.desktop-ready.v1"
DESKTOP_HANDSHAKE_SCHEMA = "atpiano.desktop-handshake.v1"
MODEL_PACK_SCHEMA = "atpiano.model-pack.v1"
DESKTOP_TOKEN_ENV = "ATPIANO_DESKTOP_TOKEN"
DESKTOP_TOKEN_PATTERN = re.compile(r"[0-9a-f]{64}")
DESKTOP_WEBSOCKET_PREFIX = f"{DESKTOP_PROTOCOL_VERSION}."
MAX_DESKTOP_READY_BYTES = 64 * 1024


class ModelAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    adapter: str
    package: str
    package_version: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["file", "directory"]


class ModelPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atpiano.model-pack.v1"] = MODEL_PACK_SCHEMA
    model_pack_id: str
    platform: Literal["macos"]
    architecture: Literal["arm64"]
    execution_backend: Literal["cpu"]
    assets: tuple[ModelAsset, ...]

    @model_validator(mode="after")
    def require_runtime_models(self) -> ModelPack:
        asset_ids = {asset.asset_id for asset in self.assets}
        required = {"basic-pitch-icassp-2022", "transkun-2.0"}
        if not required.issubset(asset_ids):
            missing = ", ".join(sorted(required - asset_ids))
            raise ValueError(f"model pack is missing: {missing}")
        return self


class DesktopReady(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atpiano.desktop-ready.v1"] = DESKTOP_READY_SCHEMA
    protocol_version: Literal["atpiano.desktop.v1"] = DESKTOP_PROTOCOL_VERSION
    contract_schema_version: Literal[
        "atpiano.contract.v1"
    ] = CONTRACT_SCHEMA_VERSION
    sidecar_version: str
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(gt=0, le=65535)
    platform: Literal["macos"]
    architecture: Literal["arm64"]
    execution_backend: Literal["cpu"]
    model_pack_id: str
    model_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DesktopHandshake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "atpiano.desktop-handshake.v1"
    ] = DESKTOP_HANDSHAKE_SCHEMA
    compatible: Literal[True] = True
    protocol_version: Literal["atpiano.desktop.v1"] = DESKTOP_PROTOCOL_VERSION
    contract_schema_version: Literal[
        "atpiano.contract.v1"
    ] = CONTRACT_SCHEMA_VERSION
    pcm_protocol_version: str = PCM_PROTOCOL_VERSION
    sidecar_version: str
    python_version: str
    platform: Literal["macos"]
    architecture: Literal["arm64"]
    execution_backend: Literal["cpu"]
    model_pack: ModelPack
    model_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    storage_policy: Literal["verified-mp3-default"] = "verified-mp3-default"
    score_available: bool = False


def validate_desktop_token(raw_token: str) -> str:
    if DESKTOP_TOKEN_PATTERN.fullmatch(raw_token) is None:
        raise ValueError(
            "desktop token must be 32 bytes encoded as lowercase hex"
        )
    return raw_token


def model_pack_sha256(pack: ModelPack) -> str:
    payload = pack.model_dump_json(exclude_none=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_model_pack(path: Path) -> ModelPack:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        raise ValueError(
            f"model pack manifest is unreadable: {error}"
        ) from error
    pack = ModelPack.model_validate(document)
    root = path.resolve().parent
    for asset in pack.assets:
        candidate = (root / asset.path).resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(
                f"model asset escapes its pack: {asset.asset_id}"
            )
        if asset.kind == "file" and not candidate.is_file():
            raise ValueError(f"model asset is missing: {asset.asset_id}")
        if asset.kind == "directory" and not candidate.is_dir():
            raise ValueError(f"model asset is missing: {asset.asset_id}")
        if sha256_path(candidate) != asset.sha256:
            raise ValueError(
                f"model asset hash mismatch: {asset.asset_id}"
            )
    return pack


def apply_model_pack(pack: ModelPack, manifest_path: Path) -> None:
    root = manifest_path.resolve().parent
    assets = {asset.asset_id: root / asset.path for asset in pack.assets}
    os.environ["ATPIANO_BASIC_PITCH_MODEL"] = str(
        assets["basic-pitch-icassp-2022"]
    )
    transkun = assets["transkun-2.0"]
    os.environ["ATPIANO_TRANSKUN_CHECKPOINT"] = str(transkun)
    config = next(
        (
            root / asset.path
            for asset in pack.assets
            if asset.asset_id == "transkun-2.0-config"
        ),
        transkun.with_suffix(".conf"),
    )
    if not config.is_file():
        raise ValueError("model pack is missing the Transkun config")
    os.environ["ATPIANO_TRANSKUN_CONFIG"] = str(config)


def host_identity() -> tuple[str, str]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Phase 5 desktop sidecar requires macOS arm64")
    return "macos", "arm64"


def create_handshake(
    pack: ModelPack,
    *,
    score_available: bool = False,
) -> DesktopHandshake:
    platform_name, architecture = host_identity()
    return DesktopHandshake(
        sidecar_version=__version__,
        python_version=platform.python_version(),
        platform=platform_name,
        architecture=architecture,
        execution_backend="cpu",
        model_pack=pack,
        model_pack_sha256=model_pack_sha256(pack),
        score_available=score_available,
    )


def create_ready(handshake: DesktopHandshake, port: int) -> DesktopReady:
    return DesktopReady(
        sidecar_version=handshake.sidecar_version,
        port=port,
        platform=handshake.platform,
        architecture=handshake.architecture,
        execution_backend=handshake.execution_backend,
        model_pack_id=handshake.model_pack.model_pack_id,
        model_pack_sha256=handshake.model_pack_sha256,
    )
