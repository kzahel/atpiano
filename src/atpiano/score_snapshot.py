"""Internal committed-prefix score snapshots through MIDI2ScoreTransformer."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atpiano import __version__
from atpiano.application.errors import bounded_error_message
from atpiano.corrected import CORRECTED_SESSION_SCHEMA
from atpiano.corrected_export import iter_latest_committed_index, write_midi
from atpiano.notation import summarize_musicxml
from atpiano.score_alignment import (
    SCORE_ALIGNMENT_SCHEMA,
    SCORE_INPUT_NOTES_SCHEMA,
    score_input_notes_document,
    validate_score_alignment,
)
from atpiano.score_postprocess import (
    SCORE_POSTPROCESSOR_VERSION,
    normalized_options,
    score_variant_id,
)
from atpiano.util import (
    git_revision,
    git_worktree_dirty,
    read_json,
    sha256_file,
    utc_now,
    write_json,
)

SCORE_SNAPSHOT_SCHEMA = "atpiano.committed-score-snapshot.v1"
SCORE_VARIANT_SCHEMA = "atpiano.score-variant.v1"
SCORE_RUNTIME_SCHEMA = "atpiano.midi2score-runtime.v2"
SCORE_PRODUCER_SCHEMA = "atpiano.score-producer.v1"
SCORE_PIPELINE_REVISION = 4
MIDI2SCORE_REPOSITORY = "https://github.com/TimFelixBeyer/MIDI2ScoreTransformer.git"
MIDI2SCORE_COMMIT = "115432bda16ca16e0fec2e9465788f2ba369971f"
MIDI2SCORE_CHECKPOINT_URL = (
    "https://github.com/TimFelixBeyer/MIDI2ScoreTransformer/"
    "releases/download/v0.0.1/MIDI2ScoreTF.ckpt"
)
MIDI2SCORE_CHECKPOINT_SHA256 = "7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638"
MAX_SCORE_NOTES = 4096
MAX_SCORE_SOURCE_S = 15 * 60
SCORE_TIMEOUT_S = 180
SCORE_VARIANT_TIMEOUT_S = 30
MAX_SCORE_NOTE_EXPANSION_RATIO = 4
MAX_SCORE_NOTE_EXPANSION_ALLOWANCE = 16
SCORE_PIPELINE_SOURCE_FILES = (
    "corrected_export.py",
    "midi2score_adapter.py",
    "score_alignment.py",
    "score_postprocess.py",
    "score_snapshot.py",
    "score_variant_adapter.py",
)

ScoreRunner = Callable[[Path, Path, Path, Path, Path], dict[str, Any]]
ScoreVariantRunner = Callable[
    [Path, Path, Path, Path, str, int | None, Path],
    dict[str, Any],
]


def score_pipeline_fingerprint() -> str:
    """Hash the tracked source boundary that can change a score snapshot."""

    source_root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in SCORE_PIPELINE_SOURCE_FILES:
        path = source_root / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def score_producer_provenance(
    runtime_directory: Path,
    *,
    adapter_schema: str,
    injected_runner: bool,
) -> dict[str, Any]:
    """Describe the exact Atpiano and model boundary that made a score."""

    runtime_manifest: dict[str, Any] | None = None
    if not injected_runner:
        runtime = inspect_score_runtime(runtime_directory)
        if not runtime["available"]:
            raise RuntimeError(str(runtime["error"]))
        runtime_manifest = runtime["manifest"]
    repository_root = Path(__file__).resolve().parents[2]
    repository = (
        runtime_manifest.get("repository", {})
        if runtime_manifest is not None
        else {}
    )
    checkpoint = (
        runtime_manifest.get("checkpoint", {})
        if runtime_manifest is not None
        else {}
    )
    return {
        "schema_version": SCORE_PRODUCER_SCHEMA,
        "pipeline_revision": SCORE_PIPELINE_REVISION,
        "pipeline_fingerprint": score_pipeline_fingerprint(),
        "application_version": __version__,
        "application_revision": git_revision(cwd=repository_root),
        "application_dirty": git_worktree_dirty(cwd=repository_root),
        "execution": (
            "injected-runner" if injected_runner else "pinned-runtime"
        ),
        "adapter_schema": adapter_schema,
        "alignment_schema": SCORE_ALIGNMENT_SCHEMA,
        "postprocessor_version": SCORE_POSTPROCESSOR_VERSION,
        "model_repository_commit": repository.get("commit"),
        "model_checkpoint_sha256": checkpoint.get("sha256"),
    }


def score_snapshot_is_plausible(manifest: dict[str, Any]) -> bool:
    """Reject transformer output whose note expansion is clearly pathological."""

    try:
        input_notes = int(manifest["note_count"])
        output_notes = int(
            manifest["musicxml"]["summary"]["pitched_note_elements"]
        )
    except (KeyError, TypeError, ValueError):
        return False
    if input_notes <= 0 or output_notes <= 0:
        return False
    output_limit = max(
        input_notes * MAX_SCORE_NOTE_EXPANSION_RATIO,
        input_notes + MAX_SCORE_NOTE_EXPANSION_ALLOWANCE,
    )
    return output_notes <= output_limit


def _validate_score_output(note_count: int, summary: dict[str, Any]) -> None:
    candidate = {
        "note_count": note_count,
        "musicxml": {"summary": summary},
    }
    if score_snapshot_is_plausible(candidate):
        return
    output_notes = summary.get("pitched_note_elements")
    raise RuntimeError(
        "Generated score was rejected because it expanded "
        f"{note_count} input notes into {output_notes} notation notes. "
        "The recording and committed MIDI are unchanged."
    )


def _runtime_paths(runtime_directory: Path) -> dict[str, Path]:
    runtime = runtime_directory.resolve()
    python_name = "python.exe" if os.name == "nt" else "python"
    python_path = runtime / ".venv" / ("Scripts" if os.name == "nt" else "bin") / python_name
    return {
        "root": runtime,
        "repository": runtime / "MIDI2ScoreTransformer",
        "checkpoint": runtime / "MIDI2ScoreTF.ckpt",
        "python": python_path,
        "manifest": runtime / "runtime.json",
    }


def inspect_score_runtime(runtime_directory: Path) -> dict[str, Any]:
    paths = _runtime_paths(runtime_directory)
    missing = [
        name
        for name in ("repository", "checkpoint", "python", "manifest")
        if not paths[name].exists()
    ]
    if missing:
        return {
            "available": False,
            "directory": str(paths["root"]),
            "error": f"missing score runtime assets: {', '.join(missing)}",
        }
    try:
        manifest = read_json(paths["manifest"])
    except (OSError, ValueError) as error:
        return {
            "available": False,
            "directory": str(paths["root"]),
            "error": f"invalid score runtime manifest: {error}",
        }
    if (
        manifest.get("schema_version") != SCORE_RUNTIME_SCHEMA
        or manifest.get("repository", {}).get("commit") != MIDI2SCORE_COMMIT
        or manifest.get("checkpoint", {}).get("sha256") != MIDI2SCORE_CHECKPOINT_SHA256
    ):
        return {
            "available": False,
            "directory": str(paths["root"]),
            "error": "score runtime versions do not match the pinned contract",
        }
    return {
        "available": True,
        "directory": str(paths["root"]),
        "manifest": manifest,
    }


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _download_checkpoint(destination: Path) -> None:
    temporary = destination.with_suffix(".download")
    digest = hashlib.sha256()
    with urllib.request.urlopen(MIDI2SCORE_CHECKPOINT_URL, timeout=60) as response:
        with temporary.open("wb") as handle:
            while block := response.read(1024 * 1024):
                digest.update(block)
                handle.write(block)
    if digest.hexdigest() != MIDI2SCORE_CHECKPOINT_SHA256:
        temporary.unlink(missing_ok=True)
        raise ValueError("downloaded MIDI2ScoreTransformer checkpoint checksum differs")
    temporary.replace(destination)


def setup_score_runtime(runtime_directory: Path) -> dict[str, Any]:
    """Create the ignored, isolated Python 3.11 score runtime once."""

    paths = _runtime_paths(runtime_directory)
    existing = inspect_score_runtime(paths["root"])
    if existing["available"]:
        return existing["manifest"]
    paths["root"].mkdir(parents=True, exist_ok=True)
    if not paths["repository"].exists():
        _run(
            [
                "git",
                "clone",
                "--no-checkout",
                MIDI2SCORE_REPOSITORY,
                str(paths["repository"]),
            ]
        )
        _run(
            ["git", "checkout", "--detach", MIDI2SCORE_COMMIT],
            cwd=paths["repository"],
        )
    repository_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=paths["repository"],
        text=True,
    ).strip()
    if repository_commit != MIDI2SCORE_COMMIT:
        raise ValueError("MIDI2ScoreTransformer checkout differs from the pinned commit")
    if not paths["checkpoint"].exists():
        _download_checkpoint(paths["checkpoint"])
    if sha256_file(paths["checkpoint"]) != MIDI2SCORE_CHECKPOINT_SHA256:
        raise ValueError("MIDI2ScoreTransformer checkpoint checksum differs")
    if not paths["python"].exists():
        _run(["uv", "venv", "--python", "3.11", str(paths["root"] / ".venv")])
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(paths["python"]),
            "-r",
            str(paths["repository"] / "requirements.txt"),
            "numpy<2",
            "setuptools<81",
            "transformers==4.44.2",
            "beautifulsoup4==4.13.4",
        ]
    )
    python_version = subprocess.check_output(
        [str(paths["python"]), "--version"],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    manifest = {
        "schema_version": SCORE_RUNTIME_SCHEMA,
        "created_at": utc_now(),
        "internal_use_only": True,
        "python": python_version,
        "repository": {
            "url": MIDI2SCORE_REPOSITORY,
            "commit": repository_commit,
        },
        "checkpoint": {
            "url": MIDI2SCORE_CHECKPOINT_URL,
            "sha256": sha256_file(paths["checkpoint"]),
            "bytes": paths["checkpoint"].stat().st_size,
        },
        "execution": {
            "device": "cpu",
            "beautifulsoup4": "4.13.4",
            "transformers": "4.44.2",
        },
    }
    write_json(paths["manifest"], manifest)
    return manifest


def run_score_adapter(
    runtime_directory: Path,
    input_midi: Path,
    input_notes: Path,
    output_musicxml: Path,
    output_alignment: Path,
    *,
    output_baseline_musicxml: Path,
    output_baseline_alignment: Path,
) -> dict[str, Any]:
    runtime = inspect_score_runtime(runtime_directory)
    if not runtime["available"]:
        raise RuntimeError(str(runtime["error"]))
    paths = _runtime_paths(runtime_directory)
    adapter_path = Path(__file__).with_name("midi2score_adapter.py").resolve()
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [
                str(paths["python"]),
                str(adapter_path),
                "--repository",
                str(paths["repository"]),
                "--checkpoint",
                str(paths["checkpoint"]),
                "--input-midi",
                str(input_midi.resolve()),
                "--input-notes",
                str(input_notes.resolve()),
                "--output-baseline-musicxml",
                str(output_baseline_musicxml.resolve()),
                "--output-baseline-alignment",
                str(output_baseline_alignment.resolve()),
                "--output-musicxml",
                str(output_musicxml.resolve()),
                "--output-alignment",
                str(output_alignment.resolve()),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=SCORE_TIMEOUT_S,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        final_line = next(
            (
                line.strip()
                for line in reversed(detail.splitlines())
                if line.strip()
            ),
            str(error),
        )
        raise RuntimeError(
            bounded_error_message(
                f"score adapter failed: {final_line}",
            )
        ) from error
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("score adapter returned no result")
    adapter = json.loads(lines[-1])
    adapter["subprocess_elapsed_s"] = time.perf_counter() - started
    return adapter


def run_score_variant_adapter(
    runtime_directory: Path,
    input_musicxml: Path,
    input_alignment: Path,
    output_musicxml: Path,
    output_alignment: Path,
    *,
    clef_policy: str,
    target_key_fifths: int | None,
) -> dict[str, Any]:
    """Run music21-only variant generation without loading the transformer."""

    runtime = inspect_score_runtime(runtime_directory)
    if not runtime["available"]:
        raise RuntimeError(str(runtime["error"]))
    paths = _runtime_paths(runtime_directory)
    adapter_path = Path(__file__).with_name("score_variant_adapter.py").resolve()
    command = [
        str(paths["python"]),
        str(adapter_path),
        "--input-musicxml",
        str(input_musicxml.resolve()),
        "--input-alignment",
        str(input_alignment.resolve()),
        "--output-musicxml",
        str(output_musicxml.resolve()),
        "--output-alignment",
        str(output_alignment.resolve()),
        "--clef-policy",
        clef_policy,
    ]
    if target_key_fifths is not None:
        command.extend(["--target-key-fifths", str(target_key_fifths)])
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=SCORE_VARIANT_TIMEOUT_S,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        raise RuntimeError(
            f"score variant adapter failed: {detail[-4000:]}"
        ) from error
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("score variant adapter returned no result")
    adapter = json.loads(lines[-1])
    adapter["subprocess_elapsed_s"] = time.perf_counter() - started
    return adapter


def _artifact_record(
    path: Path,
    *,
    session_directory: Path,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": path.relative_to(session_directory).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if summary is not None:
        value["summary"] = summary
    return value


def _variant_label(
    role: str,
    postprocess: dict[str, Any] | None,
) -> str:
    key_state = (postprocess or {}).get("key_signature", {})
    key_label = key_state.get("target_label") or key_state.get("source_label")
    prefix = {
        "baseline": "Model baseline",
        "automatic": "Automatic clefs",
        "enharmonic": "Enharmonic key",
    }[role]
    return f"{prefix} · {key_label}" if key_label else prefix


def _variant_record(
    *,
    variant_id: str,
    role: str,
    options: dict[str, Any],
    baseline_musicxml_sha256: str,
    baseline_alignment_sha256: str,
    musicxml: dict[str, Any],
    alignment: dict[str, Any],
    postprocess: dict[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCORE_VARIANT_SCHEMA,
        "variant_id": variant_id,
        "role": role,
        "label": _variant_label(role, postprocess),
        "created_at": created_at,
        "postprocessor_version": SCORE_POSTPROCESSOR_VERSION,
        "options": options,
        "baseline_musicxml_sha256": baseline_musicxml_sha256,
        "baseline_alignment_sha256": baseline_alignment_sha256,
        "musicxml": musicxml,
        "alignment": alignment,
        "postprocess": postprocess,
        "needs_review": bool(
            (postprocess or {}).get("needs_review", False)
        ),
    }


def _select_variant(
    pointer: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    selected = dict(pointer)
    selected["selected_variant_id"] = variant["variant_id"]
    selected["musicxml"] = variant["musicxml"]
    selected["alignment"] = variant["alignment"]
    return selected


def _selected_notes(
    database_path: Path,
    *,
    commit_sample: int,
) -> list[dict[str, Any]]:
    selected = []
    for event in iter_latest_committed_index(database_path):
        onset = event.get("onset_sample")
        offset = event.get("offset_sample")
        if (
            isinstance(event.get("pitch"), int)
            and isinstance(onset, int)
            and isinstance(offset, int)
            and 0 <= onset <= offset <= commit_sample
        ):
            selected.append(event)
    if not selected:
        raise ValueError(
            "No completed piano notes were detected, so there is nothing to score."
        )
    if len(selected) > MAX_SCORE_NOTES:
        raise ValueError(f"committed score snapshot exceeds {MAX_SCORE_NOTES} notes")
    return selected


def generate_score_snapshot(
    session_directory: Path,
    runtime_directory: Path,
    *,
    commit_sample: int,
    runner: ScoreRunner | None = None,
) -> dict[str, Any]:
    """Generate and atomically publish one committed-prefix score snapshot."""

    session_directory = session_directory.resolve()
    session = read_json(session_directory / "session.json")
    if session.get("schema_version") != CORRECTED_SESSION_SCHEMA:
        raise ValueError("score snapshot requires a corrected session")
    sample_rate_hz = int(session["sample_rate_hz"])
    if not 0 < commit_sample <= MAX_SCORE_SOURCE_S * sample_rate_hz:
        raise ValueError(f"score snapshot must be within {MAX_SCORE_SOURCE_S} source seconds")
    notes = _selected_notes(
        session_directory / "event-index.sqlite3",
        commit_sample=commit_sample,
    )
    score_root = session_directory / "score"
    snapshot_directory = score_root / "snapshots" / f"{commit_sample:016d}"
    snapshot_directory.mkdir(parents=True, exist_ok=True)
    midi_path = snapshot_directory / "committed.mid"
    source_notes_path = snapshot_directory / "source-notes.json"
    baseline_directory = snapshot_directory / "baseline"
    baseline_directory.mkdir(exist_ok=True)
    baseline_musicxml_path = baseline_directory / "score.musicxml"
    baseline_alignment_path = baseline_directory / "alignment.json"
    staging_musicxml_path = snapshot_directory / ".automatic.musicxml"
    staging_alignment_path = snapshot_directory / ".automatic-alignment.json"
    write_json(
        source_notes_path,
        score_input_notes_document(
            session_id=str(session["session_id"]),
            sample_rate_hz=sample_rate_hz,
            notes=notes,
        ),
    )
    note_count, pedal_count = write_midi(
        midi_path,
        notes,
        sample_rate_hz=sample_rate_hz,
    )
    if pedal_count:
        raise RuntimeError("score snapshot unexpectedly included pedal events")
    if runner is None:
        adapter = run_score_adapter(
            runtime_directory.resolve(),
            midi_path,
            source_notes_path,
            staging_musicxml_path,
            staging_alignment_path,
            output_baseline_musicxml=baseline_musicxml_path,
            output_baseline_alignment=baseline_alignment_path,
        )
    else:
        adapter = runner(
            midi_path,
            source_notes_path,
            staging_musicxml_path,
            staging_alignment_path,
            runtime_directory.resolve(),
        )
        shutil.copy2(staging_musicxml_path, baseline_musicxml_path)
        shutil.copy2(staging_alignment_path, baseline_alignment_path)

    baseline_summary = summarize_musicxml(baseline_musicxml_path.read_bytes())
    _validate_score_output(note_count, baseline_summary)
    baseline_alignment_summary = validate_score_alignment(
        read_json(baseline_alignment_path),
        source_notes_path=source_notes_path,
        musicxml_path=baseline_musicxml_path,
    )
    if baseline_alignment_summary["source_notes"] != note_count:
        raise RuntimeError("baseline score alignment source count differs")

    summary = summarize_musicxml(staging_musicxml_path.read_bytes())
    _validate_score_output(note_count, summary)
    alignment_summary = validate_score_alignment(
        read_json(staging_alignment_path),
        source_notes_path=source_notes_path,
        musicxml_path=staging_musicxml_path,
    )
    if alignment_summary["source_notes"] != note_count:
        raise RuntimeError("score alignment source count differs from snapshot")
    created_at = utc_now()
    baseline_musicxml = _artifact_record(
        baseline_musicxml_path,
        session_directory=session_directory,
        summary=baseline_summary,
    )
    baseline_alignment = _artifact_record(
        baseline_alignment_path,
        session_directory=session_directory,
        summary=baseline_alignment_summary,
    ) | {"schema_version": SCORE_ALIGNMENT_SCHEMA}
    baseline_options = normalized_options(clef_policy="preserve")
    baseline_variant_id = score_variant_id(
        baseline_musicxml_sha256=baseline_musicxml["sha256"],
        baseline_alignment_sha256=baseline_alignment["sha256"],
        options=baseline_options,
    )
    postprocess = adapter.get("postprocess")
    if not isinstance(postprocess, dict):
        postprocess = None
    baseline = _variant_record(
        variant_id=baseline_variant_id,
        role="baseline",
        options=baseline_options,
        baseline_musicxml_sha256=baseline_musicxml["sha256"],
        baseline_alignment_sha256=baseline_alignment["sha256"],
        musicxml=baseline_musicxml,
        alignment=baseline_alignment,
        postprocess=(
            {
                "schema_version": "atpiano.score-postprocessor.v1",
                "version": SCORE_POSTPROCESSOR_VERSION,
                "key_signature": postprocess.get("key_signature", {}),
                "needs_review": False,
            }
            if postprocess is not None
            else None
        ),
        created_at=created_at,
    )
    automatic_options = normalized_options(clef_policy="automatic")
    automatic_variant_id = score_variant_id(
        baseline_musicxml_sha256=baseline_musicxml["sha256"],
        baseline_alignment_sha256=baseline_alignment["sha256"],
        options=automatic_options,
    )
    variant_directory = (
        snapshot_directory
        / "variants"
        / automatic_variant_id.replace(":", "-")
    )
    variant_directory.mkdir(parents=True, exist_ok=True)
    musicxml_path = variant_directory / "score.musicxml"
    alignment_path = variant_directory / "alignment.json"
    staging_musicxml_path.replace(musicxml_path)
    staging_alignment_path.replace(alignment_path)
    musicxml = _artifact_record(
        musicxml_path,
        session_directory=session_directory,
        summary=summary,
    )
    alignment = _artifact_record(
        alignment_path,
        session_directory=session_directory,
        summary=alignment_summary,
    ) | {"schema_version": SCORE_ALIGNMENT_SCHEMA}
    automatic = _variant_record(
        variant_id=automatic_variant_id,
        role="automatic",
        options=automatic_options,
        baseline_musicxml_sha256=baseline_musicxml["sha256"],
        baseline_alignment_sha256=baseline_alignment["sha256"],
        musicxml=musicxml,
        alignment=alignment,
        postprocess=postprocess,
        created_at=created_at,
    )
    producer = score_producer_provenance(
        runtime_directory,
        adapter_schema=str(adapter.get("schema_version", "unknown")),
        injected_runner=runner is not None,
    )
    write_json(variant_directory / "manifest.json", automatic)
    manifest = {
        "schema_version": SCORE_SNAPSHOT_SCHEMA,
        "producer": producer,
        "session_id": session["session_id"],
        "generated_at": created_at,
        "commit_sample": commit_sample,
        "commit_s": commit_sample / sample_rate_hz,
        "sample_rate_hz": sample_rate_hz,
        "note_count": note_count,
        "selection": "latest committed notes with closed offsets at H_commit",
        "midi": {
            "path": midi_path.relative_to(session_directory).as_posix(),
            "sha256": sha256_file(midi_path),
        },
        "source_notes": {
            "schema_version": SCORE_INPUT_NOTES_SCHEMA,
            "path": source_notes_path.relative_to(
                session_directory
            ).as_posix(),
            "sha256": sha256_file(source_notes_path),
        },
        "baseline": baseline,
        "variants": [automatic],
        "default_variant_id": automatic_variant_id,
        "selected_variant_id": automatic_variant_id,
        "musicxml": musicxml,
        "alignment": alignment,
        "adapter": adapter,
    }
    write_json(snapshot_directory / "manifest.json", manifest)
    write_json(score_root / "current.json", manifest)
    return manifest


def generate_score_variant(
    session_directory: Path,
    runtime_directory: Path,
    *,
    baseline_musicxml_path: Path,
    baseline_alignment_path: Path,
    clef_policy: str = "automatic",
    target_key_fifths: int | None = None,
    runner: ScoreVariantRunner | None = None,
) -> dict[str, Any]:
    """Create or select one deterministic variant of the current baseline."""

    session_directory = session_directory.resolve()
    pointer_path = session_directory / "score" / "current.json"
    pointer = read_json(pointer_path)
    if (
        pointer.get("schema_version") != SCORE_SNAPSHOT_SCHEMA
        or pointer.get("session_id")
        != read_json(session_directory / "session.json").get("session_id")
    ):
        raise ValueError("current score snapshot is invalid")
    baseline = pointer.get("baseline")
    if not isinstance(baseline, dict):
        legacy_musicxml = (
            session_directory / Path(str(pointer["musicxml"]["path"]))
        ).resolve()
        legacy_alignment = (
            session_directory / Path(str(pointer["alignment"]["path"]))
        ).resolve()
        if (
            baseline_musicxml_path.resolve() != legacy_musicxml
            or baseline_alignment_path.resolve() != legacy_alignment
            or not legacy_musicxml.is_file()
            or not legacy_alignment.is_file()
            or sha256_file(legacy_musicxml)
            != str(pointer["musicxml"]["sha256"])
            or sha256_file(legacy_alignment)
            != str(pointer["alignment"]["sha256"])
        ):
            raise ValueError(
                "variant request does not name the legacy score baseline"
            )
        baseline_options = normalized_options(clef_policy="preserve")
        baseline_variant_id = score_variant_id(
            baseline_musicxml_sha256=str(pointer["musicxml"]["sha256"]),
            baseline_alignment_sha256=str(pointer["alignment"]["sha256"]),
            options=baseline_options,
        )
        baseline = _variant_record(
            variant_id=baseline_variant_id,
            role="baseline",
            options=baseline_options,
            baseline_musicxml_sha256=str(pointer["musicxml"]["sha256"]),
            baseline_alignment_sha256=str(pointer["alignment"]["sha256"]),
            musicxml=pointer["musicxml"],
            alignment=pointer["alignment"],
            postprocess=None,
            created_at=str(pointer["generated_at"]),
        )
        pointer["baseline"] = baseline
        pointer["variants"] = []
        pointer["default_variant_id"] = baseline_variant_id
        pointer["selected_variant_id"] = baseline_variant_id
    baseline_musicxml_path = baseline_musicxml_path.resolve()
    baseline_alignment_path = baseline_alignment_path.resolve()
    expected_musicxml = (
        session_directory / Path(str(baseline["musicxml"]["path"]))
    ).resolve()
    expected_alignment = (
        session_directory / Path(str(baseline["alignment"]["path"]))
    ).resolve()
    if (
        baseline_musicxml_path != expected_musicxml
        or baseline_alignment_path != expected_alignment
        or not expected_musicxml.is_file()
        or not expected_alignment.is_file()
        or sha256_file(expected_musicxml)
        != str(baseline["musicxml"]["sha256"])
        or sha256_file(expected_alignment)
        != str(baseline["alignment"]["sha256"])
    ):
        raise ValueError("variant request does not name the current baseline")

    options = normalized_options(
        clef_policy=clef_policy,
        target_key_fifths=target_key_fifths,
    )
    variant_id = score_variant_id(
        baseline_musicxml_sha256=str(baseline["musicxml"]["sha256"]),
        baseline_alignment_sha256=str(baseline["alignment"]["sha256"]),
        options=options,
    )
    if variant_id == baseline["variant_id"]:
        selected = _select_variant(pointer, baseline)
        write_json(pointer_path, selected)
        return baseline
    variants = pointer.get("variants")
    if not isinstance(variants, list):
        raise ValueError("score variant catalog is invalid")
    for existing in variants:
        if isinstance(existing, dict) and existing.get("variant_id") == variant_id:
            selected = _select_variant(pointer, existing)
            write_json(pointer_path, selected)
            return existing

    snapshot_directory = (
        session_directory
        / "score"
        / "snapshots"
        / f"{int(pointer['commit_sample']):016d}"
    ).resolve()
    variant_directory = (
        snapshot_directory / "variants" / variant_id.replace(":", "-")
    )
    if variant_directory.exists():
        raise RuntimeError("unpublished score variant directory already exists")
    variant_directory.mkdir(parents=True)
    musicxml_path = variant_directory / "score.musicxml"
    alignment_path = variant_directory / "alignment.json"
    if runner is None:
        adapter = run_score_variant_adapter(
            runtime_directory.resolve(),
            expected_musicxml,
            expected_alignment,
            musicxml_path,
            alignment_path,
            clef_policy=clef_policy,
            target_key_fifths=target_key_fifths,
        )
    else:
        adapter = runner(
            expected_musicxml,
            expected_alignment,
            musicxml_path,
            alignment_path,
            clef_policy,
            target_key_fifths,
            runtime_directory.resolve(),
        )
    source_notes_path = (
        session_directory / Path(str(pointer["source_notes"]["path"]))
    ).resolve()
    summary = summarize_musicxml(musicxml_path.read_bytes())
    _validate_score_output(int(pointer["note_count"]), summary)
    alignment_summary = validate_score_alignment(
        read_json(alignment_path),
        source_notes_path=source_notes_path,
        musicxml_path=musicxml_path,
    )
    if alignment_summary["source_notes"] != int(pointer["note_count"]):
        raise RuntimeError("variant alignment source count differs")
    postprocess = adapter.get("postprocess")
    if not isinstance(postprocess, dict):
        raise RuntimeError("score variant adapter omitted its evidence")
    role = "enharmonic" if target_key_fifths is not None else "automatic"
    variant = _variant_record(
        variant_id=variant_id,
        role=role,
        options=options,
        baseline_musicxml_sha256=str(baseline["musicxml"]["sha256"]),
        baseline_alignment_sha256=str(baseline["alignment"]["sha256"]),
        musicxml=_artifact_record(
            musicxml_path,
            session_directory=session_directory,
            summary=summary,
        ),
        alignment=_artifact_record(
            alignment_path,
            session_directory=session_directory,
            summary=alignment_summary,
        )
        | {"schema_version": SCORE_ALIGNMENT_SCHEMA},
        postprocess=postprocess,
        created_at=utc_now(),
    )
    write_json(variant_directory / "manifest.json", variant)
    variants.append(variant)
    root_manifest_path = snapshot_directory / "manifest.json"
    root_manifest = read_json(root_manifest_path)
    root_manifest["baseline"] = baseline
    root_manifest["variants"] = variants
    root_manifest["default_variant_id"] = pointer["default_variant_id"]
    write_json(root_manifest_path, root_manifest)
    pointer["variants"] = variants
    write_json(pointer_path, _select_variant(pointer, variant))
    return variant
