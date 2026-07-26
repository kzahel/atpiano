from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path
from typing import Any

from atpiano.corrected import CorrectedSession
from atpiano.corrected_export import write_corrected_exports
from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.live import PcmBlock
from atpiano.musical_fixture import generate_musical_fixture
from atpiano.workbench import create_workbench_server

BASELINE_PATH = (
    Path(__file__).parent / "fixtures" / "migration" / "legacy-contracts.json"
)
SESSION_ID = "20260726T000000-012345abcdef"


def _baseline() -> dict[str, Any]:
    value = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=2) as response:
        value = json.load(response)
    assert isinstance(value, dict)
    return value


def _serve(server: Any) -> tuple[threading.Thread, str]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread, f"http://127.0.0.1:{server.server_address[1]}"


def _stop(server: Any, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _fixture_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    structure = manifest["musical_structure"]
    renderer = manifest["renderer"]
    return {
        "audio": manifest["audio"],
        "reference": manifest["reference"],
        "structure": {
            key: structure[key]
            for key in (
                "tempo_bpm",
                "meter",
                "lead_s",
                "music_s",
                "tail_s",
                "progression",
            )
        },
        "renderer": {
            key: renderer[key]
            for key in ("name", "version", "sample_rate_hz", "release_s")
        },
    }


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("mode") != "corrected-workbench-v2":
        return config
    score = config["score"]
    return config | {
        "score": {
            "available": score["available"],
            "injected_runner": score.get("injected_runner", False),
        }
    }


def _normalize_session(state: dict[str, Any]) -> dict[str, Any]:
    session = state["session"]
    storage = state["storage"]
    horizons = state["horizons"]
    return {
        key: state[key]
        for key in (
            "schema_version",
            "status",
            "error",
            "session_id",
            "lanes",
            "transport",
            "duration_s",
            "exports_ready",
        )
    } | {
        "session": {
            key: session[key]
            for key in (
                "schema_version",
                "session_id",
                "status",
                "source",
                "realtime",
                "sample_rate_hz",
                "error",
                "source_frame_count",
            )
        },
        "storage": {
            key: storage[key]
            for key in ("audio_pcm_bytes", "minimum_free_bytes")
        },
        "horizons": {
            key: horizons[key]
            for key in (
                "schema_version",
                "sample_rate_hz",
                "audio_head_sample",
                "provisional_sample",
                "commit_sample",
                "lag_s",
            )
        },
    }


def _normalize_score(score: dict[str, Any]) -> dict[str, Any]:
    runtime = score["runtime"]
    return score | {
        "runtime": {
            "available": runtime["available"],
            "injected_runner": runtime.get("injected_runner", False),
        }
    }


def _normalize_exports(exports: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": exports["schema_version"],
        "session_id": exports["session_id"],
        "source_timeline": exports["source_timeline"],
        "jsonl": {
            key: exports["jsonl"][key]
            for key in ("path", "event_count", "history")
        },
        "midi": {
            key: exports["midi"][key]
            for key in (
                "path",
                "note_count",
                "pedal_interval_count",
                "selection",
            )
        },
    }


def test_aligned_musical_fixture_matches_frozen_manifest(
    tmp_path: Path,
) -> None:
    manifest = generate_musical_fixture(tmp_path / "musical")

    assert _fixture_summary(manifest) == _baseline()["fixture"]


def test_v1_configuration_route_matches_frozen_contract(
    tmp_path: Path,
) -> None:
    server = create_workbench_server(tmp_path, port=0)
    thread, base_url = _serve(server)
    try:
        config = _fetch_json(f"{base_url}/api/config")
    finally:
        _stop(server, thread)

    assert config == _baseline()["v1_config"]


def test_v2_recovered_session_routes_match_frozen_contract(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / SESSION_ID,
        session_id=SESSION_ID,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        minimum_free_bytes=0,
    )
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=8,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.001,
            pcm_s16le=b"\0\0" * 8,
        ),
        received_ns=1,
    )
    session.finalize()
    exports = write_corrected_exports(session.directory)

    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        minimum_free_bytes=0,
        commit_model_factory=lambda: None,  # never loaded by read routes
        score_runtime=tmp_path / "score-runtime",
        score_runner=lambda *args: {},
    )
    thread, base_url = _serve(server)
    try:
        config = _fetch_json(f"{base_url}/api/config")
        state = _fetch_json(f"{base_url}/api/session")
        events = _fetch_json(
            f"{base_url}/api/events"
            "?start_sample=0&end_sample=8&after=0"
        )
        score = _fetch_json(f"{base_url}/api/score")
    finally:
        _stop(server, thread)

    baseline = _baseline()
    assert _normalize_config(config) == baseline["v2_config"]
    assert _normalize_session(state) == baseline["v2_session"]
    assert events == baseline["v2_events"]
    assert _normalize_score(score) == baseline["v2_score"]
    assert _normalize_exports(exports) == baseline["v2_exports"]
