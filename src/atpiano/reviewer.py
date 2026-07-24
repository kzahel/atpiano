"""Local HTTP server for the independent run-artifact reviewer."""

from __future__ import annotations

import mimetypes
import re
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

WEB_ROOT = Path(__file__).with_name("web")
ASSETS = {
    "/": WEB_ROOT / "index.html",
    "/index.html": WEB_ROOT / "index.html",
    "/app.js": WEB_ROOT / "app.js",
    "/styles.css": WEB_ROOT / "styles.css",
}


class ReviewerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        run_directory: Path,
    ) -> None:
        self.run_directory = run_directory.resolve()
        super().__init__(server_address, ReviewerHandler)


class ReviewerHandler(BaseHTTPRequestHandler):
    server: ReviewerServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _resolve_request(self) -> Path | None:
        request_path = unquote(urlsplit(self.path).path)
        if request_path in ASSETS:
            return ASSETS[request_path]
        if not request_path.startswith("/artifacts/"):
            return None
        relative = request_path.removeprefix("/artifacts/")
        candidate = (self.server.run_directory / relative).resolve()
        if not candidate.is_relative_to(self.server.run_directory):
            return None
        return candidate

    def _send_file(self, path: Path, *, include_body: bool) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        start = 0
        end = size - 1
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            start_text, end_text = match.groups()
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else end
            elif end_text:
                suffix_length = min(size, int(end_text))
                start = size - suffix_length
            if start > end or start >= size:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        content_length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if not include_body:
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = content_length
            while remaining:
                block = handle.read(min(64 * 1024, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def do_GET(self) -> None:
        path = self._resolve_request()
        if path is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_file(path, include_body=True)

    def do_HEAD(self) -> None:
        path = self._resolve_request()
        if path is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_file(path, include_body=False)


def create_server(
    run_directory: Path,
    *,
    bind: str = "127.0.0.1",
    port: int = 8000,
) -> ReviewerServer:
    required = ("run.json", "scores.json", "reference.json", "prediction.json")
    missing = [name for name in required if not (run_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"run directory is missing reviewer artifacts: {', '.join(missing)}"
        )
    return ReviewerServer((bind, port), run_directory)


def serve_review(
    run_directory: Path,
    *,
    bind: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
) -> None:
    server = create_server(run_directory, bind=bind, port=port)
    actual_port = server.server_address[1]
    host_for_url = "127.0.0.1" if bind in ("", "0.0.0.0") else bind
    url = f"http://{host_for_url}:{actual_port}/"
    print(f"Reviewing {run_directory.resolve()}")
    print(url)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
