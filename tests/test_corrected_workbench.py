from __future__ import annotations

import json
import re
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from atpiano.cli import build_parser
from atpiano.corrected_commit import CommitModelOutput
from atpiano.corrected_workbench import (
    CORRECTED_STREAM_SCHEMA,
    create_corrected_workbench_server,
)
from atpiano.fixture import generate_fixture
from atpiano.live import LiveModelOutput, PcmBlock, pack_pcm_block


class _FakePreviewModel:
    sample_rate_hz = 8_000
    window_samples = 100
    fft_hop_samples = 1
    overlapping_frames = 0
    left_guard_samples = 0
    right_guard_samples = 0

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        return LiveModelOutput(
            candidates=[],
            raw={"onset": np.zeros((1, 88), dtype=np.float32)},
            inference_s=0.0,
            decode_s=0.0,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "fake-preview"}


class _FakeCommitModel:
    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        return CommitModelOutput(
            events=(),
            inference_s=0.0,
            source_frame_count=len(pcm_s16le) // 2,
            model_frame_count=len(pcm_s16le) // 2,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "fake-commit"}


def _client_frame(payload: bytes, *, opcode: int) -> bytes:
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


def _server_frame(stream: Any) -> tuple[int, bytes]:
    prefix = stream.read(2)
    assert len(prefix) == 2
    first, second = prefix
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", stream.read(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", stream.read(8))[0]
    return first & 0x0F, stream.read(length)


def _send_json(connection: socket.socket, value: dict[str, Any]) -> None:
    connection.sendall(
        _client_frame(json.dumps(value).encode("utf-8"), opcode=0x1)
    )


def test_corrected_workbench_is_separate_loopback_app(tmp_path: Path) -> None:
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base_url}/api/config", timeout=2) as response:
            config = json.load(response)
        assert config["mode"] == "corrected-workbench-v2"
        assert config["stream_schema"] == CORRECTED_STREAM_SCHEMA
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            page = response.read()
        assert b"Corrected notes" in page
        assert b"notation" not in page.lower()
        html = page.decode("utf-8")
        app = (Path(__file__).parents[1] / "src/atpiano/web_v2/app.js").read_text(
            encoding="utf-8"
        )
        requested_ids = set(re.findall(r'el\("([^"]+)"\)', app))
        assert requested_ids
        assert all(f'id="{requested_id}"' in html for requested_id in requested_ids)
        foreign = urllib.request.Request(
            f"{base_url}/api/session",
            headers={"Host": "example.test"},
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(foreign, timeout=2)
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_corrected_workbench_cli_keeps_v1_command_separate() -> None:
    parser = build_parser()

    v1 = parser.parse_args(["workbench", "--port", "8100"])
    v2 = parser.parse_args(
        [
            "workbench-v2",
            "--port",
            "8101",
            "--repeat",
            "3",
            "--silence-seconds",
            "1.5",
            "--no-wait",
        ]
    )

    assert v1.command == "workbench"
    assert v1.port == 8100
    assert not hasattr(v1, "repeat")
    assert v2.command == "workbench-v2"
    assert v2.port == 8101
    assert v2.repeat == 3
    assert v2.silence_seconds == 1.5
    assert v2.no_wait is True


def test_microphone_websocket_uses_corrected_session_and_exports(
    tmp_path: Path,
) -> None:
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
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
        _send_json(
            connection,
            {
                "schema_version": CORRECTED_STREAM_SCHEMA,
                "type": "start",
                "sample_rate_hz": 8_000,
                "client_metadata": {"capture": "unit-test"},
            },
        )
        _, payload = _server_frame(stream)
        ready = json.loads(payload)
        assert ready["type"] == "ready"
        assert [lane["name"] for lane in ready["lanes"]] == ["preview", "commit"]

        pcm = struct.pack("<6h", -32768, -2, -1, 0, 1, 32767)
        block = PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=6,
            sample_rate_hz=8_000,
            page_sent_ms=1.0,
            worklet_time_s=6 / 8_000,
            pcm_s16le=pcm,
        )
        connection.sendall(_client_frame(pack_pcm_block(block), opcode=0x2))
        _, payload = _server_frame(stream)
        acknowledgement = json.loads(payload)
        assert acknowledgement["type"] == "block_ack"
        assert acknowledgement["received_source_frames"] == 6

        _send_json(
            connection,
            {
                "schema_version": CORRECTED_STREAM_SCHEMA,
                "type": "stop",
                "frame_count": 6,
                "block_count": 1,
            },
        )
        _, payload = _server_frame(stream)
        stopped = json.loads(payload)
        assert stopped["type"] == "stopped"
        assert stopped["session"]["source"] == "microphone"
        assert stopped["session"]["source_frame_count"] == 6
        assert stopped["exports"]["midi"]["note_count"] == 0

        base_url = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base_url}/api/session", timeout=2) as response:
            status = json.load(response)
        assert status["status"] == "complete"
        assert status["exports_ready"] is True
        with urllib.request.urlopen(
            f"{base_url}/api/events?start_sample=0&end_sample=6&after=0",
            timeout=2,
        ) as response:
            events = json.load(response)
        assert events["materialized"] == []
        with urllib.request.urlopen(
            f"{base_url}/api/artifacts/exports/session.mid",
            timeout=2,
        ) as response:
            assert response.read(4) == b"MThd"
    finally:
        stream.close()
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_server_driven_replay_uses_same_review_and_export_surface(
    tmp_path: Path,
) -> None:
    fixture_directory = tmp_path / "fixture"
    fixture = generate_fixture(fixture_directory)
    server = create_corrected_workbench_server(
        tmp_path / "workspace",
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        replay_manifest=fixture_directory / "input.json",
        replay_repeat=2,
        replay_realtime=False,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        server.start_replay()
        for _ in range(100):
            with urllib.request.urlopen(f"{base_url}/api/session", timeout=2) as response:
                status = json.load(response)
            if status["status"] in {"complete", "failed"}:
                break
            time.sleep(0.05)
        assert status["status"] == "complete", status.get("error")
        assert status["session"]["source"] == "replay"
        assert status["session"]["source_frame_count"] == (
            fixture["audio"]["frame_count"] * 2
        )
        assert status["exports_ready"] is True
        session_directory = server.current_directory()
        assert session_directory is not None
        boundaries = (
            (session_directory / "boundaries.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert len(boundaries) == 2
        sample_rate_hz = status["session"]["sample_rate_hz"]
        start_sample = max(
            0,
            status["session"]["source_frame_count"] - sample_rate_hz,
        )
        with urllib.request.urlopen(
            f"{base_url}/api/events?start_sample={start_sample}"
            f"&end_sample={status['session']['source_frame_count']}&after=0",
            timeout=2,
        ) as response:
            events = json.load(response)
        assert events["range"]["start_sample"] == start_sample
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
