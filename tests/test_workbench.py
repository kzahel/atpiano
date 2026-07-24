from __future__ import annotations

import base64
import io
import json
import shutil
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

import pytest

from atpiano.capture import BROWSER_CAPTURE_SCHEMA, write_browser_capture_artifacts
from atpiano.util import read_json, write_json
from atpiano.workbench import create_workbench_server


def _wav_bytes(
    *,
    sample_rate_hz: int = 22_050,
    frame_count: int = 2_205,
    channels: int = 1,
) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(2)
        recording.setframerate(sample_rate_hz)
        recording.writeframes(b"\0\0" * frame_count * channels)
    return output.getvalue()


def _capture_metadata(
    *,
    sample_rate_hz: int = 22_050,
    frame_count: int = 2_205,
) -> dict[str, Any]:
    return {
        "schema_version": BROWSER_CAPTURE_SCHEMA,
        "sample_rate_hz": sample_rate_hz,
        "frame_count": frame_count,
        "chunk_count": 2,
        "capture_elapsed_s": frame_count / sample_rate_hz,
        "started_at": "2026-07-24T12:00:00.000Z",
        "requested_constraints": {
            "channelCount": 1,
            "echoCancellation": False,
        },
    }


def _encoded_metadata(metadata: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(metadata).encode()).decode()


def _fake_transcriber(
    input_manifest: Path,
    run_directory: Path,
    *,
    command: list[str],
) -> dict[str, Any]:
    manifest = read_json(input_manifest)
    run_directory.mkdir(parents=True)
    shutil.copyfile(input_manifest.parent / manifest["audio"]["path"], run_directory / "input.wav")
    run = {
        "schema_version": "atpiano.run.v1",
        "run_id": run_directory.parent.name,
        "status": "complete",
        "started_at": "2026-07-24T12:00:01+00:00",
        "completed_at": "2026-07-24T12:00:02+00:00",
        "mode": "offline-reference",
        "command": command,
        "input": {
            "input_id": manifest["input_id"],
            "audio": "input.wav",
            "audio_sha256": manifest["audio"]["sha256"],
        },
        "model": {"package_version": "test", "adapter": "test"},
        "runtime": {},
    }
    documents = {
        "run.json": run,
        "scores.json": {
            "schema_version": "atpiano.scores.v1",
            "quality_available": False,
            "estimated_note_count": 0,
        },
        "reference.json": {"schema_version": "atpiano.note-set.v1", "notes": []},
        "prediction.json": {"schema_version": "atpiano.note-set.v1", "notes": []},
    }
    for name, value in documents.items():
        write_json(run_directory / name, value)
    (run_directory / "events.jsonl").write_text("", encoding="utf-8")
    return run


def test_browser_capture_writer_preserves_validated_pcm_wav(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(_wav_bytes())
    output = tmp_path / "input"

    manifest = write_browser_capture_artifacts(
        output,
        source,
        client_metadata=_capture_metadata(),
    )

    assert manifest["reference"] is None
    assert manifest["audio"]["sample_rate_hz"] == 22_050
    assert manifest["audio"]["frame_count"] == 2_205
    assert manifest["capture"]["adapter"] == "web-audio-worklet-file-v1"
    assert (output / "recording.wav").read_bytes() == source.read_bytes()
    capture = read_json(output / "browser-capture.json")
    assert capture["source_timeline"] == "AudioWorklet sample index"


def test_browser_capture_writer_rejects_metadata_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(_wav_bytes())
    metadata = _capture_metadata()
    metadata["frame_count"] += 1

    with pytest.raises(ValueError, match="frame count"):
        write_browser_capture_artifacts(
            tmp_path / "input",
            source,
            client_metadata=metadata,
        )


def test_workbench_upload_job_and_reloadable_artifacts(tmp_path: Path) -> None:
    server = create_workbench_server(tmp_path, port=0, transcriber=_fake_transcriber)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base_url}/api/config", timeout=2) as response:
            assert json.load(response)["mode"] == "workbench"
        foreign_host = urllib.request.Request(
            f"{base_url}/api/config",
            headers={"Host": "example.test"},
        )
        with pytest.raises(urllib.error.HTTPError) as host_error:
            urllib.request.urlopen(foreign_host, timeout=2)
        assert host_error.value.code == 403
        with urllib.request.urlopen(f"{base_url}/capture-processor.js", timeout=2) as response:
            assert b"registerProcessor" in response.read()

        invalid_request = urllib.request.Request(
            f"{base_url}/api/transcriptions",
            data=_wav_bytes(),
            method="POST",
            headers={"Content-Type": "audio/wav"},
        )
        with pytest.raises(urllib.error.HTTPError) as invalid_error:
            urllib.request.urlopen(invalid_request, timeout=2)
        assert invalid_error.value.code == 400

        request = urllib.request.Request(
            f"{base_url}/api/transcriptions",
            data=_wav_bytes(),
            method="POST",
            headers={
                "Content-Type": "audio/wav",
                "X-Atpiano-Capture-Metadata": _encoded_metadata(_capture_metadata()),
            },
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 202
            job = json.load(response)
        job_id = job["job_id"]
        for _ in range(40):
            with urllib.request.urlopen(
                f"{base_url}/api/jobs/{job_id}",
                timeout=2,
            ) as response:
                job = json.load(response)
            if job["status"] == "complete":
                break
            time.sleep(0.05)
        assert job["status"] == "complete"
        assert job["run_url"] == f"/?run={job_id}"

        artifact_url = f"{base_url}/api/runs/{job_id}/artifacts/run.json"
        with urllib.request.urlopen(artifact_url, timeout=2) as response:
            assert json.load(response)["run_id"] == job_id
        with pytest.raises(urllib.error.HTTPError) as traversal_error:
            urllib.request.urlopen(
                f"{base_url}/api/runs/{job_id}/artifacts/%2e%2e/input/input.json",
                timeout=2,
            )
        assert traversal_error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    restarted = create_workbench_server(tmp_path, port=0, transcriber=_fake_transcriber)
    restarted_thread = threading.Thread(target=restarted.serve_forever, daemon=True)
    restarted_thread.start()
    restarted_url = f"http://127.0.0.1:{restarted.server_address[1]}"
    try:
        with urllib.request.urlopen(
            f"{restarted_url}/api/jobs/{job_id}",
            timeout=2,
        ) as response:
            assert json.load(response)["status"] == "complete"
    finally:
        restarted.shutdown()
        restarted.server_close()
        restarted_thread.join(timeout=2)
