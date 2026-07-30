from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

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
        self.is_loaded = False
        self.unload_count = 0

    def preview(self) -> _PreviewModel:
        self.is_loaded = True
        return self.preview_model

    def commit(self) -> Any:
        raise AssertionError("unavailable commit model was requested")

    def models(self) -> Any:
        raise AssertionError("replay models were not requested")

    def status(self) -> list[dict[str, Any]]:
        return []

    def loaded(self) -> bool:
        return self.is_loaded

    def unload(self) -> None:
        self.is_loaded = False
        self.unload_count += 1

    def resolve_correction_mode(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unavailable correction mode was resolved")

    def close(self) -> None:
        self.unload()
        self.closed = True


class _ManualTimer:
    def __init__(
        self,
        delay_s: float,
        callback: Callable[[], None],
    ) -> None:
        self.delay_s = delay_s
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        self.callback()


class _ManualTimerFactory:
    def __init__(self) -> None:
        self.timers: list[_ManualTimer] = []

    def __call__(
        self,
        delay_s: float,
        callback: Callable[[], None],
    ) -> _ManualTimer:
        timer = _ManualTimer(delay_s, callback)
        self.timers.append(timer)
        return timer


class _UploadSource:
    sample_rate_hz = 8_000

    def __init__(self) -> None:
        self.closed = False

    def stream(
        self,
        *,
        accept: Callable[[PcmBlock, int], None],
    ) -> tuple[int, int]:
        accept(
            PcmBlock(
                sequence=0,
                first_sample=0,
                frame_count=80,
                sample_rate_hz=self.sample_rate_hz,
                page_sent_ms=10,
                worklet_time_s=0.01,
                pcm_s16le=b"\0\0" * 80,
            ),
            time.perf_counter_ns(),
        )
        return 80, 1

    def provenance(
        self,
        *,
        state: str,
        decoded_frame_count: int = 0,
        decoded_block_count: int = 0,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": "atpiano.recording-upload.v1",
            "state": state,
            "original": {
                "filename": "Evening practice.wav",
                "media_type": "audio/wav",
                "byte_count": 204,
                "sha256": "a" * 64,
            },
            "decode": {
                "frame_count": decoded_frame_count,
                "block_count": decoded_block_count,
            },
            "error": error,
        }

    def close(self) -> None:
        self.closed = True


def _stop_empty_capture(service: CaptureApplicationService) -> None:
    service.stop_microphone(
        frame_count=0,
        block_count=0,
        transport={
            "sent_frame_count": 0,
            "sent_block_count": 0,
            "acknowledged_frame_count": 0,
            "acknowledged_block_count": 0,
            "socket_buffered_bytes_at_stop": 0,
            "socket_buffered_bytes_high_water": 0,
        },
    )
    assert service.wait_for_settlement(timeout=2)
    for _ in range(100):
        if service.state()["status"] == "complete":
            return
        time.sleep(0.01)
    raise AssertionError("capture settlement callback did not complete")


def test_capture_service_rejects_unknown_browser_diagnostics() -> None:
    with pytest.raises(
        ValueError,
        match="capture diagnostics are invalid",
    ):
        CaptureApplicationService._validate_transport(
            {
                "sent_frame_count": 8,
                "sent_block_count": 1,
                "acknowledged_frame_count": 8,
                "acknowledged_block_count": 1,
                "socket_buffered_bytes_at_stop": 0,
                "socket_buffered_bytes_high_water": 0,
                "capture_diagnostics": {
                    "schema_version": "unknown",
                },
            },
            frame_count=8,
            block_count=1,
        )


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
            "capture_diagnostics": {
                "schema_version": (
                    "atpiano.browser-capture-diagnostics.v1"
                ),
                "worklet": {
                    "render_quantum_count": 1,
                },
            },
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
    assert (
        read_json(session.directory / "transport.json")[
            "capture_diagnostics"
        ]["worklet"]["render_quantum_count"]
        == 1
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


def test_capture_service_import_uses_upload_source_and_keeps_provenance(
    tmp_path: Path,
) -> None:
    repository = LocalSessionStore(tmp_path)
    source = _UploadSource()
    finalized: list[str] = []
    service = CaptureApplicationService(
        repository,
        _UnavailableModelPool(),
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda session: finalized.append(session.session_id),
        upload_enabled=True,
    )

    started = service.start_upload(source)
    assert started.session.source == "upload"
    assert service.wait_for_settlement(timeout=2)
    for _ in range(100):
        if service.state()["status"] == "complete":
            break
        time.sleep(0.01)

    session_id = started.session.session_id
    assert service.state()["status"] == "complete"
    assert finalized == [session_id]
    assert source.closed is True
    assert read_json(tmp_path / session_id / "upload.json")["state"] == "accepted"
    assert repository.get_session(session_id).display_name == "Evening practice"
    service.close()


def test_upload_cannot_displace_an_active_microphone_capture(
    tmp_path: Path,
) -> None:
    service = CaptureApplicationService(
        LocalSessionStore(tmp_path),
        _UnavailableModelPool(),
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda _session: None,
        upload_enabled=True,
    )
    microphone = service.start_microphone(
        sample_rate_hz=8_000,
        client_metadata={},
    )
    source = _UploadSource()

    with pytest.raises(RuntimeError, match="already active"):
        service.start_upload(source)

    assert source.closed is True
    assert service.active_session_id() == microphone.session.session_id
    service.abort_microphone(RuntimeError("test cleanup"))
    service.close()


def test_capture_service_unloads_models_after_settled_idle_timeout(
    tmp_path: Path,
) -> None:
    models = _UnavailableModelPool()
    timers = _ManualTimerFactory()
    service = CaptureApplicationService(
        LocalSessionStore(tmp_path),
        models,
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda _session: None,
        model_idle_timeout_s=30,
        model_idle_timer_factory=timers,
    )

    service.start_microphone(
        sample_rate_hz=8_000,
        client_metadata={},
    )
    assert service.model_pool_status() == {
        "loaded": True,
        "idle": False,
        "idle_timeout_s": 30,
        "idle_since": None,
        "eviction_deadline": None,
        "last_unloaded_at": None,
    }
    assert timers.timers == []

    _stop_empty_capture(service)
    status = service.model_pool_status()
    assert status["loaded"] is True
    assert status["idle"] is True
    assert status["idle_since"] is not None
    assert status["eviction_deadline"] is not None
    assert len(timers.timers) == 1
    assert timers.timers[0].delay_s == 30
    assert timers.timers[0].started is True

    timers.timers[0].fire()
    status = service.model_pool_status()
    assert status["loaded"] is False
    assert status["idle"] is False
    assert status["eviction_deadline"] is None
    assert status["last_unloaded_at"] is not None
    assert models.unload_count == 1
    service.close()


def test_new_capture_invalidates_stale_model_eviction(
    tmp_path: Path,
) -> None:
    models = _UnavailableModelPool()
    timers = _ManualTimerFactory()
    service = CaptureApplicationService(
        LocalSessionStore(tmp_path),
        models,
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda _session: None,
        model_idle_timeout_s=30,
        model_idle_timer_factory=timers,
    )
    service.start_microphone(sample_rate_hz=8_000, client_metadata={})
    _stop_empty_capture(service)
    stale_timer = timers.timers[0]

    service.start_microphone(sample_rate_hz=8_000, client_metadata={})
    assert stale_timer.cancelled is True
    stale_timer.fire()
    assert service.model_pool_status()["loaded"] is True
    assert models.unload_count == 0

    service.abort_microphone(RuntimeError("test cleanup"))
    service.close()


def test_zero_model_idle_timeout_keeps_models_loaded(
    tmp_path: Path,
) -> None:
    models = _UnavailableModelPool()
    timers = _ManualTimerFactory()
    service = CaptureApplicationService(
        LocalSessionStore(tmp_path),
        models,
        minimum_free_bytes=0,
        free_bytes=lambda: 10_000,
        finalizer=lambda _session: None,
        model_idle_timeout_s=0,
        model_idle_timer_factory=timers,
    )
    service.start_microphone(sample_rate_hz=8_000, client_metadata={})
    _stop_empty_capture(service)

    status = service.model_pool_status()
    assert status["loaded"] is True
    assert status["idle"] is True
    assert status["eviction_deadline"] is None
    assert timers.timers == []
    service.close()


def test_negative_model_idle_timeout_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="idle timeout"):
        CaptureApplicationService(
            LocalSessionStore(tmp_path),
            _UnavailableModelPool(),
            minimum_free_bytes=0,
            free_bytes=lambda: 10_000,
            finalizer=lambda _session: None,
            model_idle_timeout_s=-1,
        )
