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

import atpiano.corrected_workbench as corrected_workbench_module
from atpiano.cli import build_parser
from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.corrected_commit import CommitModelOutput
from atpiano.corrected_workbench import (
    CORRECTED_STREAM_SCHEMA,
    create_corrected_workbench_server,
)
from atpiano.fixture import generate_fixture
from atpiano.live import LiveModelOutput, PcmBlock, pack_pcm_block
from atpiano.util import read_json, sha256_file, write_json


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


class _BlockingCommitModel(_FakeCommitModel):
    started = threading.Event()
    release = threading.Event()

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        self.started.set()
        if not self.release.wait(2):
            raise TimeoutError("blocking commit model was not released")
        return super().transcribe(
            pcm_s16le,
            source_sample_rate_hz=source_sample_rate_hz,
        )


class _ExitedCommitModel(_FakeCommitModel):
    def __init__(self) -> None:
        self.closed = False

    def status(self) -> dict[str, object]:
        return {"alive": False}

    def close(self) -> None:
        self.closed = True


def _fake_score_runner(
    input_midi: Path,
    input_notes: Path,
    output_musicxml: Path,
    output_alignment: Path,
    runtime_directory: Path,
) -> dict[str, Any]:
    assert input_midi.is_file()
    source = json.loads(input_notes.read_text(encoding="utf-8"))
    output_musicxml.write_text(
        """<score-partwise version="4.0">
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1"><note id="test-note-1"><pitch><step>C</step>
<octave>4</octave></pitch><duration>1</duration></note></measure></part>
</score-partwise>
""",
        encoding="utf-8",
    )
    note = source["notes"][0]
    segment = {
        "musicxml_note_id": "test-note-1",
        "part": 1,
        "pitch": note["pitch"],
        "score_time_quarters": {"numerator": 0, "denominator": 1},
        "score_duration_quarters": {"numerator": 1, "denominator": 1},
        "tie": None,
    }
    write_json(
        output_alignment,
        {
            "schema_version": "atpiano.score-alignment.v2",
            "session_id": source["session_id"],
            "sample_rate_hz": source["sample_rate_hz"],
            "source": {
                "schema_version": source["schema_version"],
                "sha256": sha256_file(input_notes),
            },
            "musicxml": {"sha256": sha256_file(output_musicxml)},
            "mapping": {
                "algorithm": "monotonic-exact-pitch-lcs-v1",
                "source_order": "onset-sample,pitch,duration,source-index",
                "score_order": "attack-quarters,pitch,output-index",
            },
            "summary": {
                "source_notes": 1,
                "mapped_source_notes": 1,
                "unmatched_source_notes": 0,
                "musicxml_note_elements": 1,
                "inserted_score_note_elements": 0,
            },
            "rows": [
                {
                    "source_index": 0,
                    "event_id": note["event_id"],
                    "pitch": note["pitch"],
                    "onset_sample": note["onset_sample"],
                    "offset_sample": note["offset_sample"],
                    "status": "mapped",
                    "score_time_quarters": {
                        "numerator": 0,
                        "denominator": 1,
                    },
                    "segments": [segment],
                }
            ],
            "inserted_score_segments": [],
        },
    )
    return {
        "schema_version": "test-score-runner.v1",
        "runtime_directory": str(runtime_directory),
    }


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
    connection.sendall(_client_frame(json.dumps(value).encode("utf-8"), opcode=0x1))


def test_corrected_workbench_is_separate_loopback_app(tmp_path: Path) -> None:
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
        correction_mode="delayed",
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
        assert b"Committed score" in page
        range_request = urllib.request.Request(
            f"{base_url}/",
            headers={"Range": "bytes=5-14"},
        )
        with urllib.request.urlopen(range_request, timeout=2) as response:
            assert response.status == 206
            assert response.headers["Accept-Ranges"] == "bytes"
            assert response.headers["Content-Range"] == f"bytes 5-14/{len(page)}"
            assert response.read() == page[5:15]
        html = page.decode("utf-8")
        app = (Path(__file__).parents[1] / "src/atpiano/web_v2/app.js").read_text(encoding="utf-8")
        styles = (Path(__file__).parents[1] / "src/atpiano/web_v2/styles.css").read_text(
            encoding="utf-8"
        )
        requested_ids = set(re.findall(r'el\("([^"]+)"\)', app))
        assert requested_ids
        assert all(f'id="{requested_id}"' in html for requested_id in requested_ids)
        assert ".timeline-empty[hidden]" in styles
        assert "#score-view[hidden]" in styles
        assert "include_history=0" in app
        assert 'fetchJson("/api/score"' in app
        assert "opensheetmusicdisplay@1.9.9" in html
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


def test_corrected_workbench_accepts_one_configured_public_origin(
    tmp_path: Path,
) -> None:
    public_origin = "https://atpiano.kzahel.com"
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
        public_origin=public_origin,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        trusted = urllib.request.Request(
            f"{base_url}/api/config",
            headers={"Host": "atpiano.kzahel.com"},
        )
        with urllib.request.urlopen(trusted, timeout=2) as response:
            assert response.status == 200

        action = urllib.request.Request(
            f"{base_url}/api/replay",
            data=b"",
            headers={
                "Host": "atpiano.kzahel.com",
                "Origin": public_origin,
            },
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(action, timeout=2)
        assert error.value.code == 409

        foreign = urllib.request.Request(
            f"{base_url}/api/replay",
            data=b"",
            headers={
                "Host": "atpiano.kzahel.com",
                "Origin": "https://other.example",
            },
            method="POST",
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
    v3 = parser.parse_args(
        [
            "workbench-v3",
            "--port",
            "8102",
            "--repeat",
            "2",
            "--no-wait",
            "--public-origin",
            "https://atpiano.kzahel.com",
        ]
    )
    profile = parser.parse_args(
        [
            "profile-backend",
            "fixture/input.json",
            "results/backend-profile",
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
    assert v2.commit_threads == 2
    assert v2.correction_mode == "auto"
    assert v2.backend_profile == Path(
        "results/backend-profile/backend-profile.json"
    )
    assert v3.command == "workbench-v3"
    assert v3.bind == "127.0.0.1"
    assert v3.port == 8102
    assert v3.repeat == 2
    assert v3.workspace == Path("results/workbench-v3")
    assert v3.commit_threads == 2
    assert v3.correction_mode == "auto"
    assert v3.public_origin == "https://atpiano.kzahel.com"
    assert profile.repeat == 2
    assert profile.warmup_seconds == 16.0
    assert profile.commit_threads == 2


def test_corrected_workbench_marks_interrupted_settlement_recoverable(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="20260726T000000-abcdef123456",
        sample_rate_hz=8_000,
        source="microphone",
        minimum_free_bytes=0,
    )
    session.accept_pcm(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=4,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0,
            pcm_s16le=bytes(8),
        ),
        received_ns=1,
    )
    session.begin_settling()
    session.events.close()
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
    )
    try:
        state = server.public_state()
        manifest = read_json(session.directory / "session.json")
    finally:
        server.server_close()

    assert state["status"] == "failed"
    assert "Accepted audio is preserved" in state["error"]
    assert manifest["status"] == "failed"
    assert manifest["source_frame_count"] == 4
    assert "settlement" in manifest["processing"]["stage_errors"]


def test_corrected_workbench_replaces_an_exited_model_before_next_session(
    tmp_path: Path,
) -> None:
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
    )
    exited = _ExitedCommitModel()
    server._commit_model = exited
    try:
        replacement = server.get_commit_model()
    finally:
        server.server_close()

    assert exited.closed
    assert isinstance(replacement, _FakeCommitModel)
    assert replacement is not exited


def test_corrected_workbench_can_serve_the_shared_app_shell(
    tmp_path: Path,
) -> None:
    web_root = tmp_path / "dist"
    assets = web_root / "assets"
    assets.mkdir(parents=True)
    (web_root / "index.html").write_text(
        "<!doctype html><title>Atpiano performance workspace</title>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("globalThis.atpianoV3 = true;\n", encoding="utf-8")
    server = create_corrected_workbench_server(
        tmp_path / "workspace",
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
        correction_mode="delayed",
        web_root=web_root,
        application_mode="shared-react-v3",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            page = response.read()
        with urllib.request.urlopen(
            f"{base_url}/assets/app.js",
            timeout=2,
        ) as response:
            script = response.read()
        with urllib.request.urlopen(
            f"{base_url}/api/config",
            timeout=2,
        ) as response:
            config = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert b"Atpiano performance workspace" in page
    assert b"atpianoV3" in script
    assert config["mode"] == "shared-react-v3"


def test_corrected_workbench_generates_committed_score_in_background(
    tmp_path: Path,
) -> None:
    session_id = "20260726T000000-abcdef123456"
    session = CorrectedSession(
        tmp_path / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        minimum_free_bytes=0,
    )
    pcm = np.zeros(800, dtype="<i2").tobytes()
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=800,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.1,
            pcm_s16le=pcm,
        ),
        received_ns=1,
    )
    session.append_events(
        [
            {
                "schema_version": CORRECTED_EVENT_SCHEMA,
                "session_id": session_id,
                "event_id": "committed-c4",
                "revision": 1,
                "lane": "commit",
                "lifecycle": "committed",
                "pitch": 60,
                "onset_sample": 100,
                "offset_sample": 400,
                "offset_state": "closed",
                "velocity": 80,
                "confidence": 0.9,
            }
        ]
    )
    session.advance_provisional(600)
    session.advance_commit(500)
    session.finalize()

    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
        correction_mode="delayed",
        score_runtime=tmp_path / "runtime",
        score_runner=_fake_score_runner,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = urllib.request.Request(
            f"{base_url}/api/score",
            data=b"",
            headers={"Origin": base_url},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 202
        deadline = time.monotonic() + 2
        score: dict[str, Any] = {}
        while time.monotonic() < deadline:
            with urllib.request.urlopen(
                f"{base_url}/api/score",
                timeout=2,
            ) as response:
                score = json.load(response)
            if score["status"] != "running":
                break
            time.sleep(0.01)
        assert score["status"] == "complete"
        assert score["snapshot"]["commit_sample"] == 500
        assert score["snapshot"]["note_count"] == 1
        assert score["stale"] is False
        with urllib.request.urlopen(
            f"{base_url}/api/artifacts/score/current.musicxml",
            timeout=2,
        ) as response:
            assert b"score-partwise" in response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_microphone_websocket_uses_corrected_session_and_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_FakeCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
        correction_mode="delayed",
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
        assert ready["correction"]["mode"] == "delayed"
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
                "transport": {
                    "sent_frame_count": 6,
                    "sent_block_count": 1,
                    "acknowledged_frame_count": 6,
                    "acknowledged_block_count": 1,
                    "socket_buffered_bytes_at_stop": 0,
                    "socket_buffered_bytes_high_water": 128,
                },
            },
        )
        _, payload = _server_frame(stream)
        stopped = json.loads(payload)
        assert stopped["type"] == "stopped"
        assert stopped["settling"] is True
        assert stopped["session"]["status"] == "stopping"
        assert stopped["session"]["source"] == "microphone"
        assert stopped["session"]["source_frame_count"] == 6
        assert stopped["exports"] == {}
        session_directory = server.current_directory()
        assert session_directory is not None
        transport = read_json(session_directory / "transport.json")
        assert transport["socket_buffered_bytes_high_water"] == 128

        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 2
        status: dict[str, Any] = {}
        while time.monotonic() < deadline:
            with urllib.request.urlopen(
                f"{base_url}/api/session",
                timeout=2,
            ) as response:
                status = json.load(response)
            if status["status"] == "complete":
                break
            time.sleep(0.01)
        assert status["status"] == "complete"
        assert status["exports_ready"] is True
        with urllib.request.urlopen(
            f"{base_url}/api/events?start_sample=0&end_sample=6&after=0",
            timeout=2,
        ) as response:
            events = json.load(response)
        assert events["materialized"] == []
        monkeypatch.setattr(
            corrected_workbench_module,
            "query_history_index",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("history query should be skipped")
            ),
        )
        with urllib.request.urlopen(
            f"{base_url}/api/events?start_sample=0&end_sample=6&include_history=0",
            timeout=2,
        ) as response:
            visible_only = json.load(response)
        assert visible_only["materialized"] == []
        assert visible_only["history"] == []
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


def test_microphone_acknowledges_pcm_while_commit_lane_is_blocked(
    tmp_path: Path,
) -> None:
    _BlockingCommitModel.started.clear()
    _BlockingCommitModel.release.clear()
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        preview_model_factory=_FakePreviewModel,
        commit_model_factory=_BlockingCommitModel,
        minimum_free_bytes=0,
        isolate_models=False,
        correction_mode="delayed",
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
                "client_metadata": {"capture": "blocked-commit-test"},
            },
        )
        _, payload = _server_frame(stream)
        assert json.loads(payload)["type"] == "ready"

        first_frames = 16 * 8_000
        block_frames = 16_000
        for sequence in range(first_frames // block_frames):
            first_sample = sequence * block_frames
            block = PcmBlock(
                sequence=sequence,
                first_sample=first_sample,
                frame_count=block_frames,
                sample_rate_hz=8_000,
                page_sent_ms=1.0,
                worklet_time_s=(first_sample + block_frames) / 8_000,
                pcm_s16le=bytes(block_frames * 2),
            )
            connection.sendall(
                _client_frame(pack_pcm_block(block), opcode=0x2)
            )
            _, payload = _server_frame(stream)
            assert (
                json.loads(payload)["received_source_frames"]
                == first_sample + block_frames
            )
        assert _BlockingCommitModel.started.wait(1)

        second = PcmBlock(
            sequence=8,
            first_sample=first_frames,
            frame_count=8,
            sample_rate_hz=8_000,
            page_sent_ms=2.0,
            worklet_time_s=16.001,
            pcm_s16le=bytes(16),
        )
        connection.sendall(_client_frame(pack_pcm_block(second), opcode=0x2))
        connection.settimeout(0.5)
        _, payload = _server_frame(stream)
        acknowledgement = json.loads(payload)
        assert acknowledgement["type"] == "block_ack"
        assert acknowledgement["received_source_frames"] == first_frames + 8

        _BlockingCommitModel.release.set()
        _send_json(
            connection,
            {
                "schema_version": CORRECTED_STREAM_SCHEMA,
                "type": "stop",
                "frame_count": first_frames + 8,
                "block_count": 9,
            },
        )
        _, payload = _server_frame(stream)
        assert json.loads(payload)["session"]["status"] == "stopping"
    finally:
        _BlockingCommitModel.release.set()
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
        isolate_models=False,
        correction_mode="delayed",
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
        assert status["session"]["source_frame_count"] == (fixture["audio"]["frame_count"] * 2)
        assert status["exports_ready"] is True
        session_directory = server.current_directory()
        assert session_directory is not None
        boundaries = (
            (session_directory / "boundaries.jsonl").read_text(encoding="utf-8").splitlines()
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
