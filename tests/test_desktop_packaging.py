from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from atpiano.desktop import load_model_pack
from atpiano.desktop_packaging import (
    _audit_anonymous_caches,
    _audit_distributions,
    _audit_media_runtime,
    _audit_symlinks,
    _internal_score_policy,
    _materialize_runtime_symlinks,
    _prune_distribution_test_material,
    _sha256_tree_without,
    _stage_fixture,
    archive_component_inventory,
    component_inventory,
    inventory,
    stage_model_pack,
)


def _fake_site_packages(root: Path) -> Path:
    basic_pitch = (
        root / "basic_pitch" / "saved_models" / "icassp_2022" / "nmp.mlpackage"
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
    assert load_model_pack(runtime / "model-pack" / "model-pack.json") == pack
    summary = inventory(runtime)
    assert summary["file_count"] == 4
    assert summary["total_bytes"] > 0


def test_bundle_audit_rejects_external_symlink(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    try:
        (root / "escape").symlink_to(tmp_path / "outside")
    except OSError as error:
        if os.name != "nt" or error.winerror != 1314:
            raise
        pytest.skip("this Windows account cannot create symbolic links")

    with pytest.raises(RuntimeError, match="symlink escapes"):
        _audit_symlinks(root)


def test_score_support_materializes_only_internal_file_links(
    tmp_path: Path,
) -> None:
    root = tmp_path / "support"
    target = root / "bin" / "python3.11"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"interpreter")
    link = target.with_name("python")
    try:
        link.symlink_to(target.name)
    except OSError as error:
        if os.name != "nt" or error.winerror != 1314:
            raise
        pytest.skip("this Windows account cannot create symbolic links")

    before = _sha256_tree_without(root, set())
    _materialize_runtime_symlinks(root)

    assert not link.is_symlink()
    assert link.read_bytes() == b"interpreter"
    assert _sha256_tree_without(root, set()) == before


def test_score_support_hash_uses_canonical_path_order(tmp_path: Path) -> None:
    first = tmp_path / "package-1.dist-info" / "METADATA"
    second = tmp_path / "package" / "module.py"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"metadata")
    second.write_bytes(b"module")
    expected = hashlib.sha256()
    for relative, contents in (
        ("package-1.dist-info/METADATA", b"metadata"),
        ("package/module.py", b"module"),
    ):
        expected.update(relative.encode("utf-8"))
        expected.update(b"\0")
        expected.update(hashlib.sha256(contents).digest())

    assert _sha256_tree_without(tmp_path, set()) == expected.hexdigest()


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


def test_internal_score_assets_require_explicit_policy(
    tmp_path: Path,
) -> None:
    score_root = tmp_path / "score-runtime"
    score_root.mkdir()
    (score_root / "MIDI2ScoreTF.ckpt").write_bytes(b"score")

    _audit_distributions(
        tmp_path,
        [{"name": "torch", "version": "2"}],
        allow_internal_score_runtime=True,
    )
    outside = tmp_path / "MIDI2ScoreTF.ckpt"
    outside.write_bytes(b"score")
    with pytest.raises(RuntimeError, match="score runtime asset"):
        _audit_distributions(
            tmp_path,
            [{"name": "torch", "version": "2"}],
            allow_internal_score_runtime=True,
        )


def test_internal_score_policy_blocks_distribution() -> None:
    policy = _internal_score_policy(
        {
            "internal_score_runtime": {
                "enabled": True,
                "internal_only": True,
                "public_distribution": False,
            }
        }
    )

    assert policy["enabled"] is True
    with pytest.raises(RuntimeError, match="policy is unsafe"):
        _internal_score_policy(
            {
                "internal_score_runtime": {
                    "enabled": True,
                    "internal_only": True,
                    "public_distribution": True,
                }
            }
        )


def test_model_pack_manifest_has_no_absolute_paths(tmp_path: Path) -> None:
    site_packages = _fake_site_packages(tmp_path / "site-packages")
    runtime = tmp_path / "runtime"

    stage_model_pack(site_packages, runtime)
    document = json.loads(
        (runtime / "model-pack" / "model-pack.json").read_text(encoding="utf-8")
    )

    assert all(not Path(asset["path"]).is_absolute() for asset in document["assets"])


def test_desktop_stages_the_golden_musical_fixture(
    tmp_path: Path,
) -> None:
    _stage_fixture(tmp_path)

    manifest = json.loads(
        (tmp_path / "fixture" / "input.json").read_text(encoding="utf-8")
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
        "score-runtime/runtime.json",
        "score-support/support-manifest.json",
    )
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(relative.encode("utf-8"))

    summary = component_inventory(tmp_path)

    assert summary["installed_bytes"] == inventory(tmp_path)["total_bytes"]
    assert set(summary["categories"]) == {
        "golden_replay_fixture",
        "internal_score_runtime",
        "media_tools",
        "model_pack",
        "python_packages",
        "python_runtime_and_manifest",
        "score_support",
    }


def test_bundle_audit_rejects_anonymous_cache(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()

    with pytest.raises(RuntimeError, match="anonymous cache"):
        _audit_anonymous_caches(tmp_path)


def test_media_audit_accepts_exact_lgpl_build_identity(tmp_path: Path) -> None:
    media = {
        "build_identity": "a" * 64,
        "ffmpeg_version": "ffmpeg version 8.1.2",
        "configuration": "--enable-shared --disable-static --enable-libmp3lame",
        "license": "LGPL-only",
        "sources": [
            {"name": "ffmpeg", "license": "LGPL-2.1-or-later"},
            {"name": "lame", "license": "LGPL-2.0-or-later"},
        ],
        "bundled_library_count": 6,
        "notices": "share/licenses/media/THIRD_PARTY_NOTICES.md",
        "build_manifest": "media-build-manifest.json",
    }
    for relative in (
        "bin/ffmpeg",
        "bin/ffprobe",
        media["notices"],
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    library_root = tmp_path / "lib" / "media"
    library_root.mkdir(parents=True)
    for index in range(6):
        (library_root / f"library-{index}.dylib").write_bytes(b"fixture")
    (tmp_path / "media-build-manifest.json").write_text(
        json.dumps(
            {
                **media,
                "file_hash_scope": (
                    "relocated ad-hoc media output before product distribution signing"
                ),
            }
        ),
        encoding="utf-8",
    )

    result = _audit_media_runtime(tmp_path, {"media": media})

    assert result["license"] == "LGPL-only"
    assert result["bundled_library_count"] == 6


def test_media_audit_rejects_gpl_configuration(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="GPL/nonfree"):
        _audit_media_runtime(
            tmp_path,
            {
                "media": {
                    "license": "LGPL-only",
                    "configuration": "--enable-gpl",
                }
            },
        )


def test_distribution_test_namespaces_are_pruned(
    tmp_path: Path,
) -> None:
    keep = tmp_path / "example" / "module.py"
    remove = tmp_path / "example" / "tests" / "test_module.py"
    required = tmp_path / "torch" / "testing" / "_comparison.py"
    required_internal = tmp_path / "torch" / "testing" / "_internal" / "test_case.py"
    keep.parent.mkdir(parents=True)
    remove.parent.mkdir(parents=True)
    required.parent.mkdir(parents=True)
    required_internal.parent.mkdir(parents=True)
    keep.write_text("value = 1\n", encoding="utf-8")
    remove.write_text("def test_value(): pass\n", encoding="utf-8")
    required.write_text("value = 1\n", encoding="utf-8")
    required_internal.write_text(
        "def test_value(): pass\n",
        encoding="utf-8",
    )

    _prune_distribution_test_material(tmp_path)

    assert keep.is_file()
    assert not remove.parent.exists()
    assert required.is_file()
    assert required_internal.is_file()


def test_score_runtime_retains_music21_import_namespace(
    tmp_path: Path,
) -> None:
    from atpiano.desktop_packaging import (
        REQUIRED_SCORE_TEST_NAMESPACES,
    )

    music21_test = tmp_path / "music21" / "test" / "testRunner.py"
    unrelated = tmp_path / "example" / "test" / "helper.py"
    music21_test.parent.mkdir(parents=True)
    unrelated.parent.mkdir(parents=True)
    music21_test.write_text("value = 1\n", encoding="utf-8")
    unrelated.write_text("value = 1\n", encoding="utf-8")

    _prune_distribution_test_material(
        tmp_path,
        required_namespaces=REQUIRED_SCORE_TEST_NAMESPACES,
    )

    assert music21_test.is_file()
    assert not unrelated.parent.exists()


def test_archive_component_inventory_accounts_for_container(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "Atpiano.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr(
            "Atpiano.app/Contents/MacOS/atpiano-desktop",
            b"shell",
        )
        zipped.writestr(
            "Atpiano.app/Contents/Resources/desktop-runtime/model-pack/model-pack.json",
            b"model",
        )
        zipped.writestr(
            "__MACOSX/Atpiano.app/Contents/._Info.plist",
            b"metadata",
        )

    summary = archive_component_inventory(archive)

    assert summary["archive_bytes"] == archive.stat().st_size
    assert summary["container_overhead_bytes"] > 0
    assert summary["categories"]["rust_shell_and_embedded_frontend"][
        "uncompressed_bytes"
    ] == len(b"shell")
    assert summary["categories"]["model_pack"]["uncompressed_bytes"] == len(b"model")
    assert summary["categories"]["archive_metadata"]["uncompressed_bytes"] == len(
        b"metadata"
    )
