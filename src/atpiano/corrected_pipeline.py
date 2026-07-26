"""Bounded asynchronous coordination for corrected microphone sessions."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from atpiano.corrected import CorrectedSession, CorrectedSessionLane
from atpiano.live import PcmBlock
from atpiano.util import utc_now

SettlementCallback = Callable[[CorrectedSession, dict[str, Any]], None]
FailureCallback = Callable[[CorrectedSession, Exception], None]
SettlementFinalizer = Callable[[CorrectedSession], None]


@dataclass
class _LaneState:
    running: bool = False
    run_count: int = 0
    completed: bool = False
    total_wall_s: float = 0.0
    maximum_wall_s: float = 0.0
    last_started_at: str | None = None
    last_completed_at: str | None = None
    error: str | None = None


class CorrectedSessionPipeline:
    """Accept PCM immediately and advance each model lane on one bounded thread."""

    def __init__(
        self,
        session: CorrectedSession,
        *,
        finalizer: SettlementFinalizer | None = None,
        on_settled: SettlementCallback | None = None,
        on_failed: FailureCallback | None = None,
    ) -> None:
        self.session = session
        self._finalizer = finalizer
        self._on_settled = on_settled
        self._on_failed = on_failed
        self._condition = threading.Condition()
        self._states = {
            lane.name: _LaneState()
            for lane in session.lanes
        }
        self._threads: list[threading.Thread] = []
        self._stopping = False
        self._aborted = False
        self._settled = threading.Event()
        self._callback_sent = False
        self._accepted_blocks = 0
        self._accepted_frames = 0
        self._accept_total_s = 0.0
        self._accept_maximum_s = 0.0
        self._last_received_ns = 0
        for lane in session.lanes:
            thread = threading.Thread(
                target=self._run_lane,
                args=(lane,),
                name=f"atpiano-{session.session_id}-{lane.name}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def accept_block(
        self,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> None:
        with self._condition:
            if self._stopping or self._aborted:
                raise RuntimeError(
                    "corrected capture is no longer accepting PCM"
                )
        started_ns = time.perf_counter_ns()
        self.session.accept_pcm(block, received_ns=received_ns)
        elapsed_s = (time.perf_counter_ns() - started_ns) / 1_000_000_000
        with self._condition:
            self._accepted_blocks += 1
            self._accepted_frames += block.frame_count
            self._accept_total_s += elapsed_s
            self._accept_maximum_s = max(
                self._accept_maximum_s,
                elapsed_s,
            )
            self._last_received_ns = received_ns
            self._condition.notify_all()

    def begin_stop(self) -> dict[str, Any]:
        with self._condition:
            if self._stopping or self._aborted:
                raise RuntimeError("corrected capture Stop is already active")
            self._stopping = True
        manifest = self.session.begin_settling()
        with self._condition:
            self._condition.notify_all()
        if not self.session.lanes:
            self._finish_settlement()
        return manifest

    def abort(self, error: Exception) -> None:
        with self._condition:
            if self._settled.is_set() or self._aborted:
                return
            self._aborted = True
            self._condition.notify_all()
        self.session.abort(error)
        self._settled.set()
        self._send_failure(error)

    def wait(self, timeout: float | None = None) -> bool:
        return self._settled.wait(timeout)

    def _run_lane(self, lane: CorrectedSessionLane) -> None:
        state = self._states[lane.name]
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(
                        lambda: (
                            self._aborted
                            or self._stopping
                            or lane.has_pending_work(self.session)
                        )
                    )
                    if self._aborted:
                        return
                    has_work = lane.has_pending_work(self.session)
                    stopping = self._stopping
                    if has_work:
                        state.running = True
                        state.last_started_at = utc_now()
                        received_ns = self._last_received_ns
                if has_work:
                    started_ns = time.perf_counter_ns()
                    self.session.process_lane(
                        lane,
                        received_ns=received_ns,
                        max_work_items=1,
                    )
                    elapsed_s = (
                        time.perf_counter_ns() - started_ns
                    ) / 1_000_000_000
                    with self._condition:
                        state.running = False
                        state.run_count += 1
                        state.total_wall_s += elapsed_s
                        state.maximum_wall_s = max(
                            state.maximum_wall_s,
                            elapsed_s,
                        )
                        state.last_completed_at = utc_now()
                        self._condition.notify_all()
                    continue
                if stopping:
                    self.session.finalize_lane(lane)
                    with self._condition:
                        state.completed = True
                        if all(
                            candidate.completed
                            for candidate in self._states.values()
                        ):
                            self._finish_settlement()
                    return
        except Exception as error:
            with self._condition:
                state.running = False
                state.error = f"{type(error).__name__}: {error}"
            self.abort(error)

    def _finish_settlement(self) -> None:
        if self._settled.is_set() or self._aborted:
            return
        try:
            if self._finalizer is not None:
                self._finalizer(self.session)
            manifest = self.session.complete_settlement()
        except Exception as error:
            self.abort(error)
            return
        self._settled.set()
        callback = self._on_settled
        if callback is not None and not self._callback_sent:
            self._callback_sent = True
            callback(self.session, manifest)

    def _send_failure(self, error: Exception) -> None:
        callback = self._on_failed
        if callback is not None and not self._callback_sent:
            self._callback_sent = True
            callback(self.session, error)

    def status(self) -> dict[str, Any]:
        with self._condition:
            states = {
                name: {
                    "running": state.running,
                    "pending": (
                        False
                        if state.completed
                        else next(
                            lane.has_pending_work(self.session)
                            for lane in self.session.lanes
                            if lane.name == name
                        )
                    ),
                    "run_count": state.run_count,
                    "completed": state.completed,
                    "total_wall_s": state.total_wall_s,
                    "maximum_wall_s": state.maximum_wall_s,
                    "last_started_at": state.last_started_at,
                    "last_completed_at": state.last_completed_at,
                    "error": state.error,
                }
                for name, state in self._states.items()
            }
            return {
                "schema_version": "atpiano.corrected-pipeline.v1",
                "state": (
                    "failed"
                    if self._aborted
                    else "complete"
                    if self._settled.is_set()
                    else "settling"
                    if self._stopping
                    else "recording"
                ),
                "accepted_blocks": self._accepted_blocks,
                "accepted_frames": self._accepted_frames,
                "accept_total_s": self._accept_total_s,
                "accept_maximum_s": self._accept_maximum_s,
                "lanes": states,
                "audio_to_provisional_lag_samples": (
                    self.session.horizons.audio_head_sample
                    - self.session.horizons.provisional_sample
                ),
                "audio_to_commit_lag_samples": (
                    self.session.horizons.audio_head_sample
                    - self.session.horizons.commit_sample
                ),
            }
