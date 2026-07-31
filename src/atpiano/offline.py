"""Untouched Basic Pitch offline reference adapter."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from atpiano.fixture import INPUT_SCHEMA
from atpiano.midi import MidiNote, load_notes, note_set_document
from atpiano.notation import generate_notation_artifacts
from atpiano.quality import score_notes, unscored_notes
from atpiano.util import (
    read_json,
    runtime_provenance,
    sha256_file,
    sha256_path,
    utc_now,
    write_json,
    write_jsonl,
)


def _validate_input_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    if manifest.get("schema_version") != INPUT_SCHEMA:
        raise ValueError(
            f"{manifest_path} has unsupported schema_version "
            f"{manifest.get('schema_version')!r}"
        )
    for section in ("audio",):
        if not isinstance(manifest.get(section), dict):
            raise ValueError(f"{manifest_path} is missing object {section!r}")
        for field in ("path", "sha256"):
            if field not in manifest[section]:
                raise ValueError(f"{manifest_path} is missing {section}.{field}")


def _event_id(note: MidiNote, ordinal: int) -> str:
    value = (
        f"{note.pitch}:{note.onset_s:.9f}:{note.offset_s:.9f}:{ordinal}"
    ).encode("ascii")
    return hashlib.sha256(value).hexdigest()[:20]


def _normalized_events(
    notes: list[MidiNote],
    *,
    sample_rate_hz: int,
    emitted_at_ns: int,
    emitted_elapsed_s: float,
) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": "atpiano.note-event.v1",
            "session_id": "offline-reference",
            "event_id": _event_id(note, ordinal),
            "revision": 1,
            "source": "acoustic",
            "lifecycle": "committed",
            "pitch": note.pitch,
            "onset_sample": round(note.onset_s * sample_rate_hz),
            "offset_sample": round(note.offset_s * sample_rate_hz),
            "velocity": note.velocity,
            "confidence": note.velocity / 127.0,
            "pedal_relationship": None,
            "emitted_at_monotonic_ns": emitted_at_ns,
            "emitted_elapsed_s": emitted_elapsed_s,
            "source_to_emission_latency_s": None,
        }
        for ordinal, note in enumerate(notes)
    ]


def _report(run: dict[str, Any], scores: dict[str, Any]) -> str:
    def metric_value(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    def metric_row(name: str, metric: dict[str, Any]) -> str:
        return (
            f"| {name} | {metric_value(metric['precision'])} "
            f"| {metric_value(metric['recall'])} | {metric_value(metric['f1'])} |"
        )

    onset_50 = scores["onset"]["50_ms"]
    onset_25 = scores["onset"]["25_ms"]
    offset = scores["note_with_offset"]
    frame = scores["frame"]
    return "\n".join(
        (
            "# Atpiano Offline Reference",
            "",
            f"- Run: `{run['run_id']}`",
            f"- Input: `{run['input']['input_id']}`",
            f"- Model: Basic Pitch {run['model']['package_version']}",
            f"- Backend artifact: `{run['model']['artifact_kind']}`",
            f"- Reference notes: {scores['reference_note_count'] or 'not supplied'}",
            f"- Estimated notes: {scores['estimated_note_count']}",
            f"- Adapter import/setup: {run['timing_summary']['adapter_setup_s']:.3f} s",
            f"- Inference wall time: {run['timing_summary']['inference_s']:.3f} s",
            "",
            "| Metric | Precision | Recall | F1 |",
            "|---|---:|---:|---:|",
            metric_row("Onset ±50 ms", onset_50),
            metric_row("Onset ±25 ms", onset_25),
            metric_row("Note with offset", offset),
            metric_row("100 Hz frame", frame),
            "",
            "Pedal output is not supported by Basic Pitch. Offline mode does not",
            "claim source-to-emission latency because the complete file is available",
            "before inference starts.",
            "",
        )
    )


def run_offline(
    input_manifest_path: Path,
    run_directory: Path,
    *,
    command: list[str] | None = None,
) -> dict[str, Any]:
    input_manifest_path = input_manifest_path.resolve()
    run_directory = run_directory.resolve()
    if run_directory.exists() and any(run_directory.iterdir()):
        raise FileExistsError(f"run directory is not empty: {run_directory}")
    run_directory.mkdir(parents=True, exist_ok=True)
    process_start_ns = time.perf_counter_ns()

    manifest = read_json(input_manifest_path)
    _validate_input_manifest(manifest, input_manifest_path)
    source_root = input_manifest_path.parent
    source_audio = (source_root / manifest["audio"]["path"]).resolve()
    reference_manifest = manifest.get("reference")
    source_reference = (
        (source_root / reference_manifest["path"]).resolve()
        if isinstance(reference_manifest, dict)
        else None
    )
    if sha256_file(source_audio) != manifest["audio"]["sha256"]:
        raise ValueError(f"audio hash does not match manifest: {source_audio}")
    if (
        source_reference is not None
        and sha256_file(source_reference) != reference_manifest["sha256"]
    ):
        raise ValueError(f"reference hash does not match manifest: {source_reference}")

    audio_path = run_directory / "input.wav"
    shutil.copyfile(source_audio, audio_path)
    reference_path = run_directory / "reference.mid" if source_reference is not None else None
    if source_reference is not None and reference_path is not None:
        shutil.copyfile(source_reference, reference_path)
    copied_manifest = json.loads(json.dumps(manifest))
    copied_manifest["audio"]["path"] = audio_path.name
    if reference_path is not None:
        copied_manifest["reference"]["path"] = reference_path.name
    write_json(run_directory / "input.json", copied_manifest)

    started_at = utc_now()
    adapter_setup_start_ns = time.perf_counter_ns()
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.constants import ANNOT_N_FRAMES, AUDIO_N_SAMPLES, AUDIO_SAMPLE_RATE, FFT_HOP
    from basic_pitch.inference import predict
    adapter_setup_end_ns = time.perf_counter_ns()

    default_onset_threshold = 0.5
    default_frame_threshold = 0.3
    default_minimum_note_length_ms = 127.7
    default_overlapping_frames = 30

    inference_start_ns = time.perf_counter_ns()
    model_output, midi_data, _ = predict(audio_path)
    inference_end_ns = time.perf_counter_ns()
    inference_s = (inference_end_ns - inference_start_ns) / 1_000_000_000.0

    prediction_path = run_directory / "prediction.mid"
    midi_data.write(str(prediction_path))
    write_json(
        run_directory / "reference.json",
        (
            note_set_document(reference_path)
            if reference_path is not None
            else {"schema_version": "atpiano.note-set.v1", "notes": [], "pedals": []}
        ),
    )
    write_json(run_directory / "prediction.json", note_set_document(prediction_path))
    raw_directory = run_directory / "raw"
    raw_directory.mkdir(parents=True, exist_ok=True)
    raw_path = raw_directory / "basic_pitch.npz"
    np.savez_compressed(
        raw_path,
        note=model_output["note"],
        onset=model_output["onset"],
        contour=model_output["contour"],
    )
    model_path = Path(ICASSP_2022_MODEL_PATH).resolve()
    hop_size = AUDIO_N_SAMPLES - default_overlapping_frames * FFT_HOP
    raw_metadata = {
        "schema_version": "atpiano.raw.basic-pitch.v1",
        "origin": "unmodified basic_pitch.inference.predict return value",
        "arrays": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
            }
            for name, value in model_output.items()
        },
        "source_coordinates": {
            "sample_rate_hz": AUDIO_SAMPLE_RATE,
            "audio_window_samples": AUDIO_N_SAMPLES,
            "fft_hop_samples": FFT_HOP,
            "annotation_frames_per_window": ANNOT_N_FRAMES,
            "overlapping_frames": default_overlapping_frames,
            "window_hop_samples": hop_size,
            "warning": (
                "Basic Pitch 0.4.0 concatenated frame rows are not a uniform "
                "source-sample clock; preserve window coordinates in replay mode."
            ),
        },
    }
    write_json(raw_directory / "metadata.json", raw_metadata)

    prediction_notes = load_notes(prediction_path)
    emitted_at_ns = time.perf_counter_ns()
    emitted_elapsed_s = (emitted_at_ns - process_start_ns) / 1_000_000_000.0
    events = _normalized_events(
        prediction_notes,
        sample_rate_hz=int(manifest["audio"]["sample_rate_hz"]),
        emitted_at_ns=emitted_at_ns,
        emitted_elapsed_s=emitted_elapsed_s,
    )
    write_jsonl(run_directory / "events.jsonl", events)
    notation = generate_notation_artifacts(run_directory)

    scores = (
        score_notes(load_notes(reference_path), prediction_notes)
        if reference_path is not None
        else unscored_notes(prediction_notes)
    )
    write_json(run_directory / "scores.json", scores)
    timing_rows = [
        {
            "schema_version": "atpiano.stage-timing.v1",
            "mode": "offline",
            "stage": "adapter_import_and_setup",
            "start_monotonic_ns": adapter_setup_start_ns,
            "end_monotonic_ns": adapter_setup_end_ns,
            "duration_s": (adapter_setup_end_ns - adapter_setup_start_ns)
            / 1_000_000_000.0,
            "source_first_sample": None,
            "source_frame_count": None,
        },
        {
            "schema_version": "atpiano.stage-timing.v1",
            "mode": "offline",
            "stage": "model_and_decode",
            "start_monotonic_ns": inference_start_ns,
            "end_monotonic_ns": inference_end_ns,
            "duration_s": inference_s,
            "source_first_sample": 0,
            "source_frame_count": int(manifest["audio"]["frame_count"]),
        }
    ]
    write_jsonl(run_directory / "timing.jsonl", timing_rows)

    artifact_kind = model_path.suffix.lstrip(".") or "directory"
    run: dict[str, Any] = {
        "schema_version": "atpiano.run.v1",
        "run_id": run_directory.name,
        "mode": "offline-reference",
        "status": "complete",
        "started_at": started_at,
        "completed_at": utc_now(),
        "command": command,
        "input": {
            "input_id": manifest["input_id"],
            "manifest": "input.json",
            "audio": audio_path.name,
            "audio_sha256": sha256_file(audio_path),
            "reference_midi": reference_path.name if reference_path is not None else None,
            "reference_sha256": (
                sha256_file(reference_path) if reference_path is not None else None
            ),
        },
        "model": {
            "adapter": "basic-pitch-offline-reference-v1",
            "package_version": runtime_provenance()["packages"]["basic-pitch"],
            "artifact_path": str(model_path),
            "artifact_sha256": sha256_path(model_path),
            "artifact_kind": artifact_kind,
            "parameters": {
                "onset_threshold": default_onset_threshold,
                "frame_threshold": default_frame_threshold,
                "minimum_note_length_ms": default_minimum_note_length_ms,
                "melodia_trick": True,
                "warm_up_policy": "none",
                "backend_cache_state": "uncontrolled",
            },
        },
        "runtime": runtime_provenance(),
        "artifacts": {
            "prediction_midi": prediction_path.name,
            "prediction_sha256": sha256_file(prediction_path),
            "reference_notes": "reference.json",
            "prediction_notes": "prediction.json",
            "raw_model_output": raw_path.relative_to(
                run_directory
            ).as_posix(),
            "raw_model_output_sha256": sha256_file(raw_path),
            "events": "events.jsonl",
            "scores": "scores.json",
            "timing": "timing.jsonl",
            "report": "report.md",
            "notation_manifest": "notation/current.json",
            "notation_musicxml": notation["artifacts"]["musicxml"],
        },
        "timing_summary": {
            "adapter_setup_s": (adapter_setup_end_ns - adapter_setup_start_ns)
            / 1_000_000_000.0,
            "inference_s": inference_s,
            "artifact_completion_s": (
                time.perf_counter_ns() - process_start_ns
            )
            / 1_000_000_000.0,
            "source_to_emission_latency": None,
        },
    }
    write_json(run_directory / "run.json", run)
    (run_directory / "report.md").write_text(_report(run, scores), encoding="utf-8")
    return run
