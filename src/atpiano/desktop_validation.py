"""R5 replay and parity validation for the packaged desktop runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import select
import subprocess
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.desktop import apply_model_pack, load_model_pack
from atpiano.midi import MidiNote, load_notes
from atpiano.quality import score_notes
from atpiano.util import write_json

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
VOLATILE_EVENT_FIELDS = {
    "emitted_at_monotonic_ns",
    "emitted_elapsed_s",
    "event_id",
    "sequence",
    "session_id",
    "source_to_emission_latency_s",
}


def normalized_event_digest(session_directory: Path) -> tuple[int, str]:
    events = []
    export = session_directory / "exports" / "session.jsonl"
    for line in export.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        events.append(
            {
                key: value
                for key, value in event.items()
                if key not in VOLATILE_EVENT_FIELDS
            }
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
    event_count, event_sha256 = normalized_event_digest(
        session_directory
    )
    final_notes = load_notes(
        session_directory / "exports" / "session.mid"
    )
    reference_notes = load_notes(reference_midi)
    return {
        "schema_version": "atpiano.desktop-replay-validation.v2",
        "status": "passed",
        "path": path,
        "session_id": session["session_id"],
        "source": {
            "frame_count": session["source_frame_count"],
            "sample_rate_hz": session["sample_rate_hz"],
            "duration_s": (
                session["source_frame_count"] / session["sample_rate_hz"]
            ),
        },
        "horizons": {
            "audio_head_sample": horizons["audio_head_sample"],
            "provisional_sample": horizons["provisional_sample"],
            "commit_sample": horizons["commit_sample"],
        },
        "events": {
            "preview_emissions": lanes["preview"][
                "event_emission_count"
            ],
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
            "preview_artifact_sha256": lanes["preview"]["model"][
                "artifact_sha256"
            ],
            "commit_checkpoint_sha256": lanes["commit"]["model"][
                "checkpoint_sha256"
            ],
            "commit_config_sha256": lanes["commit"]["model"][
                "config_sha256"
            ],
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
            "mp3_files": [
                path for path in files if path.lower().endswith(".mp3")
            ],
            "wav_files": [
                path for path in files if path.lower().endswith(".wav")
            ],
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


def run_packaged_replay(
    app_bundle: Path,
    workspace: Path,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    runtime = (
        app_bundle.resolve()
        / "Contents"
        / "Resources"
        / "desktop-runtime"
    )
    token = secrets.token_hex(32)
    environment = {
        "HOME": str(Path.home()),
        "PATH": f"{runtime / 'bin'}:/usr/bin:/bin",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "ATPIANO_DESKTOP_TOKEN": token,
        "ATPIANO_EXECUTION_BACKEND": "cpu",
        "CUDA_VISIBLE_DEVICES": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    started = time.monotonic()
    process = subprocess.Popen(
        [
            runtime / "bin" / "python3",
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
        ],
        cwd="/tmp",
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
        readable, _, _ = select.select([process.stdout], [], [], 30)
        if not readable:
            raise RuntimeError("packaged sidecar ready timeout")
        ready = json.loads(process.stdout.readline())
        sidecar_ready_s = time.monotonic() - started
        base_url = f"http://127.0.0.1:{ready['port']}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": "tauri://localhost",
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(
            f"{base_url}/api/replay",
            data=b"{}",
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
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
            raise RuntimeError(
                f"packaged replay failed: {state.get('error')}"
            )
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
    direct_notes = [
        MidiNote(**note) for note in direct["final_notes"]
    ]
    packaged_notes = [
        MidiNote(**note) for note in packaged["final_notes"]
    ]
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
            direct_events["preview_emissions"]
            == packaged_events["preview_emissions"]
        ),
        "commit_emission_relative_delta": (
            abs(
                direct_events["commit_emissions"]
                - packaged_events["commit_emissions"]
            )
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
            direct_events["normalized_export_sha256"]
            == packaged_events["normalized_export_sha256"]
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
            direct_golden["onset"]["50_ms"]["f1"]
            - packaged_golden["onset"]["50_ms"]["f1"]
        ),
        "onset_f1_25_ms": abs(
            direct_golden["onset"]["25_ms"]["f1"]
            - packaged_golden["onset"]["25_ms"]["f1"]
        ),
        "note_with_offset_f1": abs(
            direct_golden["note_with_offset"]["f1"]
            - packaged_golden["note_with_offset"]["f1"]
        ),
        "frame_f1": abs(
            direct_golden["frame"]["f1"]
            - packaged_golden["frame"]["f1"]
        ),
        "matched_velocity_mae": abs(
            direct_golden["matched_velocity_mae"]
            - packaged_golden["matched_velocity_mae"]
        ),
        "final_note_count_relative": (
            abs(len(direct_notes) - len(packaged_notes))
            / golden_note_denominator
        ),
    }
    acceptance_thresholds = {
        "event_relative_delta_max": MAX_EVENT_RELATIVE_DELTA,
        "pairwise_onset_f1_min": MIN_PAIRWISE_ONSET_F1,
        "pairwise_note_with_offset_f1_min": (
            MIN_PAIRWISE_NOTE_OFFSET_F1
        ),
        "pairwise_frame_f1_min": MIN_PAIRWISE_FRAME_F1,
        "pairwise_velocity_mae_max": MAX_PAIRWISE_VELOCITY_MAE,
        "golden_onset_f1_delta_max": MAX_GOLDEN_ONSET_F1_DELTA,
        "golden_note_with_offset_f1_delta_max": (
            MAX_GOLDEN_NOTE_OFFSET_F1_DELTA
        ),
        "golden_frame_f1_delta_max": MAX_GOLDEN_FRAME_F1_DELTA,
        "golden_velocity_mae_delta_max": (
            MAX_GOLDEN_VELOCITY_MAE_DELTA
        ),
        "golden_note_count_relative_delta_max": (
            MAX_GOLDEN_NOTE_COUNT_RELATIVE_DELTA
        ),
    }
    comparisons = {
        "source": packaged["source"] == direct["source"],
        "horizons": packaged["horizons"] == direct["horizons"],
        "models": packaged["models"] == direct["models"],
        "artifacts": packaged["artifacts"] == direct["artifacts"],
        "golden_reference": (
            packaged["golden_reference"]["note_count"]
            == direct["golden_reference"]["note_count"]
        ),
        "event_tolerance": (
            event_tolerance["preview_emissions_equal"]
            and event_tolerance["commit_emission_relative_delta"]
            <= MAX_EVENT_RELATIVE_DELTA
            and event_tolerance["export_count_relative_delta"]
            <= MAX_EVENT_RELATIVE_DELTA
        ),
        "pairwise_musical_floor": (
            musical_tolerance["onset_f1_50_ms"]
            >= MIN_PAIRWISE_ONSET_F1
            and musical_tolerance["onset_f1_25_ms"]
            >= MIN_PAIRWISE_ONSET_F1
            and musical_tolerance["note_with_offset_f1"]
            >= MIN_PAIRWISE_NOTE_OFFSET_F1
            and musical_tolerance["frame_f1"]
            >= MIN_PAIRWISE_FRAME_F1
            and musical_tolerance["matched_velocity_mae"]
            <= MAX_PAIRWISE_VELOCITY_MAE
        ),
        "golden_quality_delta": (
            golden_quality_delta["onset_f1_50_ms"]
            <= MAX_GOLDEN_ONSET_F1_DELTA
            and golden_quality_delta["onset_f1_25_ms"]
            <= MAX_GOLDEN_ONSET_F1_DELTA
            and golden_quality_delta["note_with_offset_f1"]
            <= MAX_GOLDEN_NOTE_OFFSET_F1_DELTA
            and golden_quality_delta["frame_f1"]
            <= MAX_GOLDEN_FRAME_F1_DELTA
            and golden_quality_delta["matched_velocity_mae"]
            <= MAX_GOLDEN_VELOCITY_MAE_DELTA
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
    parser = argparse.ArgumentParser(
        prog="python -m atpiano.desktop_validation"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    packaged = commands.add_parser("packaged-replay")
    packaged.add_argument("--app", type=Path, required=True)
    packaged.add_argument("--workspace", type=Path, required=True)
    packaged.add_argument("--report", type=Path, required=True)
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
    elif args.command == "direct-replay":
        report = run_direct_replay(args.runtime_root, args.workspace)
    else:
        packaged = json.loads(
            args.packaged_report.read_text(encoding="utf-8")
        )
        direct = json.loads(
            args.direct_report.read_text(encoding="utf-8")
        )
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
