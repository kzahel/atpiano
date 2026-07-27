from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from atpiano.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalSessionStore,
)
from atpiano.application.scores import ScoreApplicationService
from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.live import PcmBlock


class _BlockingScoreExecutor:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.targets: list[tuple[Path, int]] = []

    def runtime_state(self) -> dict[str, Any]:
        return {"available": True, "injected_runner": True}

    def generate_snapshot(
        self,
        session_directory: Path,
        *,
        commit_sample: int,
    ) -> dict[str, Any]:
        self.targets.append((session_directory, commit_sample))
        self.started.set()
        assert self.release.wait(timeout=2)
        return {"session_id": session_directory.name}

    def generate_variant(self, *_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("variant execution was not requested")


def _committed_session(workspace: Path, session_id: str) -> CorrectedSession:
    session = CorrectedSession(
        workspace / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        minimum_free_bytes=0,
    )
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=100,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0125,
            pcm_s16le=b"\0\0" * 100,
        ),
        received_ns=1,
    )
    session.append_events(
        [
            {
                "schema_version": CORRECTED_EVENT_SCHEMA,
                "session_id": session_id,
                "event_id": f"note:{session_id}",
                "revision": 1,
                "lane": "commit",
                "lifecycle": "committed",
                "pitch": 60,
                "controller": None,
                "onset_sample": 10,
                "offset_sample": 80,
                "offset_state": "closed",
                "velocity": 80,
                "confidence": 0.9,
            }
        ]
    )
    session.advance_commit(80)
    session.finalize()
    return session


def test_score_service_freezes_explicit_target_without_http(
    tmp_path: Path,
) -> None:
    older_id = "20260726T100000-aaaaaaaaaaaa"
    newer_id = "20260726T100001-bbbbbbbbbbbb"
    older = _committed_session(tmp_path, older_id)
    _committed_session(tmp_path, newer_id)
    executor = _BlockingScoreExecutor()
    service = ScoreApplicationService(
        LocalSessionStore(tmp_path),
        executor,
        workspace_id=LOCAL_WORKSPACE_ID,
        current_session_id=lambda: newer_id,
    )

    job = service.start(older_id, expected_commit_sample=80)
    assert executor.started.wait(timeout=2)
    assert service.running_session_id() == older_id
    assert executor.targets == [(older.directory, 80)]

    executor.release.set()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = service.job(job.job_id)
        if job.status.value != "running":
            break
        time.sleep(0.01)

    assert job.status.value == "complete"
    assert job.session_id == older_id
    assert job.input_horizon_sample == 80
    assert service.running_session_id() is None
