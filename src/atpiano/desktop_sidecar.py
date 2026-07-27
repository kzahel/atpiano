"""Authenticated loopback sidecar for the Phase 5 Tauri boundary."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

from atpiano.contracts import CONTRACT_SCHEMA_VERSION
from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.desktop import (
    DESKTOP_PROTOCOL_VERSION,
    DESKTOP_TOKEN_ENV,
    MAX_DESKTOP_READY_BYTES,
    apply_model_pack,
    create_handshake,
    create_ready,
    load_model_pack,
    validate_desktop_token,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atpiano-desktop-sidecar",
        description="run the authenticated Atpiano desktop sidecar",
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--replay-manifest", type=Path, required=True)
    parser.add_argument("--model-pack", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--desktop-origin",
        default="tauri://localhost",
    )
    parser.add_argument(
        "--expected-protocol",
        default=DESKTOP_PROTOCOL_VERSION,
    )
    parser.add_argument(
        "--expected-contract",
        default=CONTRACT_SCHEMA_VERSION,
    )
    parser.add_argument("--expected-model-pack", required=True)
    parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--no-parent-stdin",
        action="store_true",
        help="keep serving when standard input closes (terminal diagnosis)",
    )
    return parser


def _start_shutdown_watcher(
    server: object,
    *,
    monitor_stdin: bool,
) -> None:
    shutdown = getattr(server, "shutdown")
    requested = threading.Event()

    def request_shutdown() -> None:
        if requested.is_set():
            return
        requested.set()
        threading.Thread(target=shutdown, daemon=True).start()

    def handle_signal(_signum: int, _frame: object) -> None:
        request_shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if monitor_stdin:
        def watch_stdin() -> None:
            try:
                sys.stdin.buffer.read(1)
            finally:
                request_shutdown()

        threading.Thread(
            target=watch_stdin,
            name="atpiano-parent-stdin",
            daemon=True,
        ).start()


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    raw_token = os.environ.pop(DESKTOP_TOKEN_ENV, "")
    token = validate_desktop_token(raw_token)
    if args.expected_protocol != DESKTOP_PROTOCOL_VERSION:
        raise ValueError("desktop protocol is incompatible")
    if args.expected_contract != CONTRACT_SCHEMA_VERSION:
        raise ValueError("desktop contract schema is incompatible")
    if args.minimum_free_gib < 0:
        raise ValueError("minimum free space cannot be negative")

    manifest_path = args.model_pack.resolve()
    pack = load_model_pack(manifest_path)
    if pack.model_pack_id != args.expected_model_pack:
        raise ValueError("desktop model pack is incompatible")
    apply_model_pack(pack, manifest_path)
    handshake = create_handshake(pack)

    server = create_corrected_workbench_server(
        args.workspace,
        bind="127.0.0.1",
        port=args.port,
        correction_mode="after-stop",
        minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
        replay_manifest=args.replay_manifest,
        replay_realtime=False,
        score_runtime=args.workspace / ".unavailable-score-runtime",
        application_mode="tauri-desktop-v1",
        desktop_origin=args.desktop_origin,
        desktop_token=token,
        desktop_handshake=handshake,
        compact_recordings=True,
        debug_retention=False,
    )
    ready = create_ready(handshake, int(server.server_address[1]))
    encoded_ready = ready.model_dump_json()
    if len(encoded_ready.encode("utf-8")) > MAX_DESKTOP_READY_BYTES:
        server.server_close()
        raise ValueError("desktop ready record exceeds its size bound")
    print(encoded_ready, flush=True)
    _start_shutdown_watcher(
        server,
        monitor_stdin=not args.no_parent_stdin,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (OSError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema_version": "atpiano.desktop-error.v1",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
