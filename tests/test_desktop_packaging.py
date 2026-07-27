from __future__ import annotations

import json
from pathlib import Path

import pytest

from atpiano.desktop import load_model_pack
from atpiano.desktop_packaging import (
    _audit_anonymous_caches,
    _audit_distributions,
    _audit_symlinks,
    _stage_fixture,
    component_inventory,
    inventory,
    stage_model_pack,
)


def _fake_site_packages(root: Path) -> Path:
    basic_pitch = (
        root
        / "basic_pitch"
        / "saved_models"
        / "icassp_2022"
        / "nmp.mlpackage"
    )
    basic_pitch.mkdir(parents=True)
    (basic_pitch / "model.mlmodel").write_bytes(b"basic-pitch")
    transkun = root / "transkun" / "pretrained"
    transkun.mkdir(parents=True)
    (transkun / "2.0.pt").write_bytes(b"transkun")
    (transkun / "2.0.conf").write_text("{}\n", encoding="utf-8")
    return root


def test_model_pack_is_separated_and_verified(tmp_path: Path) -> None:
    site_packages = _fake_site_packages(tmp_path / "site-packages")
    runtime = tmp_path / "runtime"

    pack = stage_model_pack(site_packages, runtime)

    assert pack.model_pack_id == "atpiano-cpu-models-2026.07"
    assert not (site_packages / "transkun" / "pretrained").exists()
    assert not (site_packages / "basic_pitch" / "saved_models").exists()
    assert load_model_pack(
        runtime / "model-pack" / "model-pack.json"
    ) == pack
    summary = inventory(runtime)
    assert summary["file_count"] == 4
    assert summary["total_bytes"] > 0


def test_bundle_audit_rejects_external_symlink(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path / "outside")

    with pytest.raises(RuntimeError, match="symlink escapes"):
        _audit_symlinks(root)


def test_bundle_audit_rejects_accelerator_and_score_assets(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="accelerator package"):
        _audit_distributions(
            tmp_path,
            [{"name": "nvidia-cublas", "version": "1"}],
        )
    (tmp_path / "MIDI2ScoreTF.ckpt").write_bytes(b"score")
    with pytest.raises(RuntimeError, match="score runtime asset"):
        _audit_distributions(
            tmp_path,
            [{"name": "torch", "version": "2"}],
        )
    with pytest.raises(RuntimeError, match="development package"):
        _audit_distributions(
            tmp_path,
            [{"name": "pytest", "version": "8"}],
        )


def test_model_pack_manifest_has_no_absolute_paths(tmp_path: Path) -> None:
    site_packages = _fake_site_packages(tmp_path / "site-packages")
    runtime = tmp_path / "runtime"

    stage_model_pack(site_packages, runtime)
    document = json.loads(
        (runtime / "model-pack" / "model-pack.json").read_text(
            encoding="utf-8"
        )
    )

    assert all(
        not Path(asset["path"]).is_absolute()
        for asset in document["assets"]
    )


def test_desktop_stages_the_golden_musical_fixture(
    tmp_path: Path,
) -> None:
    _stage_fixture(tmp_path)

    manifest = json.loads(
        (tmp_path / "fixture" / "input.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["input_id"] == "deterministic-musical-loop-v1"
    assert manifest["audio"]["duration_s"] == 42.0
    assert manifest["audio"]["frame_count"] == 2_016_000


def test_component_inventory_reconciles_staged_runtime(
    tmp_path: Path,
) -> None:
    paths = (
        "bin/python3.10",
        "bin/ffmpeg",
        "fixture/input.json",
        "lib/media/libcodec.dylib",
        "lib/python3.10/site-packages/example/module.py",
        "model-pack/model-pack.json",
    )
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(relative.encode("utf-8"))

    summary = component_inventory(tmp_path)

    assert summary["installed_bytes"] == inventory(tmp_path)["total_bytes"]
    assert set(summary["categories"]) == {
        "golden_replay_fixture",
        "media_tools",
        "model_pack",
        "python_packages",
        "python_runtime_and_manifest",
    }


def test_bundle_audit_rejects_anonymous_cache(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()

    with pytest.raises(RuntimeError, match="anonymous cache"):
        _audit_anonymous_caches(tmp_path)
