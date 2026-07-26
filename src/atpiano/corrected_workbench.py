"""Loopback-only web application for bounded corrected-note sessions."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import sqlite3
import threading
import time
import uuid
import webbrowser
from collections.abc import Callable
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from atpiano.corrected import (
    CorrectedSession,
    run_corrected_replay,
)
from atpiano.corrected_commit import CommitModel, CorrectedCommitLane
from atpiano.corrected_export import (
    MAX_QUERY_LIMIT,
    ensure_materialized_index,
    query_history_index,
    query_materialized_index,
    write_corrected_exports,
)
from atpiano.corrected_preview import CorrectedPreviewLane
from atpiano.live import LiveWindowModel, parse_pcm_block
from atpiano.util import read_json, utc_now, write_json
from atpiano.websocket import encode_frame, encode_json, read_frame, websocket_accept

CORRECTED_WORKBENCH_SCHEMA = "atpiano.corrected-workbench.v1"
CORRECTED_STREAM_SCHEMA = "atpiano.corrected-stream.v1"
MAX_CLIENT_METADATA_BYTES = 16 * 1024
MAX_VISIBLE_RANGE_S = 120.0
DEFAULT_MINIMUM_FREE_BYTES = 2 * 1024**3
WEB_ROOT = Path(__file__).with_name("web_v2")
ASSETS = {
    "/": WEB_ROOT / "index.html",
    "/index.html": WEB_ROOT / "index.html",
    "/app.js": WEB_ROOT / "app.js",
    "/capture-processor.js": WEB_ROOT / "capture-processor.js",
    "/timeline.js": WEB_ROOT / "timeline.js",
    "/styles.css": WEB_ROOT / "styles.css",
}
EXPORT_ASSETS = {
    "/api/artifacts/exports/session.mid": "session.mid",
    "/api/artifacts/exports/session.jsonl": "session.jsonl",
    "/api/artifacts/exports/manifest.json": "manifest.json",
}
SESSION_ID_PATTERN = re.compile(r"\d{8}T\d{6}-[0-9a-f]{12}")

PreviewModelFactory = Callable[[], LiveWindowModel]
CommitModelFactory = Callable[[], CommitModel]


def _new_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def _default_preview_model() -> LiveWindowModel:
    from atpiano.live import BasicPitchLiveModel

    return BasicPitchLiveModel()


def _default_commit_model(*, device: str) -> CommitModel:
    from atpiano.corrected_commit import TranskunCommitModel

    return TranskunCommitModel(device=device)


class CorrectedWorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        workspace_directory: Path,
        *,
        port: int,
        preview_model_factory: PreviewModelFactory = _default_preview_model,
        commit_model_factory: CommitModelFactory,
        minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
        replay_manifest: Path | None = None,
        replay_repeat: int = 1,
        replay_realtime: bool = True,
    ) -> None:
        if minimum_free_bytes < 0:
            raise ValueError("minimum free bytes cannot be negative")
        if replay_repeat <= 0:
            raise ValueError("replay repetition count must be positive")
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        self.preview_model_factory = preview_model_factory
        self.commit_model_factory = commit_model_factory
        self.minimum_free_bytes = minimum_free_bytes
        self.replay_manifest = replay_manifest.resolve() if replay_manifest else None
        self.replay_repeat = replay_repeat
        self.replay_realtime = replay_realtime
        self.state_lock = threading.Lock()
        self.model_lock = threading.Lock()
        self._preview_model: LiveWindowModel | None = None
        self._commit_model: CommitModel | None = None
        self._active_session: CorrectedSession | None = None
        self._session_id: str | None = None
        self._session_directory: Path | None = None
        self._status = "idle"
        self._error: str | None = None
        self._received_blocks = 0
        self._last_event_sequence = 0
        self._load_latest_session()
        super().__init__(("127.0.0.1", port), CorrectedWorkbenchHandler)

    def _load_latest_session(self) -> None:
        manifests = sorted(
            self.workspace_directory.glob("*/session.json"),
            key=lambda path: path.stat().st_mtime_ns,
        )
        if not manifests:
            return
        latest_path = manifests[-1]
        try:
            latest = read_json(latest_path)
        except (OSError, ValueError):
            return
        session_id = str(latest.get("session_id", ""))
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            return
        try:
            ensure_materialized_index(latest_path.parent / "event-index.sqlite3")
        except (FileNotFoundError, sqlite3.Error):
            return
        self._session_id = session_id
        self._session_directory = latest_path.parent
        persisted_status = str(latest.get("status", "failed"))
        if persisted_status == "active":
            self._status = "failed"
            self._error = "The prior process ended before this session stopped."
        else:
            self._status = persisted_status
            self._error = latest.get("error")

    def get_models(self) -> tuple[LiveWindowModel, CommitModel]:
        with self.model_lock:
            if self._preview_model is None:
                self._preview_model = self.preview_model_factory()
            if self._commit_model is None:
                self._commit_model = self.commit_model_factory()
            return self._preview_model, self._commit_model

    def claim_session(self, *, source: str) -> tuple[str, Path]:
        with self.state_lock:
            if self._active_session is not None or self._status in {
                "warming",
                "active",
                "stopping",
            }:
                raise RuntimeError("another corrected session is already active")
            session_id = _new_session_id()
            directory = self.workspace_directory / session_id
            self._session_id = session_id
            self._session_directory = directory
            self._status = "warming"
            self._error = None
            self._received_blocks = 0
            self._last_event_sequence = 0
            return session_id, directory

    def set_active(self, session: CorrectedSession) -> None:
        with self.state_lock:
            if session.session_id != self._session_id:
                raise RuntimeError("corrected session claim changed during startup")
            self._active_session = session
            self._status = "active"

    def record_delivery(self, events: list[dict[str, Any]]) -> None:
        with self.state_lock:
            self._received_blocks += 1
            if events:
                self._last_event_sequence = max(
                    self._last_event_sequence,
                    max(int(event["sequence"]) for event in events),
                )

    def complete_session(self) -> None:
        with self.state_lock:
            self._active_session = None
            self._status = "complete"
            self._error = None

    def fail_session(self, error: Exception) -> None:
        with self.state_lock:
            self._active_session = None
            self._status = "failed"
            self._error = f"{type(error).__name__}: {error}"

    def begin_stop(self) -> None:
        with self.state_lock:
            self._status = "stopping"

    def current_directory(self) -> Path | None:
        with self.state_lock:
            return self._session_directory

    def public_state(self) -> dict[str, Any]:
        with self.state_lock:
            status = self._status
            error = self._error
            session_id = self._session_id
            directory = self._session_directory
            active = self._active_session
            received_blocks = self._received_blocks
            last_event_sequence = self._last_event_sequence
        session: dict[str, Any] | None = None
        horizons: dict[str, Any] | None = None
        lanes: list[dict[str, Any]] = []
        if active is not None:
            horizons = active.horizons.document(
                sample_rate_hz=active.sample_rate_hz
            )
            session = {
                "session_id": active.session_id,
                "status": status,
                "source": active.source,
                "realtime": active.realtime,
                "sample_rate_hz": active.sample_rate_hz,
                "source_frame_count": active.horizons.audio_head_sample,
                "started_at": active.started_at,
            }
            lanes = [lane.status() for lane in active.lanes]
            minimum_free_bytes = active.audio.minimum_free_bytes
        elif directory is not None and (directory / "session.json").is_file():
            try:
                session = read_json(directory / "session.json")
                horizon_path = directory / "horizons.json"
                horizons = read_json(horizon_path) if horizon_path.is_file() else None
                lanes = list(session.get("lanes", []))
                minimum_free_bytes = int(
                    session.get("retention", {}).get("minimum_free_bytes", 0)
                )
            except (OSError, TypeError, ValueError):
                session = None
                minimum_free_bytes = self.minimum_free_bytes
        else:
            minimum_free_bytes = self.minimum_free_bytes
        usage = shutil.disk_usage(self.workspace_directory)
        audio_frames = (
            int(horizons["audio_head_sample"])
            if horizons is not None
            else int((session or {}).get("source_frame_count", 0))
        )
        sample_rate_hz = int((session or {}).get("sample_rate_hz", 0))
        return {
            "schema_version": CORRECTED_WORKBENCH_SCHEMA,
            "status": status,
            "error": error,
            "session_id": session_id,
            "session": session,
            "horizons": horizons,
            "lanes": lanes,
            "storage": {
                "audio_pcm_bytes": audio_frames * 2,
                "free_bytes": usage.free,
                "minimum_free_bytes": minimum_free_bytes,
                "warning": usage.free < minimum_free_bytes * 5 // 4,
            },
            "transport": {
                "received_blocks": received_blocks,
                "last_event_sequence": last_event_sequence,
                "recovery": "bounded indexed sequence query",
            },
            "duration_s": (
                audio_frames / sample_rate_hz if sample_rate_hz else 0.0
            ),
            "exports_ready": bool(
                directory is not None
                and (directory / "exports" / "manifest.json").is_file()
            ),
        }

    def start_replay(self) -> None:
        if self.replay_manifest is None:
            raise ValueError("no replay manifest was configured")
        session_id, directory = self.claim_session(source="replay")
        thread = threading.Thread(
            target=self._run_replay,
            args=(session_id, directory),
            name=f"atpiano-replay-{session_id}",
            daemon=True,
        )
        thread.start()

    def _run_replay(self, session_id: str, directory: Path) -> None:
        try:
            preview_model, commit_model = self.get_models()
            manifest = run_corrected_replay(
                self.replay_manifest or Path(),
                directory,
                repeat=self.replay_repeat,
                realtime=self.replay_realtime,
                minimum_free_bytes=self.minimum_free_bytes,
                preview_model=preview_model,
                commit_model=commit_model,
                session_callback=self.set_active,
            )
            if manifest["session_id"] != session_id:
                raise RuntimeError("corrected replay returned a different session")
            write_corrected_exports(directory)
        except Exception as error:
            self.fail_session(error)
        else:
            self.complete_session()


class CorrectedWorkbenchHandler(BaseHTTPRequestHandler):
    server: CorrectedWorkbenchServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_body(self, body: bytes) -> bool:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return False
        return True

    def _host_is_local(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
        }

    def _origin_is_local(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Origin") in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def _send_json(
        self,
        value: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = (
            json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self._write_body(body)

    def _require_local_host(self) -> bool:
        if self._host_is_local():
            return True
        self._send_json(
            {"error": "corrected workbench requests require the local address"},
            HTTPStatus.FORBIDDEN,
        )
        return False

    def _send_file(self, path: Path, *, include_body: bool) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not include_body:
            return
        with path.open("rb") as handle:
            while block := handle.read(64 * 1024):
                if not self._write_body(block):
                    return

    def _current_export(self, request_path: str) -> Path | None:
        name = EXPORT_ASSETS.get(request_path)
        directory = self.server.current_directory()
        if name is None or directory is None:
            return None
        return directory / "exports" / name

    def do_GET(self) -> None:
        if not self._require_local_host():
            return
        parsed = urlsplit(self.path)
        request_path = unquote(parsed.path)
        if request_path == "/api/live":
            self._handle_live_websocket()
            return
        if request_path in ASSETS:
            self._send_file(ASSETS[request_path], include_body=True)
            return
        if request_path == "/api/config":
            self._send_json(
                {
                    "schema_version": CORRECTED_WORKBENCH_SCHEMA,
                    "mode": "corrected-workbench-v2",
                    "stream_schema": CORRECTED_STREAM_SCHEMA,
                    "max_visible_range_s": MAX_VISIBLE_RANGE_S,
                    "replay": {
                        "configured": self.server.replay_manifest is not None,
                        "manifest": (
                            str(self.server.replay_manifest)
                            if self.server.replay_manifest
                            else None
                        ),
                        "repeat": self.server.replay_repeat,
                        "realtime": self.server.replay_realtime,
                    },
                }
            )
            return
        if request_path == "/api/session":
            self._send_json(self.server.public_state())
            return
        if request_path == "/api/events":
            self._get_events(parse_qs(parsed.query))
            return
        export_path = self._current_export(request_path)
        if export_path is not None:
            self._send_file(export_path, include_body=True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
        if request_path in ASSETS:
            self._send_file(ASSETS[request_path], include_body=False)
            return
        export_path = self._current_export(request_path)
        if export_path is not None:
            self._send_file(export_path, include_body=False)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._require_local_host():
            return
        if not self._origin_is_local():
            self._send_json(
                {"error": "corrected workbench actions require the local origin"},
                HTTPStatus.FORBIDDEN,
            )
            return
        request_path = unquote(urlsplit(self.path).path)
        if request_path != "/api/replay":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            self.server.start_replay()
        except (OSError, RuntimeError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.CONFLICT)
            return
        self._send_json(self.server.public_state(), HTTPStatus.ACCEPTED)

    def _get_events(self, query: dict[str, list[str]]) -> None:
        state = self.server.public_state()
        session = state.get("session")
        directory = self.server.current_directory()
        if not isinstance(session, dict) or directory is None:
            self._send_json({"error": "no corrected session is available"}, HTTPStatus.NOT_FOUND)
            return
        try:
            start_sample = int(query.get("start_sample", ["0"])[0])
            end_sample = int(query.get("end_sample", ["0"])[0])
            after = int(query.get("after", ["0"])[0])
            limit = int(query.get("limit", ["1024"])[0])
            sample_rate_hz = int(session["sample_rate_hz"])
            if end_sample - start_sample > round(MAX_VISIBLE_RANGE_S * sample_rate_hz):
                raise ValueError("visible event range exceeds the configured bound")
            database_path = directory / "event-index.sqlite3"
            visible = query_materialized_index(
                database_path,
                start_sample=start_sample,
                end_sample=end_sample,
            )
            history = query_history_index(
                database_path,
                after_sequence=after,
                limit=limit,
            )
        except (FileNotFoundError, sqlite3.Error, TypeError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        cursor = after
        if history:
            cursor = max(int(event["sequence"]) for event in history)
        self._send_json(
            {
                "schema_version": CORRECTED_STREAM_SCHEMA,
                "session_id": session["session_id"],
                "range": {
                    "start_sample": start_sample,
                    "end_sample": end_sample,
                },
                "materialized": visible,
                "history": history,
                "next_sequence": cursor,
                "history_truncated": len(history) == min(limit, MAX_QUERY_LIMIT),
            }
        )

    def _send_websocket_json(self, value: dict[str, Any]) -> None:
        self.connection.sendall(encode_json(value))

    def _send_websocket_close(self, code: int = 1000, reason: str = "") -> None:
        payload = code.to_bytes(2, "big") + reason.encode("utf-8")[:120]
        self.connection.sendall(encode_frame(payload, opcode=0x8))

    def _upgrade_websocket(self) -> bool:
        if not self._origin_is_local():
            self._send_json(
                {"error": "microphone capture requires the local origin"},
                HTTPStatus.FORBIDDEN,
            )
            return False
        if (
            self.headers.get("Upgrade", "").lower() != "websocket"
            or "upgrade" not in self.headers.get("Connection", "").lower()
            or self.headers.get("Sec-WebSocket-Version") != "13"
        ):
            self._send_json(
                {"error": "microphone capture requires a WebSocket upgrade"},
                HTTPStatus.UPGRADE_REQUIRED,
            )
            return False
        try:
            accept = websocket_accept(self.headers.get("Sec-WebSocket-Key", ""))
        except ValueError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return False
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.close_connection = True
        return True

    def _handle_live_websocket(self) -> None:
        if not self._upgrade_websocket():
            return
        session: CorrectedSession | None = None
        stopped = False
        try:
            while True:
                frame = read_frame(self.rfile)
                if frame is None or frame.opcode == 0x8:
                    break
                if frame.opcode == 0x9:
                    self.connection.sendall(encode_frame(frame.payload, opcode=0xA))
                    continue
                if frame.opcode == 0x2:
                    if session is None:
                        raise ValueError("microphone PCM arrived before Start")
                    block = parse_pcm_block(frame.payload)
                    events = session.accept_block(
                        block,
                        received_ns=time.perf_counter_ns(),
                    )
                    self.server.record_delivery(events)
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "block_ack",
                            "sequence": block.sequence,
                            "received_source_frames": session.horizons.audio_head_sample,
                            "events": events,
                            "horizons": session.horizons.document(
                                sample_rate_hz=session.sample_rate_hz
                            ),
                        }
                    )
                    continue
                if frame.opcode != 0x1:
                    raise ValueError("unsupported microphone WebSocket message")
                try:
                    message = json.loads(frame.payload)
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    raise ValueError("microphone control message is invalid JSON") from error
                if not isinstance(message, dict):
                    raise ValueError("microphone control message must be an object")
                if message.get("schema_version") != CORRECTED_STREAM_SCHEMA:
                    raise ValueError("microphone control schema is unsupported")
                message_type = message.get("type")
                if message_type == "start":
                    if session is not None:
                        raise ValueError("microphone session already started")
                    sample_rate_hz = message.get("sample_rate_hz")
                    metadata = message.get("client_metadata")
                    if (
                        not isinstance(sample_rate_hz, int)
                        or isinstance(sample_rate_hz, bool)
                        or not 8_000 <= sample_rate_hz <= 192_000
                        or not isinstance(metadata, dict)
                    ):
                        raise ValueError("microphone Start metadata is invalid")
                    encoded_metadata = json.dumps(metadata, allow_nan=False).encode()
                    if len(encoded_metadata) > MAX_CLIENT_METADATA_BYTES:
                        raise ValueError("microphone client metadata is too large")
                    session_id, directory = self.server.claim_session(
                        source="microphone"
                    )
                    preview_model, commit_model = self.server.get_models()
                    session = CorrectedSession(
                        directory,
                        session_id=session_id,
                        sample_rate_hz=sample_rate_hz,
                        source="microphone",
                        minimum_free_bytes=self.server.minimum_free_bytes,
                    )
                    session.add_lane(
                        CorrectedPreviewLane(session, model=preview_model)
                    )
                    session.add_lane(
                        CorrectedCommitLane(session, model=commit_model)
                    )
                    write_json(
                        directory / "client.json",
                        {
                            "schema_version": "atpiano.corrected-client.v1",
                            "received_at": utc_now(),
                            "metadata": metadata,
                        },
                    )
                    self.server.set_active(session)
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "ready",
                            "session_id": session_id,
                            "sample_rate_hz": sample_rate_hz,
                            "lanes": [lane.status() for lane in session.lanes],
                        }
                    )
                elif message_type == "stop":
                    if session is None:
                        raise ValueError("microphone Stop arrived before Start")
                    frame_count = message.get("frame_count")
                    block_count = message.get("block_count")
                    if (
                        not isinstance(frame_count, int)
                        or isinstance(frame_count, bool)
                        or not isinstance(block_count, int)
                        or isinstance(block_count, bool)
                        or frame_count != session.horizons.audio_head_sample
                        or block_count != session.next_sequence
                    ):
                        raise ValueError("microphone Stop counts do not match accepted PCM")
                    self.server.begin_stop()
                    manifest = session.finalize()
                    exports = write_corrected_exports(session.directory)
                    stopped = True
                    self.server.complete_session()
                    self._send_websocket_json(
                        {
                            "schema_version": CORRECTED_STREAM_SCHEMA,
                            "type": "stopped",
                            "session": manifest,
                            "exports": exports,
                        }
                    )
                    self._send_websocket_close()
                    return
                else:
                    raise ValueError(f"unsupported microphone control type: {message_type}")
        except (ConnectionError, OSError, RuntimeError, ValueError) as error:
            if session is not None and not session.closed:
                session.abort(error)
            self.server.fail_session(error)
            try:
                self._send_websocket_json(
                    {
                        "schema_version": CORRECTED_STREAM_SCHEMA,
                        "type": "error",
                        "error": str(error),
                    }
                )
                self._send_websocket_close(1008, str(error))
            except OSError:
                pass
        finally:
            if session is not None and not stopped and not session.closed:
                error = RuntimeError("microphone WebSocket closed before Stop")
                session.abort(error)
                self.server.fail_session(error)


def create_corrected_workbench_server(
    workspace_directory: Path,
    *,
    port: int = 8001,
    preview_model_factory: PreviewModelFactory = _default_preview_model,
    commit_model_factory: CommitModelFactory | None = None,
    commit_device: str = "cpu",
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_realtime: bool = True,
) -> CorrectedWorkbenchServer:
    factory = commit_model_factory or (
        lambda: _default_commit_model(device=commit_device)
    )
    return CorrectedWorkbenchServer(
        workspace_directory,
        port=port,
        preview_model_factory=preview_model_factory,
        commit_model_factory=factory,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_realtime=replay_realtime,
    )


def serve_corrected_workbench(
    workspace_directory: Path,
    *,
    port: int = 8001,
    open_browser: bool = True,
    commit_device: str = "cpu",
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    replay_manifest: Path | None = None,
    replay_repeat: int = 1,
    replay_realtime: bool = True,
) -> None:
    server = create_corrected_workbench_server(
        workspace_directory,
        port=port,
        commit_device=commit_device,
        minimum_free_bytes=minimum_free_bytes,
        replay_manifest=replay_manifest,
        replay_repeat=replay_repeat,
        replay_realtime=replay_realtime,
    )
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"Corrected-note workspace: {server.workspace_directory}")
    print(url)
    if open_browser:
        webbrowser.open(url)
    if replay_manifest is not None:
        server.start_replay()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
