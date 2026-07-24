"""Local browser capture, transcription, and review workbench."""

from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
import threading
import time
import uuid
import webbrowser
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from atpiano.capture import write_browser_capture_artifacts
from atpiano.live import (
    LIVE_STREAM_SCHEMA,
    BasicPitchLiveModel,
    LiveCaptureSession,
    LiveRecognitionProcessor,
    LiveWindowModel,
    decode_live_message,
    finalize_live_run,
    parse_pcm_block,
)
from atpiano.notation import (
    MUSICXML_MAX_BYTES,
    current_notation,
    generate_notation_artifacts,
    import_oracle_musicxml,
    oracle_status,
)
from atpiano.offline import run_offline
from atpiano.reviewer import ASSETS, ReviewerHandler
from atpiano.util import read_json, utc_now
from atpiano.websocket import encode_frame, encode_json, read_frame, websocket_accept

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_METADATA_BYTES = 16 * 1024
MAX_NOTATION_OPTIONS_BYTES = 16 * 1024
JOB_ID_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}-[0-9a-f]{12}")
Transcriber = Callable[..., dict[str, Any]]
LiveModelFactory = Callable[[], LiveWindowModel]


class WorkbenchHandler(ReviewerHandler):
    server: WorkbenchServer

    def _host_is_local(self) -> bool:
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _require_local_host(self) -> bool:
        if self._host_is_local():
            return True
        self._send_json(
            {"error": "workbench requests must use the local server address"},
            HTTPStatus.FORBIDDEN,
        )
        return False

    def _origin_is_local(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Origin") in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def _send_json(self, value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = (
            json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self._write_body(body)

    def _job(self, job_id: str) -> dict[str, Any] | None:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            return None
        with self.server.jobs_lock:
            job = self.server.jobs.get(job_id)
            return dict(job) if job is not None else None

    def _run_artifact(self, request_path: str) -> Path | None:
        match = re.fullmatch(
            r"/api/runs/([^/]+)/artifacts/(.+)",
            request_path,
        )
        if not match:
            return None
        job_id, relative_text = match.groups()
        job = self._job(job_id)
        if job is None or job["status"] != "complete":
            return None
        run_directory = Path(job["run_directory"]).resolve()
        candidate = (run_directory / unquote(relative_text)).resolve()
        if not candidate.is_relative_to(run_directory):
            return None
        return candidate

    def _complete_run_directory(self, job_id: str) -> Path | None:
        job = self._job(job_id)
        if job is None or job["status"] != "complete":
            return None
        return Path(job["run_directory"]).resolve()

    def _static_asset(self, request_path: str) -> Path | None:
        return ASSETS.get(request_path)

    def do_GET(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
        if request_path == "/api/live":
            self._handle_live_websocket()
            return
        static_path = self._static_asset(request_path)
        if static_path is not None:
            self._send_file(static_path, include_body=True)
            return
        if request_path == "/api/config":
            self._send_json(
                {
                    "schema_version": "atpiano.workbench-config.v1",
                    "mode": "workbench",
                    "max_upload_bytes": MAX_UPLOAD_BYTES,
                    "live": {
                        "enabled": True,
                        "schema_version": LIVE_STREAM_SCHEMA,
                        "transport": "same-origin loopback WebSocket PCM16",
                        "hop_s": 0.25,
                        "commit_horizon_s": 1.0,
                    },
                }
            )
            return
        job_match = re.fullmatch(r"/api/jobs/([^/]+)", request_path)
        if job_match:
            job = self._job(job_match.group(1))
            if job is None:
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._send_json(_public_job(job))
            return
        notation_match = re.fullmatch(r"/api/runs/([^/]+)/notation", request_path)
        if notation_match:
            run_directory = self._complete_run_directory(notation_match.group(1))
            if run_directory is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                self._send_json(current_notation(run_directory))
            except (OSError, RuntimeError, ValueError) as error:
                self._send_json(
                    {"error": f"notation generation failed: {error}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        oracle_match = re.fullmatch(r"/api/runs/([^/]+)/oracle", request_path)
        if oracle_match:
            run_directory = self._complete_run_directory(oracle_match.group(1))
            if run_directory is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_json(oracle_status(run_directory))
            return
        artifact_path = self._run_artifact(request_path)
        if artifact_path is not None:
            self._send_file(artifact_path, include_body=True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _send_websocket_json(self, value: dict[str, object]) -> None:
        self.connection.sendall(encode_json(value))

    def _send_websocket_close(self, code: int = 1000, reason: str = "") -> None:
        payload = code.to_bytes(2, "big") + reason.encode("utf-8")[:120]
        self.connection.sendall(encode_frame(payload, opcode=0x8))

    def _upgrade_websocket(self) -> bool:
        if not self._origin_is_local():
            self._send_json(
                {"error": "live capture requires the local workbench origin"},
                HTTPStatus.FORBIDDEN,
            )
            return False
        if (
            self.headers.get("Upgrade", "").lower() != "websocket"
            or "upgrade" not in self.headers.get("Connection", "").lower()
            or self.headers.get("Sec-WebSocket-Version") != "13"
        ):
            self._send_json(
                {"error": "live capture requires a WebSocket upgrade"},
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
        capture: LiveCaptureSession | None = None
        recognition: LiveRecognitionProcessor | None = None
        live_model: LiveWindowModel | None = None
        job_id: str | None = None
        finalized = False
        try:
            while True:
                frame = read_frame(self.rfile)
                if frame is None or frame.opcode == 0x8:
                    break
                if frame.opcode == 0x9:
                    self.connection.sendall(encode_frame(frame.payload, opcode=0xA))
                    continue
                if frame.opcode == 0x2:
                    if capture is None or live_model is None:
                        raise ValueError("live PCM arrived before the start message")
                    block = parse_pcm_block(frame.payload)
                    received_ns = time.perf_counter_ns()
                    row = capture.accept_block(
                        block,
                        received_ns=received_ns,
                    )
                    if recognition is None:
                        estimated_origin_ns = received_ns - round(
                            (block.first_sample + block.frame_count)
                            / block.sample_rate_hz
                            * 1_000_000_000
                        )
                        recognition = LiveRecognitionProcessor(
                            capture.live_directory / "recognition",
                            session_id=job_id or capture.job_id,
                            source_sample_rate_hz=block.sample_rate_hz,
                            session_origin_ns=estimated_origin_ns,
                            model=live_model,
                        )
                    recognition_batch = recognition.accept_block(
                        block,
                        received_ns=received_ns,
                    )
                    self._send_websocket_json(
                        {
                            "schema_version": LIVE_STREAM_SCHEMA,
                            "type": "block_ack",
                            "sequence": row["sequence"],
                            "source_first_sample": row["source_first_sample"],
                            "source_frame_count": row["source_frame_count"],
                            "received_source_frames": capture.next_sample,
                            "window_count": recognition_batch["window_count"],
                            "noise_gate": recognition_batch["noise_gate"],
                        }
                    )
                    if (
                        recognition_batch["windows_processed"]
                        or recognition_batch["events"]
                    ):
                        self._send_websocket_json(
                            {
                                "schema_version": LIVE_STREAM_SCHEMA,
                                "type": "events",
                                "batch_id": (
                                    f"{job_id}-{recognition_batch['window_count']}"
                                ),
                                "audio_head_sample": recognition_batch[
                                    "audio_head_sample"
                                ],
                                "windows_processed": recognition_batch[
                                    "windows_processed"
                                ],
                                "noise_gate": recognition_batch["noise_gate"],
                                "events": recognition_batch["events"],
                                "host_sent_monotonic_ns": time.perf_counter_ns(),
                            }
                        )
                    continue
                if frame.opcode != 0x1:
                    raise ValueError("unsupported WebSocket message kind")
                try:
                    message = decode_live_message(frame.payload.decode("utf-8"))
                except UnicodeDecodeError as error:
                    raise ValueError("live control message is not UTF-8") from error
                if message["type"] == "start":
                    if capture is not None:
                        raise ValueError("live capture already started")
                    sample_rate_hz = message.get("sample_rate_hz")
                    metadata = message.get("client_metadata")
                    if (
                        not isinstance(sample_rate_hz, int)
                        or isinstance(sample_rate_hz, bool)
                        or not isinstance(metadata, dict)
                    ):
                        raise ValueError("live start metadata is invalid")
                    job_id = self.server.claim_live_job()
                    job_root = self.server.workspace_directory / job_id
                    capture = LiveCaptureSession(
                        job_root,
                        job_id=job_id,
                        sample_rate_hz=sample_rate_hz,
                        client_metadata=metadata,
                    )
                    live_model = self.server.get_live_model()
                    job = {
                        "schema_version": "atpiano.transcription-job.v1",
                        "job_id": job_id,
                        "status": "streaming",
                        "created_at": utc_now(),
                        "started_at": utc_now(),
                        "completed_at": None,
                        "error": None,
                        "input_manifest": str(capture.input_directory / "input.json"),
                        "run_directory": str(job_root / f"run-{job_id}"),
                        "live_directory": str(capture.live_directory),
                    }
                    with self.server.jobs_lock:
                        self.server.jobs[job_id] = job
                    self._send_websocket_json(
                        {
                            "schema_version": LIVE_STREAM_SCHEMA,
                            "type": "ready",
                            "job_id": job_id,
                            "sample_rate_hz": sample_rate_hz,
                            "host_monotonic_ns": time.perf_counter_ns(),
                            "model": live_model.provenance(),
                            "window": {
                                "duration_s": (
                                    live_model.window_samples
                                    / live_model.sample_rate_hz
                                ),
                                "hop_s": 0.25,
                                "commit_horizon_s": 1.0,
                            },
                            "noise_gate": {
                                "calibration_s": 1.0,
                                "policy": (
                                    "median 50 ms room RMS + 8 dB, clamped "
                                    "to -48 through -34 dBFS"
                                ),
                            },
                        }
                    )
                elif message["type"] == "stop":
                    if capture is None or job_id is None:
                        raise ValueError("live Stop arrived before start")
                    frame_count = message.get("frame_count")
                    block_count = message.get("block_count")
                    elapsed_s = message.get("capture_elapsed_s")
                    if (
                        not isinstance(frame_count, int)
                        or isinstance(frame_count, bool)
                        or not isinstance(block_count, int)
                        or isinstance(block_count, bool)
                        or not isinstance(elapsed_s, (int, float))
                        or isinstance(elapsed_s, bool)
                    ):
                        raise ValueError("live Stop metadata is invalid")
                    recognition_manifest = (
                        recognition.finalize() if recognition is not None else None
                    )
                    capture.finalize(
                        expected_frame_count=frame_count,
                        expected_block_count=block_count,
                        capture_elapsed_s=float(elapsed_s),
                    )
                    finalized = True
                    with self.server.jobs_lock:
                        self.server.jobs[job_id]["status"] = "queued"
                    self.server.executor.submit(self.server.run_job, job_id)
                    self.server.release_live_job(job_id)
                    self._send_websocket_json(
                        {
                            "schema_version": LIVE_STREAM_SCHEMA,
                            "type": "stopped",
                            "job_id": job_id,
                            "received_source_frames": capture.next_sample,
                            "block_count": capture.next_sequence,
                            "recognition": recognition_manifest,
                        }
                    )
                    self._send_websocket_close()
                    return
                elif message["type"] == "clock_ping":
                    page_send_ms = message.get("page_send_ms")
                    if (
                        not isinstance(page_send_ms, (int, float))
                        or isinstance(page_send_ms, bool)
                    ):
                        raise ValueError("live clock ping is invalid")
                    host_receive_ns = time.perf_counter_ns()
                    self._send_websocket_json(
                        {
                            "schema_version": LIVE_STREAM_SCHEMA,
                            "type": "clock_pong",
                            "page_send_ms": page_send_ms,
                            "host_receive_ns": host_receive_ns,
                            "host_send_ns": time.perf_counter_ns(),
                        }
                    )
                elif message["type"] == "clock_observation":
                    if capture is None:
                        raise ValueError("clock observation arrived before start")
                    capture.record_clock_observation(
                        message,
                        received_ns=time.perf_counter_ns(),
                    )
                elif message["type"] == "paint":
                    if capture is None:
                        raise ValueError("paint acknowledgement arrived before start")
                    capture.record_paint(
                        message,
                        received_ns=time.perf_counter_ns(),
                    )
                else:
                    raise ValueError(f"unsupported live control type: {message['type']}")
        except (ConnectionError, OSError, RuntimeError, ValueError) as error:
            if capture is not None and not finalized:
                capture.abort(f"{type(error).__name__}: {error}")
            if job_id is not None:
                self.server.fail_live_job(job_id, error)
            try:
                self._send_websocket_json(
                    {
                        "schema_version": LIVE_STREAM_SCHEMA,
                        "type": "error",
                        "error": str(error),
                    }
                )
                self._send_websocket_close(1008, str(error))
            except OSError:
                pass
        finally:
            if capture is not None and not finalized and not capture.closed:
                capture.abort("live WebSocket closed before Stop")
            if job_id is not None and not finalized:
                self.server.release_live_job(job_id)

    def do_HEAD(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
        static_path = self._static_asset(request_path)
        if static_path is not None:
            self._send_file(static_path, include_body=False)
            return
        artifact_path = self._run_artifact(request_path)
        if artifact_path is not None:
            self._send_file(artifact_path, include_body=False)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
        notation_match = re.fullmatch(r"/api/runs/([^/]+)/notation", request_path)
        if notation_match:
            self._post_notation(notation_match.group(1))
            return
        oracle_match = re.fullmatch(
            r"/api/runs/([^/]+)/oracle/(audio|midi)",
            request_path,
        )
        if oracle_match:
            self._post_oracle(oracle_match.group(1), oracle_match.group(2))
            return
        if request_path != "/api/transcriptions":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = self.headers.get_content_type()
        if content_type not in {"audio/wav", "audio/x-wav"}:
            self._send_json(
                {"error": "recording must be uploaded as audio/wav"},
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
            return
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            content_length = -1
        if content_length <= 0:
            self._send_json(
                {"error": "a positive Content-Length is required"},
                HTTPStatus.LENGTH_REQUIRED,
            )
            return
        if content_length > MAX_UPLOAD_BYTES:
            self._send_json(
                {"error": "recording exceeds the 64 MiB upload limit"},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return
        try:
            metadata = _decode_metadata(
                self.headers.get("X-Atpiano-Capture-Metadata", "")
            )
        except ValueError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        job_id = _new_job_id()
        job_root = self.server.workspace_directory / job_id
        input_directory = job_root / "input"
        run_directory = job_root / f"run-{job_id}"
        input_directory.mkdir(parents=True)
        upload_path = input_directory / ".upload.wav"
        try:
            remaining = content_length
            with upload_path.open("wb") as handle:
                while remaining:
                    block = self.rfile.read(min(64 * 1024, remaining))
                    if not block:
                        raise ValueError("recording upload ended early")
                    handle.write(block)
                    remaining -= len(block)
            write_browser_capture_artifacts(
                input_directory,
                upload_path,
                client_metadata=metadata,
            )
        except (OSError, RuntimeError, ValueError) as error:
            shutil.rmtree(job_root, ignore_errors=True)
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        finally:
            upload_path.unlink(missing_ok=True)

        job = {
            "schema_version": "atpiano.transcription-job.v1",
            "job_id": job_id,
            "status": "queued",
            "created_at": utc_now(),
            "started_at": None,
            "completed_at": None,
            "error": None,
            "input_manifest": str(input_directory / "input.json"),
            "run_directory": str(run_directory),
        }
        with self.server.jobs_lock:
            self.server.jobs[job_id] = job
        self.server.executor.submit(self.server.run_job, job_id)
        self._send_json(_public_job(job), HTTPStatus.ACCEPTED)

    def _content_length(self, *, maximum: int, label: str) -> int | None:
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            content_length = -1
        if content_length <= 0:
            self._send_json(
                {"error": f"a positive Content-Length is required for {label}"},
                HTTPStatus.LENGTH_REQUIRED,
            )
            return None
        if content_length > maximum:
            self._send_json(
                {"error": f"{label} exceeds its upload limit"},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return None
        return content_length

    def _read_body(self, content_length: int) -> bytes:
        body = self.rfile.read(content_length)
        if len(body) != content_length:
            raise ValueError("request body ended early")
        return body

    def _post_notation(self, job_id: str) -> None:
        run_directory = self._complete_run_directory(job_id)
        if run_directory is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(
                {"error": "notation options must be application/json"},
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
            return
        content_length = self._content_length(
            maximum=MAX_NOTATION_OPTIONS_BYTES,
            label="notation options",
        )
        if content_length is None:
            return
        try:
            value = json.loads(self._read_body(content_length))
            if not isinstance(value, dict):
                raise ValueError("notation options must be an object")
            manifest = generate_notation_artifacts(run_directory, overrides=value)
        except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(manifest)

    def _post_oracle(self, job_id: str, lane: str) -> None:
        run_directory = self._complete_run_directory(job_id)
        if run_directory is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get_content_type() not in {
            "application/octet-stream",
            "application/vnd.recordare.musicxml+xml",
            "application/xml",
            "text/xml",
        }:
            self._send_json(
                {"error": "oracle result must be an uncompressed MusicXML file"},
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
            return
        content_length = self._content_length(
            maximum=MUSICXML_MAX_BYTES,
            label="MusicXML",
        )
        if content_length is None:
            return
        filename = self.headers.get("X-Atpiano-Filename", "oracle.musicxml")
        try:
            manifest = import_oracle_musicxml(
                run_directory,
                lane=lane,
                data=self._read_body(content_length),
                original_filename=filename,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(manifest)


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        workspace_directory: Path,
        *,
        port: int,
        transcriber: Transcriber,
        live_model_factory: LiveModelFactory,
    ) -> None:
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        self.jobs = _load_completed_jobs(self.workspace_directory)
        self.jobs_lock = threading.Lock()
        self.live_lock = threading.Lock()
        self.active_live_job_id: str | None = None
        self.transcriber = transcriber
        self.live_model_factory = live_model_factory
        self._live_model: LiveWindowModel | None = None
        self._live_model_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="atpiano-transcription",
        )
        super().__init__(("127.0.0.1", port), WorkbenchHandler)

    def get_live_model(self) -> LiveWindowModel:
        with self._live_model_lock:
            if self._live_model is None:
                self._live_model = self.live_model_factory()
            return self._live_model

    def claim_live_job(self) -> str:
        with self.live_lock:
            if self.active_live_job_id is not None:
                raise RuntimeError("another live capture is already active")
            job_id = _new_job_id()
            self.active_live_job_id = job_id
            return job_id

    def release_live_job(self, job_id: str) -> None:
        with self.live_lock:
            if self.active_live_job_id == job_id:
                self.active_live_job_id = None

    def fail_live_job(self, job_id: str, error: Exception) -> None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if job is not None and job["status"] != "complete":
                job["status"] = "failed"
                job["error"] = f"{type(error).__name__}: {error}"
                job["completed_at"] = utc_now()

    def run_job(self, job_id: str) -> None:
        with self.jobs_lock:
            job = self.jobs[job_id]
            job["status"] = "transcribing"
            job["started_at"] = utc_now()
            input_manifest = Path(job["input_manifest"])
            run_directory = Path(job["run_directory"])
            live_directory = (
                Path(job["live_directory"]) if job.get("live_directory") else None
            )
        try:
            self.transcriber(
                input_manifest,
                run_directory,
                command=["atpiano", "workbench", "browser-upload", job_id],
            )
            if live_directory is not None and live_directory.is_dir():
                capture_metadata = input_manifest.parent / "browser-capture.json"
                if capture_metadata.is_file():
                    shutil.copyfile(
                        capture_metadata,
                        run_directory / capture_metadata.name,
                    )
                shutil.copytree(live_directory, run_directory / "live")
                finalize_live_run(run_directory)
        except Exception as error:
            with self.jobs_lock:
                job["status"] = "failed"
                job["error"] = f"{type(error).__name__}: {error}"
                job["completed_at"] = utc_now()
        else:
            with self.jobs_lock:
                job["status"] = "complete"
                job["completed_at"] = utc_now()

    def server_close(self) -> None:
        super().server_close()
        self.executor.shutdown(wait=True, cancel_futures=True)


def _decode_metadata(encoded: str) -> dict[str, Any]:
    if not encoded:
        raise ValueError("browser capture metadata is required")
    if len(encoded) > MAX_METADATA_BYTES:
        raise ValueError("browser capture metadata is too large")
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = json.loads(raw)
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("browser capture metadata is invalid") from error
    if not isinstance(value, dict):
        raise ValueError("browser capture metadata must be an object")
    return value


def _new_job_id() -> str:
    compact_time = (
        utc_now()
        .replace("-", "")
        .replace(":", "")
        .replace("+00:00", "Z")
        .split(".")[0]
        .removesuffix("Z")
    )
    return f"{compact_time}-{uuid.uuid4().hex[:12]}"


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: job[key]
        for key in (
            "schema_version",
            "job_id",
            "status",
            "created_at",
            "started_at",
            "completed_at",
            "error",
        )
    } | {
        "run_url": f"/?run={job['job_id']}" if job["status"] == "complete" else None
    }


def create_workbench_server(
    workspace_directory: Path,
    *,
    port: int = 8000,
    transcriber: Transcriber = run_offline,
    live_model_factory: LiveModelFactory = BasicPitchLiveModel,
) -> WorkbenchServer:
    return WorkbenchServer(
        workspace_directory,
        port=port,
        transcriber=transcriber,
        live_model_factory=live_model_factory,
    )


def _load_completed_jobs(workspace_directory: Path) -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for job_root in workspace_directory.iterdir():
        if not job_root.is_dir() or not JOB_ID_PATTERN.fullmatch(job_root.name):
            continue
        run_directories = (
            job_root / f"run-{job_root.name}",
            job_root / "run",
        )
        run_directory = next(
            (path for path in run_directories if (path / "run.json").is_file()),
            None,
        )
        if run_directory is None:
            continue
        run_manifest = run_directory / "run.json"
        input_manifest = job_root / "input" / "input.json"
        if not run_manifest.is_file() or not input_manifest.is_file():
            continue
        try:
            run = read_json(run_manifest)
        except (OSError, ValueError):
            continue
        if run.get("status") != "complete":
            continue
        jobs[job_root.name] = {
            "schema_version": "atpiano.transcription-job.v1",
            "job_id": job_root.name,
            "status": "complete",
            "created_at": run.get("started_at"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "error": None,
            "input_manifest": str(input_manifest),
            "run_directory": str(run_directory),
        }
    return jobs


def serve_workbench(
    workspace_directory: Path,
    *,
    port: int = 8000,
    open_browser: bool = True,
) -> None:
    server = create_workbench_server(workspace_directory, port=port)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"Atpiano workbench: {workspace_directory.resolve()}")
    print(url)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
