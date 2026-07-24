from __future__ import annotations

import base64
import io
import json
import shutil
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from atpiano.capture import BROWSER_CAPTURE_SCHEMA, write_browser_capture_artifacts
from atpiano.live import (
    LIVE_STREAM_SCHEMA,
    LiveModelOutput,
    PcmBlock,
    pack_pcm_block,
)
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


def _client_websocket_frame(payload: bytes, *, opcode: int) -> bytes:
    mask = b"\x11\x22\x33\x44"
    length = len(payload)
    first = 0x80 | opcode
    if length < 126:
        prefix = bytes((first, 0x80 | length))
    elif length <= 0xFFFF:
        prefix = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
    else:
        prefix = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    return prefix + mask + masked


def _server_websocket_frame(stream: Any) -> tuple[int, bytes]:
    prefix = stream.read(2)
    assert len(prefix) == 2
    first, second = prefix
    assert first & 0x80
    assert not second & 0x80
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", stream.read(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", stream.read(8))[0]
    return first & 0x0F, stream.read(length)


def _send_live_json(connection: socket.socket, value: dict[str, Any]) -> None:
    connection.sendall(
        _client_websocket_frame(json.dumps(value).encode(), opcode=0x1)
    )


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
        "run_id": run_directory.name,
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
            "estimated_note_count": 1,
        },
        "reference.json": {"schema_version": "atpiano.note-set.v1", "notes": []},
        "prediction.json": {
            "schema_version": "atpiano.note-set.v1",
            "notes": [
                {
                    "onset_s": 0.0,
                    "offset_s": 0.5,
                    "pitch": 60,
                    "velocity": 80,
                }
            ],
        },
    }
    for name, value in documents.items():
        write_json(run_directory / name, value)
    (run_directory / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "fake-event",
                "lifecycle": "committed",
                "pitch": 60,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return run


class _FakeLiveModel:
    sample_rate_hz = 22_050
    window_samples = 8
    fft_hop_samples = 1
    overlapping_frames = 4
    left_guard_samples = 1
    right_guard_samples = 3

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        return LiveModelOutput(
            candidates=[],
            raw={"onset": np.zeros((1, 88), dtype=np.float32)},
            inference_s=0.001,
            decode_s=0.001,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "test-live-model"}


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
            assert json.load(response)["run_id"] == f"run-{job_id}"
        with urllib.request.urlopen(
            f"{base_url}/api/runs/{job_id}/notation",
            timeout=2,
        ) as response:
            notation = json.load(response)
        assert notation["selected"]["meter_numerator"] == 4
        notation_request = urllib.request.Request(
            f"{base_url}/api/runs/{job_id}/notation",
            data=json.dumps({"tempo_bpm": 90, "key": "G"}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(notation_request, timeout=2) as response:
            notation = json.load(response)
        assert notation["selected"]["tempo_bpm"] == 90
        assert notation["selected"]["key"] == "G"
        with urllib.request.urlopen(
            f"{base_url}/api/runs/{job_id}/artifacts/"
            f"{notation['artifacts']['musicxml']}",
            timeout=2,
        ) as response:
            assert b"<score-partwise" in response.read()

        oracle_musicxml = b"""<score-partwise version="4.0">
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1"><note><rest/><duration>1</duration></note>
</measure></part></score-partwise>"""
        oracle_request = urllib.request.Request(
            f"{base_url}/api/runs/{job_id}/oracle/audio",
            data=oracle_musicxml,
            method="POST",
            headers={
                "Content-Type": "application/vnd.recordare.musicxml+xml",
                "X-Atpiano-Filename": "ivory-audio.musicxml",
            },
        )
        with urllib.request.urlopen(oracle_request, timeout=2) as response:
            oracle = json.load(response)
        assert oracle["lanes"]["audio"]["original_filename"] == (
            "ivory-audio.musicxml"
        )
        with urllib.request.urlopen(
            f"{base_url}/api/runs/{job_id}/oracle",
            timeout=2,
        ) as response:
            assert "audio" in json.load(response)["lanes"]
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


def test_workbench_live_websocket_preserves_sample_stream(tmp_path: Path) -> None:
    server = create_workbench_server(
        tmp_path,
        port=0,
        transcriber=_fake_transcriber,
        live_model_factory=_FakeLiveModel,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    connection = socket.create_connection(("127.0.0.1", port), timeout=2)
    stream = connection.makefile("rb")
    try:
        request = (
            "GET /api/live HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Origin: http://127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "\r\n"
        )
        connection.sendall(request.encode("ascii"))
        assert stream.readline().startswith(b"HTTP/1.0 101")
        while stream.readline() not in {b"\r\n", b""}:
            pass

        _send_live_json(
            connection,
            {
                "schema_version": LIVE_STREAM_SCHEMA,
                "type": "start",
                "sample_rate_hz": 22_050,
                "client_metadata": {
                    "schema_version": BROWSER_CAPTURE_SCHEMA,
                    "started_at": "2026-07-24T12:00:00.000Z",
                    "requested_constraints": {"echoCancellation": False},
                },
            },
        )
        opcode, payload = _server_websocket_frame(stream)
        ready = json.loads(payload)
        assert opcode == 0x1
        assert ready["type"] == "ready"
        job_id = ready["job_id"]

        pcm = struct.pack("<6h", -32768, -2, -1, 0, 1, 32767)
        blocks = (
            PcmBlock(0, 0, 3, 22_050, 1.0, 0.0, pcm[:6]),
            PcmBlock(1, 3, 3, 22_050, 2.0, 3 / 22_050, pcm[6:]),
        )
        for block in blocks:
            connection.sendall(
                _client_websocket_frame(pack_pcm_block(block), opcode=0x2)
            )
            _, payload = _server_websocket_frame(stream)
            acknowledgement = json.loads(payload)
            assert acknowledgement["type"] == "block_ack"
            if acknowledgement["window_count"]:
                _, payload = _server_websocket_frame(stream)
                assert json.loads(payload)["type"] == "events"

        _send_live_json(
            connection,
            {
                "schema_version": LIVE_STREAM_SCHEMA,
                "type": "stop",
                "frame_count": 6,
                "block_count": 2,
                "capture_elapsed_s": 6 / 22_050,
            },
        )
        _, payload = _server_websocket_frame(stream)
        assert json.loads(payload)["type"] == "stopped"

        base_url = f"http://127.0.0.1:{port}"
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
        input_directory = tmp_path / job_id / "input"
        with wave.open(str(input_directory / "recording.wav"), "rb") as recording:
            assert recording.getnframes() == 6
            assert recording.readframes(6) == pcm
        manifest = read_json(input_directory / "input.json")
        assert manifest["capture"]["adapter"] == "web-audio-worklet-live-v1"
        assert manifest["capture"]["block_count"] == 2
    finally:
        stream.close()
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
