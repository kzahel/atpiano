"""Internal committed-prefix score snapshots through MIDI2ScoreTransformer."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atpiano.corrected import CORRECTED_SESSION_SCHEMA
from atpiano.corrected_export import iter_latest_committed_index, write_midi
from atpiano.notation import summarize_musicxml
from atpiano.util import read_json, sha256_file, utc_now, write_json

SCORE_SNAPSHOT_SCHEMA = "atpiano.committed-score-snapshot.v1"
SCORE_RUNTIME_SCHEMA = "atpiano.midi2score-runtime.v1"
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

ScoreRunner = Callable[[Path, Path, Path], dict[str, Any]]


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
            "transformers": "4.44.2",
        },
    }
    write_json(paths["manifest"], manifest)
    return manifest


def run_score_adapter(
    runtime_directory: Path,
    input_midi: Path,
    output_musicxml: Path,
) -> dict[str, Any]:
    runtime = inspect_score_runtime(runtime_directory)
    if not runtime["available"]:
        raise RuntimeError(str(runtime["error"]))
    paths = _runtime_paths(runtime_directory)
    adapter_path = Path(__file__).with_name("midi2score_adapter.py").resolve()
    started = time.perf_counter()
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
            "--output-musicxml",
            str(output_musicxml.resolve()),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=SCORE_TIMEOUT_S,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("score adapter returned no result")
    adapter = json.loads(lines[-1])
    adapter["subprocess_elapsed_s"] = time.perf_counter() - started
    return adapter


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
        raise ValueError("no closed committed notes are available to score")
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
    musicxml_path = snapshot_directory / "score.musicxml"
    note_count, pedal_count = write_midi(
        midi_path,
        notes,
        sample_rate_hz=sample_rate_hz,
    )
    if pedal_count:
        raise RuntimeError("score snapshot unexpectedly included pedal events")
    execute = runner or (
        lambda input_path, output_path, runtime_path: run_score_adapter(
            runtime_path,
            input_path,
            output_path,
        )
    )
    adapter = execute(midi_path, musicxml_path, runtime_directory.resolve())
    summary = summarize_musicxml(musicxml_path.read_bytes())
    manifest = {
        "schema_version": SCORE_SNAPSHOT_SCHEMA,
        "session_id": session["session_id"],
        "generated_at": utc_now(),
        "commit_sample": commit_sample,
        "commit_s": commit_sample / sample_rate_hz,
        "sample_rate_hz": sample_rate_hz,
        "note_count": note_count,
        "selection": "latest committed notes with closed offsets at H_commit",
        "midi": {
            "path": str(midi_path.relative_to(session_directory)),
            "sha256": sha256_file(midi_path),
        },
        "musicxml": {
            "path": str(musicxml_path.relative_to(session_directory)),
            "sha256": sha256_file(musicxml_path),
            "bytes": musicxml_path.stat().st_size,
            "summary": summary,
        },
        "adapter": adapter,
    }
    write_json(snapshot_directory / "manifest.json", manifest)
    write_json(score_root / "current.json", manifest)
    return manifest
