"""Spawned local model workers with a small bounded request protocol."""

from __future__ import annotations

import multiprocessing
import os
import sys
import threading
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any, Literal

from atpiano.corrected_commit import CommitModelOutput
from atpiano.live import LiveModelOutput

MODEL_WORKER_SCHEMA = "atpiano.model-worker.v1"
DEFAULT_WORKER_START_TIMEOUT_S = 120.0

ModelKind = Literal["preview", "commit"]
ModelFactory = Callable[[], Any]


def _apply_thread_limit(thread_limit: int | None) -> None:
    if thread_limit is None:
        return
    if thread_limit <= 0:
        raise ValueError("model worker thread limit must be positive")
    value = str(thread_limit)
    for name in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = value


def _limit_loaded_torch(thread_limit: int | None) -> None:
    if thread_limit is None:
        return
    torch = sys.modules.get("torch")
    if torch is None:
        return
    torch.set_num_threads(thread_limit)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass


def _preview_descriptor(model: Any) -> dict[str, Any]:
    names = (
        "sample_rate_hz",
        "window_samples",
        "fft_hop_samples",
        "overlapping_frames",
        "left_guard_samples",
        "right_guard_samples",
    )
    return {name: getattr(model, name) for name in names}


def _worker_main(
    connection: Connection,
    factory: ModelFactory,
    kind: ModelKind,
    thread_limit: int | None,
) -> None:
    try:
        _apply_thread_limit(thread_limit)
        model = factory()
        _limit_loaded_torch(thread_limit)
        descriptor = _preview_descriptor(model) if kind == "preview" else {}
        connection.send(
            {
                "schema_version": MODEL_WORKER_SCHEMA,
                "type": "ready",
                "kind": kind,
                "descriptor": descriptor,
                "provenance": model.provenance(),
                "pid": os.getpid(),
                "thread_limit": thread_limit,
            }
        )
        while True:
            request = connection.recv()
            if (
                not isinstance(request, dict)
                or request.get("schema_version") != MODEL_WORKER_SCHEMA
            ):
                raise ValueError("model worker request schema is unsupported")
            if request.get("type") == "shutdown":
                return
            if request.get("type") != "infer":
                raise ValueError("model worker request type is unsupported")
            request_id = int(request["request_id"])
            started_ns = time.perf_counter_ns()
            if kind == "preview":
                output = model.predict(request["audio"])
            else:
                output = model.transcribe(
                    request["pcm_s16le"],
                    source_sample_rate_hz=int(
                        request["source_sample_rate_hz"]
                    ),
                )
            connection.send(
                {
                    "schema_version": MODEL_WORKER_SCHEMA,
                    "type": "result",
                    "request_id": request_id,
                    "output": output,
                    "worker_wall_s": (
                        time.perf_counter_ns() - started_ns
                    )
                    / 1_000_000_000,
                }
            )
    except EOFError:
        return
    except Exception as error:
        try:
            connection.send(
                {
                    "schema_version": MODEL_WORKER_SCHEMA,
                    "type": "error",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


class _ModelProcess:
    def __init__(
        self,
        factory: ModelFactory,
        *,
        kind: ModelKind,
        thread_limit: int | None = None,
        start_timeout_s: float = DEFAULT_WORKER_START_TIMEOUT_S,
    ) -> None:
        if start_timeout_s <= 0:
            raise ValueError("model worker start timeout must be positive")
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(
            target=_worker_main,
            args=(child, factory, kind, thread_limit),
            name=f"atpiano-{kind}-model",
            daemon=True,
        )
        process.start()
        child.close()
        self._connection = parent
        self._process = process
        self._kind = kind
        self._lock = threading.Lock()
        self._next_request_id = 1
        self._request_count = 0
        self._total_wall_s = 0.0
        self._maximum_wall_s = 0.0
        self._closed = False
        if not parent.poll(start_timeout_s):
            self.close(force=True)
            raise TimeoutError(f"{kind} model worker did not become ready")
        ready = parent.recv()
        if ready.get("type") == "error":
            self.close(force=True)
            raise RuntimeError(
                f"{kind} model worker failed during startup: "
                f"{ready.get('error_type')}: {ready.get('error')}"
            )
        if (
            ready.get("schema_version") != MODEL_WORKER_SCHEMA
            or ready.get("type") != "ready"
            or ready.get("kind") != kind
        ):
            self.close(force=True)
            raise RuntimeError(f"{kind} model worker returned invalid readiness")
        self.descriptor = dict(ready["descriptor"])
        self._provenance = dict(ready["provenance"])
        self.pid = int(ready["pid"])
        self.thread_limit = ready.get("thread_limit")

    def infer(self, fields: dict[str, Any]) -> Any:
        with self._lock:
            if self._closed or not self._process.is_alive():
                raise RuntimeError(f"{self._kind} model worker is unavailable")
            request_id = self._next_request_id
            self._next_request_id += 1
            started_ns = time.perf_counter_ns()
            try:
                self._connection.send(
                    {
                        "schema_version": MODEL_WORKER_SCHEMA,
                        "type": "infer",
                        "request_id": request_id,
                        **fields,
                    }
                )
                response = self._connection.recv()
            except (BrokenPipeError, EOFError, OSError) as error:
                raise RuntimeError(
                    f"{self._kind} model worker disconnected"
                ) from error
            elapsed_s = (
                time.perf_counter_ns() - started_ns
            ) / 1_000_000_000
            if response.get("type") == "error":
                raise RuntimeError(
                    f"{self._kind} model worker failed: "
                    f"{response.get('error_type')}: {response.get('error')}"
                )
            if (
                response.get("schema_version") != MODEL_WORKER_SCHEMA
                or response.get("type") != "result"
                or response.get("request_id") != request_id
            ):
                raise RuntimeError(
                    f"{self._kind} model worker returned a stale result"
                )
            self._request_count += 1
            self._total_wall_s += elapsed_s
            self._maximum_wall_s = max(self._maximum_wall_s, elapsed_s)
            return response["output"]

    def provenance(self) -> dict[str, Any]:
        return self._provenance | {
            "execution": {
                "boundary": "spawned-process",
                "worker_schema": MODEL_WORKER_SCHEMA,
                "thread_limit": self.thread_limit,
            }
        }

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_WORKER_SCHEMA,
            "kind": self._kind,
            "pid": self.pid,
            "alive": self._process.is_alive(),
            "thread_limit": self.thread_limit,
            "request_count": self._request_count,
            "total_wall_s": self._total_wall_s,
            "maximum_wall_s": self._maximum_wall_s,
        }

    def close(self, *, force: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if not force and self._process.is_alive():
                try:
                    self._connection.send(
                        {
                            "schema_version": MODEL_WORKER_SCHEMA,
                            "type": "shutdown",
                        }
                    )
                except (BrokenPipeError, EOFError, OSError):
                    pass
            self._connection.close()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2)


class PreviewModelWorker:
    def __init__(
        self,
        factory: ModelFactory,
        *,
        thread_limit: int | None = None,
    ) -> None:
        self._worker = _ModelProcess(
            factory,
            kind="preview",
            thread_limit=thread_limit,
        )
        for name, value in self._worker.descriptor.items():
            setattr(self, name, value)

    def predict(self, audio: Any) -> LiveModelOutput:
        output = self._worker.infer({"audio": audio})
        if not isinstance(output, LiveModelOutput):
            raise RuntimeError("preview worker output type is invalid")
        return output

    def provenance(self) -> dict[str, Any]:
        return self._worker.provenance()

    def status(self) -> dict[str, Any]:
        return self._worker.status()

    def close(self) -> None:
        self._worker.close()


class CommitModelWorker:
    def __init__(
        self,
        factory: ModelFactory,
        *,
        thread_limit: int | None = None,
    ) -> None:
        self._worker = _ModelProcess(
            factory,
            kind="commit",
            thread_limit=thread_limit,
        )

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        output = self._worker.infer(
            {
                "pcm_s16le": pcm_s16le,
                "source_sample_rate_hz": source_sample_rate_hz,
            }
        )
        if not isinstance(output, CommitModelOutput):
            raise RuntimeError("commit worker output type is invalid")
        return output

    def provenance(self) -> dict[str, Any]:
        return self._worker.provenance()

    def status(self) -> dict[str, Any]:
        return self._worker.status()

    def close(self) -> None:
        self._worker.close()
