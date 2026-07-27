from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from atpiano.adapters.local_replay import LocalReplaySource
from atpiano.adapters.local_sessions import LocalSessionStore
from atpiano.application.capture import CaptureApplicationService
from atpiano.fixture import generate_fixture
from atpiano.live import LiveModelOutput, PcmBlock
from atpiano.util import read_json


class _PreviewModel:
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
        return {"name": "application-capture-preview"}


class _UnavailableModelPool:
    correction_mode = "unavailable"

    def __init__(self) -> None:
        self.preview_model = _PreviewModel()
        self.closed = False

    def preview(self) -> _PreviewModel:
        return self.preview_model

    def commit(self) -> Any:
        raise AssertionError("unavailable commit model was requested")

    def models(self) -> Any:
        raise AssertionError("replay models were not requested")

    def status(self) -> list[dict[str, Any]]:
        return []

    def resolve_correction_mode(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unavailable correction mode was resolved")

    def close(self) -> None:
        self.closed = True


def test_capture_service_owns_start_pcm_stop_and_settlement_without_http(
    tmp_path: Path,
) -> None:
    finalized: list[str] = []
    models = _UnavailableModelPool()
    service = CaptureApplicationService(
        LocalSessionStore(tmp_path),
        models,
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda session: finalized.append(session.session_id),
    )

    started = service.start_microphone(
        sample_rate_hz=8_000,
        client_metadata={"device": "test"},
    )
    session = service.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=100,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0125,
            pcm_s16le=b"\0\0" * 100,
        ),
        received_ns=time.perf_counter_ns(),
    )
    stopped = service.stop_microphone(
        frame_count=100,
        block_count=1,
        transport={
            "sent_frame_count": 100,
            "sent_block_count": 1,
            "acknowledged_frame_count": 100,
            "acknowledged_block_count": 1,
            "socket_buffered_bytes_at_stop": 0,
            "socket_buffered_bytes_high_water": 200,
        },
    )

    assert stopped["status"] == "stopping"
    assert service.wait_for_settlement(timeout=2)
    assert service.state()["status"] == "complete"
    assert finalized == [session.session_id]
    assert started.session is session
    assert read_json(session.directory / "client.json")["metadata"] == {
        "device": "test"
    }
    assert (
        read_json(session.directory / "transport.json")[
            "socket_buffered_bytes_high_water"
        ]
        == 200
    )

    service.close()
    assert models.closed


def test_capture_service_replay_uses_same_pipeline_without_http(
    tmp_path: Path,
) -> None:
    fixture_directory = tmp_path / "fixture"
    fixture = generate_fixture(fixture_directory)
    models = _UnavailableModelPool()
    finalized: list[str] = []
    service = CaptureApplicationService(
        LocalSessionStore(tmp_path / "workspace"),
        models,
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda session: finalized.append(
            session.session_id
        ),
        replay_source=LocalReplaySource(
            fixture_directory / "input.json",
            repeat=2,
            realtime=False,
        ),
    )

    service.start_replay()
    for _ in range(100):
        state = service.state()
        if state["status"] in {"complete", "failed"}:
            break
        time.sleep(0.05)

    assert state["status"] == "complete", state["error"]
    assert state["session"]["source"] == "replay"
    assert state["session"]["source_frame_count"] == (
        fixture["audio"]["frame_count"] * 2
    )
    assert finalized == [state["session_id"]]
    session_directory = service.current_directory()
    assert session_directory is not None
    assert (
        len(
            (session_directory / "boundaries.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        == 2
    )
    service.close()
