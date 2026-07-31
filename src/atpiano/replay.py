"""Wall-clock-cadence Basic Pitch replay benchmark."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile

from atpiano.fixture import INPUT_SCHEMA
from atpiano.midi import MidiNote, load_notes, note_set_document, write_notes
from atpiano.quality import match_note_indices, score_notes, unscored_notes
from atpiano.reconcile import NoteTrack, Reconciler, WindowRegion
from atpiano.util import (
    read_json,
    runtime_provenance,
    sha256_file,
    sha256_path,
    utc_now,
    write_json,
    write_jsonl,
)


@dataclass(frozen=True)
class ReplayWindow:
    index: int
    source_start_sample: int
    source_end_sample: int
    required_source_end_sample: int


def _validate_manifest(manifest: dict[str, Any], path: Path) -> None:
    if manifest.get("schema_version") != INPUT_SCHEMA:
        raise ValueError(f"{path} has unsupported schema_version")
    for section in ("audio",):
        if not isinstance(manifest.get(section), dict):
            raise ValueError(f"{path} is missing {section}")


def _windows(
    frame_count: int,
    *,
    audio_window_samples: int,
    hop_samples: int,
    left_pad_samples: int,
) -> list[ReplayWindow]:
    padded_frame_count = frame_count + left_pad_samples
    return [
        ReplayWindow(
            index=index,
            source_start_sample=padded_start - left_pad_samples,
            source_end_sample=padded_start - left_pad_samples + audio_window_samples,
            required_source_end_sample=min(
                frame_count,
                padded_start - left_pad_samples + audio_window_samples,
            ),
        )
        for index, padded_start in enumerate(range(0, padded_frame_count, hop_samples))
    ]


def _prepare_window(audio: np.ndarray, window: ReplayWindow, frame_count: int) -> np.ndarray:
    result = np.zeros(window.source_end_sample - window.source_start_sample, dtype=np.float32)
    source_start = max(0, window.source_start_sample)
    source_end = min(frame_count, window.source_end_sample)
    if source_end > source_start:
        destination_start = source_start - window.source_start_sample
        destination_end = destination_start + (source_end - source_start)
        result[destination_start:destination_end] = audio[source_start:source_end]
    return result.reshape((1, result.shape[0], 1))


def _latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "p50": None, "p95": None, "max": None}
    return {
        "count": len(values),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def _lifecycle_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    return {
        lifecycle: sum(event["lifecycle"] == lifecycle for event in events)
        for lifecycle in ("provisional", "committed", "retracted")
    }


def _latency_scores(
    reference: list[MidiNote],
    tracks: list[NoteTrack],
    *,
    sample_rate_hz: int,
    session_origin_ns: int,
    realtime: bool,
) -> dict[str, Any]:
    if not realtime:
        return {
            "realtime": False,
            "predicted_onset_to_first_visible_s": _latency_summary([]),
            "predicted_onset_to_commit_s": _latency_summary([]),
            "reference_onset_to_first_visible_s": _latency_summary([]),
            "reference_onset_to_commit_s": _latency_summary([]),
        }
    estimates = [track.note for track in tracks]
    predicted_first = [
        (track.first_emitted_ns - session_origin_ns) / 1_000_000_000.0
        - track.note.onset_s
        for track in tracks
    ]
    predicted_commit = [
        (track.committed_emitted_ns - session_origin_ns) / 1_000_000_000.0
        - track.note.onset_s
        for track in tracks
        if track.committed_emitted_ns is not None
    ]
    reference_first: list[float] = []
    reference_commit: list[float] = []
    for reference_index, estimate_index in match_note_indices(reference, estimates):
        track = tracks[estimate_index]
        reference_onset = reference[reference_index].onset_s
        reference_first.append(
            (track.first_emitted_ns - session_origin_ns) / 1_000_000_000.0
            - reference_onset
        )
        if track.committed_emitted_ns is not None:
            reference_commit.append(
                (track.committed_emitted_ns - session_origin_ns)
                / 1_000_000_000.0
                - reference_onset
            )
    return {
        "realtime": True,
        "sample_rate_hz": sample_rate_hz,
        "predicted_onset_to_first_visible_s": _latency_summary(predicted_first),
        "predicted_onset_to_commit_s": _latency_summary(predicted_commit),
        "reference_onset_to_first_visible_s": _latency_summary(reference_first),
        "reference_onset_to_commit_s": _latency_summary(reference_commit),
    }


def _report(run: dict[str, Any], scores: dict[str, Any]) -> str:
    onset = scores["onset"]["50_ms"]
    first_visible = scores["latency"]["reference_onset_to_first_visible_s"]
    committed = scores["latency"]["reference_onset_to_commit_s"]
    lifecycle = scores["lifecycle"]

    def seconds(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    onset_f1 = "not scored" if onset["f1"] is None else f"{onset['f1']:.3f}"
    return "\n".join(
        (
            "# Atpiano Live Replay",
            "",
            f"- Run: `{run['run_id']}`",
            f"- Input: `{run['input']['input_id']}`",
            f"- Cadence: {'wall clock' if run['replay']['realtime'] else 'no-wait functional'}",
            f"- Model windows: {run['replay']['window_count']}",
            f"- Final estimated notes: {scores['estimated_note_count']}",
            f"- Onset F1 at 50 ms: {onset_f1}",
            "",
            "| Event latency | p50 s | p95 s | max s | count |",
            "|---|---:|---:|---:|---:|",
            f"| first visible, matched reference | {seconds(first_visible['p50'])} | "
            f"{seconds(first_visible['p95'])} | {seconds(first_visible['max'])} | "
            f"{first_visible['count']} |",
            f"| committed, matched reference | {seconds(committed['p50'])} | "
            f"{seconds(committed['p95'])} | {seconds(committed['max'])} | "
            f"{committed['count']} |",
            "",
            f"Lifecycle emissions: {lifecycle['provisional']} provisional, "
            f"{lifecycle['committed']} committed, "
            f"{lifecycle['retracted']} retracted.",
            "",
            "Latency includes required future samples, replay scheduling, inference,",
            "decoding, and reconciliation. It excludes microphone and transport time.",
            "",
        )
    )


def run_replay(
    input_manifest_path: Path,
    run_directory: Path,
    *,
    realtime: bool = True,
    block_samples: int = 1024,
    command: list[str] | None = None,
) -> dict[str, Any]:
    input_manifest_path = input_manifest_path.resolve()
    run_directory = run_directory.resolve()
    if run_directory.exists() and any(run_directory.iterdir()):
        raise FileExistsError(f"run directory is not empty: {run_directory}")
    run_directory.mkdir(parents=True, exist_ok=True)
    process_start_ns = time.perf_counter_ns()
    started_at = utc_now()

    manifest = read_json(input_manifest_path)
    _validate_manifest(manifest, input_manifest_path)
    source_root = input_manifest_path.parent
    source_audio = (source_root / manifest["audio"]["path"]).resolve()
    reference_manifest = manifest.get("reference")
    source_reference = (
        (source_root / reference_manifest["path"]).resolve()
        if isinstance(reference_manifest, dict)
        else None
    )
    if sha256_file(source_audio) != manifest["audio"]["sha256"]:
        raise ValueError("audio hash does not match input manifest")
    if (
        source_reference is not None
        and sha256_file(source_reference) != reference_manifest["sha256"]
    ):
        raise ValueError("reference hash does not match input manifest")

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

    audio, sample_rate_hz = soundfile.read(
        audio_path,
        dtype="float32",
        always_2d=True,
    )
    audio = np.mean(audio, axis=1, dtype=np.float32)
    expected_sample_rate = int(manifest["audio"]["sample_rate_hz"])
    if sample_rate_hz != expected_sample_rate:
        raise ValueError(
            f"WAV sample rate {sample_rate_hz} does not match manifest "
            f"{expected_sample_rate}"
        )

    adapter_import_start_ns = time.perf_counter_ns()
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.constants import ANNOT_N_FRAMES, AUDIO_N_SAMPLES, AUDIO_SAMPLE_RATE, FFT_HOP
    from basic_pitch.inference import Model
    from basic_pitch.note_creation import model_output_to_notes
    adapter_import_end_ns = time.perf_counter_ns()
    if sample_rate_hz != AUDIO_SAMPLE_RATE:
        raise ValueError(
            f"replay adapter currently requires {AUDIO_SAMPLE_RATE} Hz audio, "
            f"got {sample_rate_hz} Hz"
        )

    model_load_start_ns = time.perf_counter_ns()
    model_path = Path(ICASSP_2022_MODEL_PATH).resolve()
    model = Model(model_path)
    model_load_end_ns = time.perf_counter_ns()

    overlapping_frames = 30
    overlap_samples = overlapping_frames * FFT_HOP
    right_guard_samples = 20 * FFT_HOP
    left_guard_samples = overlap_samples - right_guard_samples
    hop_samples = AUDIO_N_SAMPLES - overlap_samples
    frame_count = audio.shape[0]
    windows = _windows(
        frame_count,
        audio_window_samples=AUDIO_N_SAMPLES,
        hop_samples=hop_samples,
        left_pad_samples=overlap_samples // 2,
    )

    raw_directory = run_directory / "raw" / "windows"
    raw_directory.mkdir(parents=True, exist_ok=True)
    timing_rows: list[dict[str, Any]] = [
        {
            "schema_version": "atpiano.stage-timing.v1",
            "mode": "replay",
            "stage": "adapter_import",
            "start_monotonic_ns": adapter_import_start_ns,
            "end_monotonic_ns": adapter_import_end_ns,
            "duration_s": (adapter_import_end_ns - adapter_import_start_ns)
            / 1_000_000_000.0,
            "source_first_sample": None,
            "source_frame_count": None,
        },
        {
            "schema_version": "atpiano.stage-timing.v1",
            "mode": "replay",
            "stage": "model_load",
            "start_monotonic_ns": model_load_start_ns,
            "end_monotonic_ns": model_load_end_ns,
            "duration_s": (model_load_end_ns - model_load_start_ns)
            / 1_000_000_000.0,
            "source_first_sample": None,
            "source_frame_count": None,
        },
    ]
    raw_index: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    session_origin_ns = time.perf_counter_ns()
    reconciler = Reconciler(
        session_id=run_directory.name,
        sample_rate_hz=sample_rate_hz,
        session_origin_ns=session_origin_ns,
        realtime=realtime,
    )
    next_window = 0

    def process_ready_window(window: ReplayWindow) -> None:
        prepare_start_ns = time.perf_counter_ns()
        model_input = _prepare_window(audio, window, frame_count)
        prepare_end_ns = time.perf_counter_ns()
        inference_start_ns = time.perf_counter_ns()
        output = model.predict(model_input)
        inference_end_ns = time.perf_counter_ns()

        raw_path = raw_directory / f"{window.index:04d}.npz"
        np.savez_compressed(
            raw_path,
            note=output["note"],
            onset=output["onset"],
            contour=output["contour"],
        )
        decode_start_ns = time.perf_counter_ns()
        _, note_events = model_output_to_notes(
            {name: values[0].copy() for name, values in output.items()},
            onset_thresh=0.5,
            frame_thresh=0.3,
            min_note_len=round(127.7 / 1000 * (AUDIO_SAMPLE_RATE / FFT_HOP)),
            min_freq=None,
            max_freq=None,
            multiple_pitch_bends=False,
            melodia_trick=True,
            midi_tempo=120,
        )
        candidates = [
            (
                MidiNote(
                    onset_s=float(start_s) + window.source_start_sample / sample_rate_hz,
                    offset_s=float(end_s) + window.source_start_sample / sample_rate_hz,
                    pitch=int(pitch),
                    velocity=max(1, min(127, round(float(amplitude) * 127))),
                ),
                float(amplitude),
            )
            for start_s, end_s, pitch, amplitude, _ in note_events
        ]
        decode_end_ns = time.perf_counter_ns()
        region = WindowRegion(
            index=window.index,
            source_start_sample=window.source_start_sample,
            source_end_sample=window.source_end_sample,
            left_guard_samples=left_guard_samples,
            right_guard_samples=right_guard_samples,
            is_first=window.index == 0,
            has_future=window.index < len(windows) - 1,
        )
        reconcile_start_ns = time.perf_counter_ns()
        all_events.extend(
            reconciler.process(
                candidates,
                region,
                emitted_ns=reconcile_start_ns,
                total_source_samples=frame_count,
            )
        )
        reconcile_end_ns = time.perf_counter_ns()
        raw_index.append(
            {
                "schema_version": "atpiano.raw-window.v1",
                "window_index": window.index,
                "path": raw_path.relative_to(run_directory).as_posix(),
                "sha256": sha256_file(raw_path),
                "source_start_sample": window.source_start_sample,
                "source_end_sample": window.source_end_sample,
                "required_source_end_sample": window.required_source_end_sample,
                "arrays": {
                    name: {"shape": list(values.shape), "dtype": str(values.dtype)}
                    for name, values in output.items()
                },
            }
        )
        for stage, stage_start, stage_end in (
            ("window_prepare", prepare_start_ns, prepare_end_ns),
            ("model_inference", inference_start_ns, inference_end_ns),
            ("decode", decode_start_ns, decode_end_ns),
            ("reconcile_and_emit", reconcile_start_ns, reconcile_end_ns),
        ):
            timing_rows.append(
                {
                    "schema_version": "atpiano.stage-timing.v1",
                    "mode": "replay",
                    "stage": stage,
                    "window_index": window.index,
                    "start_monotonic_ns": stage_start,
                    "end_monotonic_ns": stage_end,
                    "duration_s": (stage_end - stage_start) / 1_000_000_000.0,
                    "source_first_sample": window.source_start_sample,
                    "source_frame_count": AUDIO_N_SAMPLES,
                }
            )

    available_samples = 0
    while available_samples < frame_count:
        block_start = available_samples
        available_samples = min(frame_count, available_samples + block_samples)
        scheduled_ns = session_origin_ns + round(
            available_samples / sample_rate_hz * 1_000_000_000
        )
        wait_start_ns = time.perf_counter_ns()
        if realtime:
            remaining_s = (scheduled_ns - wait_start_ns) / 1_000_000_000.0
            if remaining_s > 0:
                time.sleep(remaining_s)
        delivered_ns = time.perf_counter_ns()
        timing_rows.append(
            {
                "schema_version": "atpiano.stage-timing.v1",
                "mode": "replay",
                "stage": "replay_delivery",
                "start_monotonic_ns": wait_start_ns,
                "end_monotonic_ns": delivered_ns,
                "duration_s": (delivered_ns - wait_start_ns) / 1_000_000_000.0,
                "scheduled_monotonic_ns": scheduled_ns if realtime else None,
                "schedule_lateness_s": (
                    (delivered_ns - scheduled_ns) / 1_000_000_000.0
                    if realtime
                    else None
                ),
                "source_first_sample": block_start,
                "source_frame_count": available_samples - block_start,
            }
        )
        while (
            next_window < len(windows)
            and windows[next_window].required_source_end_sample <= available_samples
        ):
            process_ready_window(windows[next_window])
            next_window += 1

    while next_window < len(windows):
        process_ready_window(windows[next_window])
        next_window += 1

    final_tracks = reconciler.final_tracks()
    prediction_notes = [track.note for track in final_tracks]
    prediction_path = run_directory / "prediction.mid"
    write_notes(prediction_path, prediction_notes)
    write_json(
        run_directory / "reference.json",
        (
            note_set_document(reference_path)
            if reference_path is not None
            else {"schema_version": "atpiano.note-set.v1", "notes": [], "pedals": []}
        ),
    )
    write_json(run_directory / "prediction.json", note_set_document(prediction_path))
    write_jsonl(run_directory / "events.jsonl", all_events)
    write_jsonl(run_directory / "timing.jsonl", timing_rows)
    write_jsonl(run_directory / "raw" / "windows.jsonl", raw_index)
    write_json(
        run_directory / "raw" / "metadata.json",
        {
            "schema_version": "atpiano.raw.basic-pitch.windows.v1",
            "sample_rate_hz": sample_rate_hz,
            "audio_window_samples": AUDIO_N_SAMPLES,
            "fft_hop_samples": FFT_HOP,
            "annotation_frames_per_window": ANNOT_N_FRAMES,
            "overlapping_frames": overlapping_frames,
            "left_guard_samples": left_guard_samples,
            "right_guard_samples": right_guard_samples,
            "window_hop_samples": hop_samples,
            "commit_policy": (
                "emit the center region directly; emit the right edge "
                "provisionally and commit or retract it against the next window"
            ),
        },
    )

    reference_notes = load_notes(reference_path) if reference_path is not None else []
    scores = (
        score_notes(reference_notes, prediction_notes)
        if reference_path is not None
        else unscored_notes(prediction_notes)
    )
    scores["latency"] = _latency_scores(
        reference_notes,
        final_tracks,
        sample_rate_hz=sample_rate_hz,
        session_origin_ns=session_origin_ns,
        realtime=realtime,
    )
    scores["lifecycle"] = _lifecycle_counts(all_events)
    scores["provisional_to_committed_count"] = sum(
        track.revision > 1 and track.lifecycle == "committed"
        for track in reconciler.tracks
    )
    scores["provisional_to_committed_s"] = _latency_summary(
        [
            (track.committed_emitted_ns - track.first_emitted_ns) / 1_000_000_000.0
            for track in reconciler.tracks
            if track.revision > 1
            and track.lifecycle == "committed"
            and track.committed_emitted_ns is not None
        ]
    )
    scores["revised_event_rate"] = (
        sum(track.revision > 1 for track in reconciler.tracks)
        / len(reconciler.tracks)
        if reconciler.tracks
        else 0.0
    )
    scores["retraction_rate"] = (
        scores["lifecycle"]["retracted"] / scores["lifecycle"]["provisional"]
        if scores["lifecycle"]["provisional"]
        else 0.0
    )
    write_json(run_directory / "scores.json", scores)

    inference_durations = [
        row["duration_s"] for row in timing_rows if row["stage"] == "model_inference"
    ]
    lateness = [
        row["schedule_lateness_s"]
        for row in timing_rows
        if row["stage"] == "replay_delivery" and row["schedule_lateness_s"] is not None
    ]
    run: dict[str, Any] = {
        "schema_version": "atpiano.run.v1",
        "run_id": run_directory.name,
        "mode": "live-replay",
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
            "adapter": "basic-pitch-window-replay-v1",
            "package_version": runtime_provenance()["packages"]["basic-pitch"],
            "artifact_path": str(model_path),
            "artifact_sha256": sha256_path(model_path),
            "artifact_kind": model_path.suffix.lstrip(".") or "directory",
            "parameters": {
                "onset_threshold": 0.5,
                "frame_threshold": 0.3,
                "minimum_note_length_ms": 127.7,
                "melodia_trick": True,
                "warm_up_policy": "load model before replay; do not infer",
                "backend_cache_state": "uncontrolled",
            },
        },
        "runtime": runtime_provenance(),
        "replay": {
            "realtime": realtime,
            "block_samples": block_samples,
            "block_duration_s": block_samples / sample_rate_hz,
            "session_origin_monotonic_ns": session_origin_ns,
            "window_count": len(windows),
            "window_samples": AUDIO_N_SAMPLES,
            "window_hop_samples": hop_samples,
            "left_guard_samples": left_guard_samples,
            "right_guard_samples": right_guard_samples,
            "commit_policy": "center commit with one-window provisional right edge",
        },
        "artifacts": {
            "prediction_midi": prediction_path.name,
            "prediction_sha256": sha256_file(prediction_path),
            "reference_notes": "reference.json",
            "prediction_notes": "prediction.json",
            "raw_window_index": "raw/windows.jsonl",
            "events": "events.jsonl",
            "scores": "scores.json",
            "timing": "timing.jsonl",
            "report": "report.md",
        },
        "timing_summary": {
            "adapter_import_s": (
                adapter_import_end_ns - adapter_import_start_ns
            )
            / 1_000_000_000.0,
            "model_load_s": (model_load_end_ns - model_load_start_ns)
            / 1_000_000_000.0,
            "inference_s": _latency_summary(inference_durations),
            "replay_schedule_lateness_s": _latency_summary(lateness),
            "artifact_completion_s": (
                time.perf_counter_ns() - process_start_ns
            )
            / 1_000_000_000.0,
        },
    }
    write_json(run_directory / "run.json", run)
    (run_directory / "report.md").write_text(_report(run, scores), encoding="utf-8")
    return run
