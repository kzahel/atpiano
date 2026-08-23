"""R5 replay and parity validation for the packaged desktop runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import secrets
import subprocess
import tempfile
import threading
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.desktop import (
    apply_model_pack,
    desktop_runtime_environment,
    load_model_pack,
)
from atpiano.midi import MidiNote, load_notes
from atpiano.notation import summarize_musicxml
from atpiano.quality import score_notes
from atpiano.score_alignment import validate_score_alignment
from atpiano.score_snapshot import score_snapshot_is_plausible
from atpiano.util import read_json, sha256_file, write_json

MODEL_PACK_ID = "atpiano-cpu-models-2026.07"
TERMINAL_STATES = {"complete", "failed"}
MAX_EVENT_RELATIVE_DELTA = 0.10
MIN_PAIRWISE_ONSET_F1 = 0.90
MIN_PAIRWISE_NOTE_OFFSET_F1 = 0.85
MIN_PAIRWISE_FRAME_F1 = 0.90
MAX_PAIRWISE_VELOCITY_MAE = 5.0
MAX_GOLDEN_ONSET_F1_DELTA = 0.02
MAX_GOLDEN_NOTE_OFFSET_F1_DELTA = 0.05
MAX_GOLDEN_FRAME_F1_DELTA = 0.02
MAX_GOLDEN_VELOCITY_MAE_DELTA = 2.0
MAX_GOLDEN_NOTE_COUNT_RELATIVE_DELTA = 0.05
REPLAY_START_TIMEOUT_S = 30
WINDOWS_REPLAY_START_TIMEOUT_S = 5 * 60
VOLATILE_EVENT_FIELDS = {
    "emitted_at_monotonic_ns",
    "emitted_elapsed_s",
    "event_id",
    "sequence",
    "session_id",
    "source_to_emission_latency_s",
}


def packaged_runtime_paths(app_path: Path) -> tuple[Path, Path, str]:
    """Resolve the packaged runtime boundary for either published desktop."""
    app = app_path.resolve()
    macos_runtime = app / "Contents" / "Resources" / "desktop-runtime"
    if macos_runtime.is_dir():
        runtime = macos_runtime
        python = runtime / "bin" / "python3"
        origin = "tauri://localhost"
    elif app.suffix.lower() == ".exe":
        runtime = app.parent / "desktop-runtime"
        python = runtime / "python.exe"
        origin = "http://tauri.localhost"
    else:
        raise ValueError("packaged replay requires a macOS app or Windows executable")
    if not python.is_file():
        raise ValueError("packaged desktop Python runtime is missing")
    return runtime, python, origin


def _read_ready_line(process: subprocess.Popen[str], timeout: float) -> str:
    if process.stdout is None:
        raise RuntimeError("packaged sidecar stdout is unavailable")
    lines: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

    def read() -> None:
        try:
            lines.put(process.stdout.readline())
        except BaseException as error:  # pragma: no cover - subprocess boundary
            lines.put(error)

    threading.Thread(target=read, daemon=True).start()
    try:
        result = lines.get(timeout=timeout)
    except queue.Empty as error:
        raise RuntimeError("packaged sidecar ready timeout") from error
    if isinstance(result, BaseException):
        raise RuntimeError("packaged sidecar ready read failed") from result
    if not result:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError(f"packaged sidecar exited before ready: {stderr[-1000:]}")
    return result


def normalized_event_digest(session_directory: Path) -> tuple[int, str]:
    events = []
    export = session_directory / "exports" / "session.jsonl"
    for line in export.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        events.append(
            {key: value for key, value in event.items() if key not in VOLATILE_EVENT_FIELDS}
        )
    encoded_events = sorted(
        json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        for event in events
    )
    encoded = "\n".join(encoded_events).encode("utf-8")
    return len(events), hashlib.sha256(encoded).hexdigest()


def _summarize(
    state: dict[str, Any],
    session_directory: Path,
    *,
    path: str,
    reference_midi: Path,
    total_s: float,
    sidecar_ready_s: float | None,
) -> dict[str, Any]:
    session = state["session"]
    horizons = state["horizons"]
    lanes = {lane["name"]: lane for lane in session["lanes"]}
    files = sorted(
        candidate.relative_to(session_directory).as_posix()
        for candidate in session_directory.rglob("*")
        if candidate.is_file()
    )
    event_count, event_sha256 = normalized_event_digest(session_directory)
    final_notes = load_notes(session_directory / "exports" / "session.mid")
    reference_notes = load_notes(reference_midi)
    return {
        "schema_version": "atpiano.desktop-replay-validation.v2",
        "status": "passed",
        "path": path,
        "session_id": session["session_id"],
        "source": {
            "frame_count": session["source_frame_count"],
            "sample_rate_hz": session["sample_rate_hz"],
            "duration_s": (session["source_frame_count"] / session["sample_rate_hz"]),
        },
        "horizons": {
            "audio_head_sample": horizons["audio_head_sample"],
            "provisional_sample": horizons["provisional_sample"],
            "commit_sample": horizons["commit_sample"],
        },
        "events": {
            "preview_emissions": lanes["preview"]["event_emission_count"],
            "commit_emissions": lanes["commit"]["events"]["emissions"],
            "normalized_export_count": event_count,
            "normalized_export_sha256": event_sha256,
        },
        "final_notes": [asdict(note) for note in final_notes],
        "golden_reference": {
            "note_count": len(reference_notes),
            "scores": score_notes(reference_notes, final_notes),
        },
        "models": {
            "preview_artifact_sha256": lanes["preview"]["model"]["artifact_sha256"],
            "commit_checkpoint_sha256": lanes["commit"]["model"]["checkpoint_sha256"],
            "commit_config_sha256": lanes["commit"]["model"]["config_sha256"],
            "commit_device": lanes["commit"]["model"]["device"],
        },
        "timing": {
            "sidecar_ready_s": sidecar_ready_s,
            "total_s": total_s,
            "commit_model_load_s": lanes["commit"]["model"]["load_s"],
            "commit_inference_s": lanes["commit"]["inference_s"]["total"],
        },
        "artifacts": {
            "exports_ready": state["exports_ready"],
            "file_count": len(files),
            "mp3_files": [path for path in files if path.lower().endswith(".mp3")],
            "wav_files": [path for path in files if path.lower().endswith(".wav")],
        },
    }


def _require_complete(report: dict[str, Any]) -> None:
    source = report["source"]
    horizons = report["horizons"]
    artifacts = report["artifacts"]
    if (
        source["frame_count"] != 2_016_000
        or source["sample_rate_hz"] != 48_000
        or horizons["audio_head_sample"] != source["frame_count"]
        or horizons["commit_sample"] != source["frame_count"]
        or not 0 <= horizons["provisional_sample"] <= source["frame_count"]
        or not artifacts["exports_ready"]
        or artifacts["mp3_files"] != ["playback/session.mp3"]
        or artifacts["wav_files"]
        or report["models"]["commit_device"] != "cpu"
    ):
        raise RuntimeError("desktop golden replay acceptance failed")


def _render_packaged_score(
    base_url: str,
    headers: dict[str, str],
    session_directory: Path,
) -> dict[str, Any]:
    started = time.monotonic()
    request = urllib.request.Request(
        f"{base_url}/api/score",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        state = json.load(response)
    deadline = time.monotonic() + 5 * 60
    while time.monotonic() < deadline:
        request = urllib.request.Request(
            f"{base_url}/api/score",
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            state = json.load(response)
        if state["status"] in TERMINAL_STATES:
            break
        time.sleep(0.25)
    if state["status"] != "complete":
        raise RuntimeError(f"packaged score failed: {state.get('error')}")
    snapshot = read_json(session_directory / "score" / "current.json")
    if not score_snapshot_is_plausible(snapshot):
        raise RuntimeError("packaged score snapshot is implausible")
    musicxml = session_directory / snapshot["musicxml"]["path"]
    alignment = session_directory / snapshot["alignment"]["path"]
    source_notes = session_directory / snapshot["source_notes"]["path"]
    if (
        sha256_file(musicxml) != snapshot["musicxml"]["sha256"]
        or sha256_file(alignment) != snapshot["alignment"]["sha256"]
        or sha256_file(source_notes) != snapshot["source_notes"]["sha256"]
    ):
        raise RuntimeError("packaged score artifact hash mismatch")
    summary = summarize_musicxml(musicxml.read_bytes())
    alignment_summary = validate_score_alignment(
        read_json(alignment),
        source_notes_path=source_notes,
        musicxml_path=musicxml,
    )
    return {
        "status": "passed",
        "elapsed_s": time.monotonic() - started,
        "commit_sample": snapshot["commit_sample"],
        "input_note_count": snapshot["note_count"],
        "musicxml": {
            "path": snapshot["musicxml"]["path"],
            "sha256": snapshot["musicxml"]["sha256"],
            "bytes": musicxml.stat().st_size,
            "summary": summary,
        },
        "alignment": {
            "path": snapshot["alignment"]["path"],
            "sha256": snapshot["alignment"]["sha256"],
            "summary": alignment_summary,
        },
        "adapter": snapshot["adapter"],
    }


def run_packaged_replay(
    app_bundle: Path,
    workspace: Path,
    *,
    render_score: bool = False,
    score_runtime: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    runtime, python, desktop_origin = packaged_runtime_paths(app_bundle)
    selected_score_runtime = (
        score_runtime.resolve() if score_runtime is not None else runtime / "score-runtime"
    )
    token = secrets.token_hex(32)
    environment = dict(os.environ)
    environment.update(
        {
            "PATH": f"{runtime / 'bin'}{os.pathsep}{environment.get('PATH', '')}",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "ATPIANO_DESKTOP_TOKEN": token,
            "ATPIANO_EXECUTION_BACKEND": "cpu",
            "CUDA_VISIBLE_DEVICES": "",
            **desktop_runtime_environment(workspace),
        }
    )
    if desktop_origin == "http://tauri.localhost":
        environment["ATPIANO_MODEL_WORKER_START_TIMEOUT_S"] = "600"
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(name, None)
    started = time.monotonic()
    process = subprocess.Popen(
        [
            python,
            "-I",
            "-B",
            "-m",
            "atpiano.desktop_sidecar",
            "--workspace",
            workspace,
            "--replay-manifest",
            runtime / "fixture" / "input.json",
            "--model-pack",
            runtime / "model-pack" / "model-pack.json",
            "--expected-model-pack",
            MODEL_PACK_ID,
            "--minimum-free-gib",
            "0",
            "--score-runtime",
            selected_score_runtime,
            "--desktop-origin",
            desktop_origin,
        ],
        cwd=tempfile.gettempdir(),
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.terminate()
        raise RuntimeError("packaged sidecar pipes are unavailable")
    try:
        ready = json.loads(_read_ready_line(process, 180 if render_score else 30))
        sidecar_ready_s = time.monotonic() - started
        base_url = f"http://127.0.0.1:{ready['port']}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": desktop_origin,
            "Content-Type": "application/json",
        }
        handshake_request = urllib.request.Request(
            f"{base_url}/desktop/v1/handshake",
            headers=headers,
        )
        with urllib.request.urlopen(
            handshake_request,
            timeout=10,
        ) as response:
            handshake = json.load(response)
        if bool(handshake["score_available"]) != render_score:
            raise RuntimeError("packaged score capability differs from validation mode")
        request = urllib.request.Request(
            f"{base_url}/api/replay",
            data=b"{}",
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(
            request,
            timeout=(
                WINDOWS_REPLAY_START_TIMEOUT_S
                if desktop_origin == "http://tauri.localhost"
                else REPLAY_START_TIMEOUT_S
            ),
        ) as response:
            state = json.load(response)
        deadline = time.monotonic() + 20 * 60
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{base_url}/api/session",
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                state = json.load(response)
            if state["status"] in TERMINAL_STATES:
                break
            time.sleep(0.5)
        if state["status"] != "complete":
            raise RuntimeError(f"packaged replay failed: {state.get('error')}")
        session_directory = workspace / state["session"]["session_id"]
        report = _summarize(
            state,
            session_directory,
            path="packaged-sidecar",
            reference_midi=runtime / "fixture" / "reference.mid",
            total_s=time.monotonic() - started,
            sidecar_ready_s=sidecar_ready_s,
        )
        _require_complete(report)
        report["score"] = (
            _render_packaged_score(
                base_url,
                headers,
                session_directory,
            )
            if render_score
            else {"status": "not-requested"}
        )
        return report
    finally:
        if not process.stdin.closed:
            process.stdin.close()
        try:
            returncode = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            returncode = process.wait(timeout=5)
        stderr = process.stderr.read()
        if token in stderr:
            raise RuntimeError("packaged sidecar leaked its token")
        if returncode != 0:
            raise RuntimeError(f"packaged sidecar exited {returncode}")


def run_direct_replay(
    runtime_root: Path,
    workspace: Path,
) -> dict[str, Any]:
    runtime = runtime_root.resolve()
    workspace = workspace.resolve()
    model_pack = runtime / "model-pack" / "model-pack.json"
    apply_model_pack(load_model_pack(model_pack), model_pack)
    started = time.monotonic()
    server = create_corrected_workbench_server(
        workspace,
        bind="127.0.0.1",
        port=0,
        correction_mode="after-stop",
        minimum_free_bytes=0,
        replay_manifest=runtime / "fixture" / "input.json",
        replay_realtime=False,
        score_runtime=workspace / ".unavailable-score-runtime",
        compact_recordings=True,
        debug_retention=False,
    )
    try:
        server.start_replay()
        deadline = time.monotonic() + 20 * 60
        while time.monotonic() < deadline:
            state = server.public_state()
            if state["status"] in TERMINAL_STATES:
                break
            time.sleep(0.5)
        if state["status"] != "complete":
            raise RuntimeError(f"direct replay failed: {state.get('error')}")
        session_directory = workspace / state["session"]["session_id"]
        report = _summarize(
            state,
            session_directory,
            path="direct-application-core",
            reference_midi=runtime / "fixture" / "reference.mid",
            total_s=time.monotonic() - started,
            sidecar_ready_s=None,
        )
        _require_complete(report)
        return report
    finally:
        server.server_close()


def compare_replays(
    packaged: dict[str, Any],
    direct: dict[str, Any],
) -> dict[str, Any]:
    direct_notes = [MidiNote(**note) for note in direct["final_notes"]]
    packaged_notes = [MidiNote(**note) for note in packaged["final_notes"]]
    scores = score_notes(direct_notes, packaged_notes)
    direct_events = direct["events"]
    packaged_events = packaged["events"]
    commit_denominator = max(
        1,
        direct_events["commit_emissions"],
        packaged_events["commit_emissions"],
    )
    export_denominator = max(
        1,
        direct_events["normalized_export_count"],
        packaged_events["normalized_export_count"],
    )
    event_tolerance = {
        "preview_emissions_equal": (
            direct_events["preview_emissions"] == packaged_events["preview_emissions"]
        ),
        "commit_emission_relative_delta": (
            abs(direct_events["commit_emissions"] - packaged_events["commit_emissions"])
            / commit_denominator
        ),
        "export_count_relative_delta": (
            abs(
                direct_events["normalized_export_count"]
                - packaged_events["normalized_export_count"]
            )
            / export_denominator
        ),
        "exact_normalized_export_match": (
            direct_events["normalized_export_sha256"] == packaged_events["normalized_export_sha256"]
        ),
    }
    musical_tolerance = {
        "onset_f1_50_ms": scores["onset"]["50_ms"]["f1"],
        "onset_f1_25_ms": scores["onset"]["25_ms"]["f1"],
        "note_with_offset_f1": scores["note_with_offset"]["f1"],
        "frame_f1": scores["frame"]["f1"],
        "matched_velocity_mae": scores["matched_velocity_mae"],
        "direct_note_count": scores["reference_note_count"],
        "packaged_note_count": scores["estimated_note_count"],
    }
    direct_golden = direct["golden_reference"]["scores"]
    packaged_golden = packaged["golden_reference"]["scores"]
    golden_note_denominator = max(
        1,
        len(direct_notes),
        len(packaged_notes),
    )
    golden_quality_delta = {
        "onset_f1_50_ms": abs(
            direct_golden["onset"]["50_ms"]["f1"] - packaged_golden["onset"]["50_ms"]["f1"]
        ),
        "onset_f1_25_ms": abs(
            direct_golden["onset"]["25_ms"]["f1"] - packaged_golden["onset"]["25_ms"]["f1"]
        ),
        "note_with_offset_f1": abs(
            direct_golden["note_with_offset"]["f1"] - packaged_golden["note_with_offset"]["f1"]
        ),
        "frame_f1": abs(direct_golden["frame"]["f1"] - packaged_golden["frame"]["f1"]),
        "matched_velocity_mae": abs(
            direct_golden["matched_velocity_mae"] - packaged_golden["matched_velocity_mae"]
        ),
        "final_note_count_relative": (
            abs(len(direct_notes) - len(packaged_notes)) / golden_note_denominator
        ),
    }
    acceptance_thresholds = {
        "event_relative_delta_max": MAX_EVENT_RELATIVE_DELTA,
        "pairwise_onset_f1_min": MIN_PAIRWISE_ONSET_F1,
        "pairwise_note_with_offset_f1_min": (MIN_PAIRWISE_NOTE_OFFSET_F1),
        "pairwise_frame_f1_min": MIN_PAIRWISE_FRAME_F1,
        "pairwise_velocity_mae_max": MAX_PAIRWISE_VELOCITY_MAE,
        "golden_onset_f1_delta_max": MAX_GOLDEN_ONSET_F1_DELTA,
        "golden_note_with_offset_f1_delta_max": (MAX_GOLDEN_NOTE_OFFSET_F1_DELTA),
        "golden_frame_f1_delta_max": MAX_GOLDEN_FRAME_F1_DELTA,
        "golden_velocity_mae_delta_max": (MAX_GOLDEN_VELOCITY_MAE_DELTA),
        "golden_note_count_relative_delta_max": (MAX_GOLDEN_NOTE_COUNT_RELATIVE_DELTA),
    }
    comparisons = {
        "source": packaged["source"] == direct["source"],
        "horizons": packaged["horizons"] == direct["horizons"],
        "models": packaged["models"] == direct["models"],
        "artifacts": packaged["artifacts"] == direct["artifacts"],
        "golden_reference": (
            packaged["golden_reference"]["note_count"] == direct["golden_reference"]["note_count"]
        ),
        "event_tolerance": (
            event_tolerance["preview_emissions_equal"]
            and event_tolerance["commit_emission_relative_delta"] <= MAX_EVENT_RELATIVE_DELTA
            and event_tolerance["export_count_relative_delta"] <= MAX_EVENT_RELATIVE_DELTA
        ),
        "pairwise_musical_floor": (
            musical_tolerance["onset_f1_50_ms"] >= MIN_PAIRWISE_ONSET_F1
            and musical_tolerance["onset_f1_25_ms"] >= MIN_PAIRWISE_ONSET_F1
            and musical_tolerance["note_with_offset_f1"] >= MIN_PAIRWISE_NOTE_OFFSET_F1
            and musical_tolerance["frame_f1"] >= MIN_PAIRWISE_FRAME_F1
            and musical_tolerance["matched_velocity_mae"] <= MAX_PAIRWISE_VELOCITY_MAE
        ),
        "golden_quality_delta": (
            golden_quality_delta["onset_f1_50_ms"] <= MAX_GOLDEN_ONSET_F1_DELTA
            and golden_quality_delta["onset_f1_25_ms"] <= MAX_GOLDEN_ONSET_F1_DELTA
            and golden_quality_delta["note_with_offset_f1"] <= MAX_GOLDEN_NOTE_OFFSET_F1_DELTA
            and golden_quality_delta["frame_f1"] <= MAX_GOLDEN_FRAME_F1_DELTA
            and golden_quality_delta["matched_velocity_mae"] <= MAX_GOLDEN_VELOCITY_MAE_DELTA
            and golden_quality_delta["final_note_count_relative"]
            <= MAX_GOLDEN_NOTE_COUNT_RELATIVE_DELTA
        ),
    }
    if not all(comparisons.values()):
        raise RuntimeError("packaged and direct replay products differ")
    return {
        "schema_version": "atpiano.desktop-replay-parity.v2",
        "status": "passed",
        "comparisons": comparisons,
        "acceptance_thresholds": acceptance_thresholds,
        "event_tolerance": event_tolerance,
        "pairwise_musical_evidence": musical_tolerance,
        "golden_quality_delta": golden_quality_delta,
        "packaged_session_id": packaged["session_id"],
        "direct_session_id": direct["session_id"],
        "packaged_total_s": packaged["timing"]["total_s"],
        "direct_total_s": direct["timing"]["total_s"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m atpiano.desktop_validation")
    commands = parser.add_subparsers(dest="command", required=True)
    packaged = commands.add_parser("packaged-replay")
    packaged.add_argument("--app", type=Path, required=True)
    packaged.add_argument("--workspace", type=Path, required=True)
    packaged.add_argument("--report", type=Path, required=True)
    packaged_score = commands.add_parser("packaged-score")
    packaged_score.add_argument("--app", type=Path, required=True)
    packaged_score.add_argument("--score-runtime", type=Path)
    packaged_score.add_argument("--workspace", type=Path, required=True)
    packaged_score.add_argument("--report", type=Path, required=True)
    direct = commands.add_parser("direct-replay")
    direct.add_argument("--runtime-root", type=Path, required=True)
    direct.add_argument("--workspace", type=Path, required=True)
    direct.add_argument("--report", type=Path, required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--packaged-report", type=Path, required=True)
    compare.add_argument("--direct-report", type=Path, required=True)
    compare.add_argument("--report", type=Path, required=True)
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    if args.command == "packaged-replay":
        report = run_packaged_replay(args.app, args.workspace)
    elif args.command == "packaged-score":
        report = run_packaged_replay(
            args.app,
            args.workspace,
            render_score=True,
            score_runtime=args.score_runtime,
        )
    elif args.command == "direct-replay":
        report = run_direct_replay(args.runtime_root, args.workspace)
    else:
        packaged = json.loads(args.packaged_report.read_text(encoding="utf-8"))
        direct = json.loads(args.direct_report.read_text(encoding="utf-8"))
        report = compare_replays(packaged, direct)
    write_json(args.report, report)
    print(
        json.dumps(
            {
                "schema_version": report["schema_version"],
                "status": report["status"],
                "report": str(args.report),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
