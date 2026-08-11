from __future__ import annotations

from copy import deepcopy

import pytest

from atpiano.desktop_media import (
    BUILD_SCHEMA,
    load_build_contract,
    validate_build_contract,
)


def test_tracked_media_contract_is_minimal_shared_and_lgpl_only() -> None:
    contract = load_build_contract()

    assert contract["schema_version"] == BUILD_SCHEMA
    assert contract["target"] == "macos-arm64"
    assert contract["runtime_library_directory"] == "lib/media"
    assert {source["name"] for source in contract["sources"]} == {
        "ffmpeg",
        "lame",
    }
    assert all(
        source["license"].startswith("LGPL-") for source in contract["sources"]
    )
    flags = contract["ffmpeg_configure"]
    assert "--enable-shared" in flags
    assert "--disable-static" in flags
    assert "--disable-everything" in flags
    assert "--enable-libmp3lame" in flags
    assert "--enable-gpl" not in flags
    assert "--enable-nonfree" not in flags


@pytest.mark.parametrize("forbidden", ["--enable-gpl", "--enable-nonfree"])
def test_media_contract_rejects_forbidden_ffmpeg_modes(forbidden: str) -> None:
    contract = deepcopy(load_build_contract())
    contract["ffmpeg_configure"].append(forbidden)

    with pytest.raises(RuntimeError, match="exclude GPL and nonfree"):
        validate_build_contract(contract)


def test_media_contract_rejects_static_ffmpeg() -> None:
    contract = deepcopy(load_build_contract())
    contract["ffmpeg_configure"].remove("--disable-static")

    with pytest.raises(RuntimeError, match="flag is missing: --disable-static"):
        validate_build_contract(contract)
