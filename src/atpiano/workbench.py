"""Local browser capture, transcription, and review workbench."""

from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
import threading
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
from atpiano.offline import run_offline
from atpiano.reviewer import ASSETS, ReviewerHandler
from atpiano.util import read_json, utc_now

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_METADATA_BYTES = 16 * 1024
JOB_ID_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}-[0-9a-f]{12}")
Transcriber = Callable[..., dict[str, Any]]


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

    def _send_json(self, value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = (
            json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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

    def _static_asset(self, request_path: str) -> Path | None:
        return ASSETS.get(request_path)

    def do_GET(self) -> None:
        if not self._require_local_host():
            return
        request_path = unquote(urlsplit(self.path).path)
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
        artifact_path = self._run_artifact(request_path)
        if artifact_path is not None:
            self._send_file(artifact_path, include_body=True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

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
        if urlsplit(self.path).path != "/api/transcriptions":
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
        run_directory = job_root / "run"
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


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        workspace_directory: Path,
        *,
        port: int,
        transcriber: Transcriber,
    ) -> None:
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        self.jobs = _load_completed_jobs(self.workspace_directory)
        self.jobs_lock = threading.Lock()
        self.transcriber = transcriber
        self.executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="atpiano-transcription",
        )
        super().__init__(("127.0.0.1", port), WorkbenchHandler)

    def run_job(self, job_id: str) -> None:
        with self.jobs_lock:
            job = self.jobs[job_id]
            job["status"] = "transcribing"
            job["started_at"] = utc_now()
            input_manifest = Path(job["input_manifest"])
            run_directory = Path(job["run_directory"])
        try:
            self.transcriber(
                input_manifest,
                run_directory,
                command=["atpiano", "workbench", "browser-upload", job_id],
            )
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
) -> WorkbenchServer:
    return WorkbenchServer(
        workspace_directory,
        port=port,
        transcriber=transcriber,
    )


def _load_completed_jobs(workspace_directory: Path) -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for job_root in workspace_directory.iterdir():
        if not job_root.is_dir() or not JOB_ID_PATTERN.fullmatch(job_root.name):
            continue
        run_directory = job_root / "run"
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
