"""Trailing Transkun commit lane for corrected-note sessions."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from atpiano.corrected import (
    CORRECTED_EVENT_SCHEMA,
    CorrectedSession,
    LaneUpdate,
)
from atpiano.live import PcmBlock
from atpiano.util import sha256_file, utc_now, write_json

COMMIT_LANE_SCHEMA = "atpiano.corrected-commit-lane.v1"
DEFAULT_COMMIT_BUFFER_S = 28.0
DEFAULT_COMMIT_HOP_S = 4.0
DEFAULT_COMMIT_MAX_HOP_S = 8.0
DEFAULT_COMMIT_GUARD_S = 4.0
DEFAULT_COMMIT_MIN_CONTEXT_S = 16.0
DEFAULT_COMMIT_ONSET_MATCH_S = 0.12


@dataclass(frozen=True)
class CommitModelEvent:
    onset_s: float
    offset_s: float
    pitch: int
    velocity: int
    has_onset: bool = True
    has_offset: bool = True


@dataclass(frozen=True)
class CommitModelOutput:
    events: tuple[CommitModelEvent, ...]
    inference_s: float
    source_frame_count: int
    model_frame_count: int


class CommitModel(Protocol):
    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput: ...

    def provenance(self) -> dict[str, Any]: ...


class TranskunCommitModel:
    """Pinned Transkun 2.0.1 adapter with no file or subprocess boundary."""

    def __init__(
        self,
        *,
        device: str = "cpu",
        thread_limit: int | None = None,
    ) -> None:
        try:
            import moduleconf
            import torch
            import transkun
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Transkun is unavailable; run `uv sync --extra corrected` "
                "or `uv sync --extra corrected-cu132`"
            ) from error
        if thread_limit is not None:
            if thread_limit <= 0:
                raise ValueError("Transkun thread limit must be positive")
            torch.set_num_threads(thread_limit)
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass

        package_root = Path(transkun.__file__).resolve().parent
        self.checkpoint_path = Path(
            os.environ.get(
                "ATPIANO_TRANSKUN_CHECKPOINT",
                str(package_root / "pretrained" / "2.0.pt"),
            )
        ).resolve()
        self.config_path = Path(
            os.environ.get(
                "ATPIANO_TRANSKUN_CONFIG",
                str(package_root / "pretrained" / "2.0.conf"),
            )
        ).resolve()
        manager = moduleconf.parseFromFile(str(self.config_path))
        model_class = manager["Model"].module.TransKun
        config = manager["Model"].config
        load_started_ns = time.perf_counter_ns()
        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=device,
            weights_only=False,
        )
        torch_device = torch.device(device)
        if torch_device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                f"Transkun requested {device!r}, but Torch cannot use CUDA"
            )
        if torch_device.type == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            torch.set_float32_matmul_precision("highest")
        model = model_class(conf=config).to(torch_device)
        state = checkpoint.get("best_state_dict", checkpoint.get("state_dict"))
        if state is None:
            raise RuntimeError("Transkun checkpoint has no model state")
        model.load_state_dict(state, strict=False)
        model.eval()
        if torch_device.type == "cuda":
            torch.cuda.synchronize(torch_device)
        self._torch = torch
        self._model = model
        self._torch_device = torch_device
        self.device = str(torch_device)
        self.thread_limit = thread_limit
        self.sample_rate_hz = int(model.fs)
        self.load_s = (
            time.perf_counter_ns() - load_started_ns
        ) / 1_000_000_000
        self.checkpoint_sha256 = sha256_file(self.checkpoint_path)
        self.config_sha256 = sha256_file(self.config_path)
        parameter = next(model.parameters(), None)
        self.precision = (
            str(parameter.dtype).removeprefix("torch.")
            if parameter is not None
            else "unknown"
        )
        self.accelerator = self._accelerator_provenance()

    def _accelerator_provenance(self) -> dict[str, Any]:
        if self._torch_device.type != "cuda":
            return {"kind": self._torch_device.type}
        index = (
            self._torch_device.index
            if self._torch_device.index is not None
            else self._torch.cuda.current_device()
        )
        properties = self._torch.cuda.get_device_properties(index)
        major, minor = self._torch.cuda.get_device_capability(index)
        return {
            "kind": "cuda",
            "runtime_version": self._torch.version.cuda,
            "device_index": index,
            "device_name": properties.name,
            "compute_capability": f"{major}.{minor}",
            "compiled_architectures": self._torch.cuda.get_arch_list(),
            "total_memory_bytes": properties.total_memory,
            "float32_matmul_precision": (
                self._torch.get_float32_matmul_precision()
            ),
            "matmul_allow_tf32": (
                self._torch.backends.cuda.matmul.allow_tf32
            ),
            "cudnn_allow_tf32": self._torch.backends.cudnn.allow_tf32,
        }

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        import soxr

        source = (
            np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32) / 32768.0
        )
        source = source[:, np.newaxis]
        if source_sample_rate_hz != self.sample_rate_hz:
            model_audio = soxr.resample(
                source,
                source_sample_rate_hz,
                self.sample_rate_hz,
                quality="HQ",
            ).astype(np.float32)
        else:
            model_audio = source
        tensor = self._torch.from_numpy(np.ascontiguousarray(model_audio)).to(
            self._torch_device
        )
        started_ns = time.perf_counter_ns()
        with self._torch.inference_mode():
            native = self._model.transcribe(
                tensor,
                stepInSecond=None,
                segmentSizeInSecond=None,
                discardSecondHalf=False,
                mergeIncompleteEvent=True,
            )
        if self._torch_device.type == "cuda":
            self._torch.cuda.synchronize(self._torch_device)
        inference_s = (
            time.perf_counter_ns() - started_ns
        ) / 1_000_000_000
        events = tuple(
            sorted(
                (
                    CommitModelEvent(
                        onset_s=max(0.0, float(event.start)),
                        offset_s=max(float(event.start), float(event.end)),
                        pitch=int(event.pitch),
                        velocity=max(1, min(127, int(event.velocity))),
                        has_onset=bool(event.hasOnset),
                        has_offset=bool(event.hasOffset),
                    )
                    for event in native
                    if bool(event.hasOnset)
                ),
                key=lambda event: (
                    event.onset_s,
                    event.pitch,
                    event.offset_s,
                ),
            )
        )
        return CommitModelOutput(
            events=events,
            inference_s=inference_s,
            source_frame_count=source.shape[0],
            model_frame_count=model_audio.shape[0],
        )

    def provenance(self) -> dict[str, Any]:
        return {
            "name": "transkun",
            "version": version("transkun"),
            "adapter": "atpiano-transkun-trailing-v1",
            "device": self.device,
            "thread_limit": self.thread_limit,
            "sample_rate_hz": self.sample_rate_hz,
            "checkpoint": str(self.checkpoint_path),
            "checkpoint_sha256": self.checkpoint_sha256,
            "config": str(self.config_path),
            "config_sha256": self.config_sha256,
            "load_s": self.load_s,
            "torch_version": version("torch"),
            "precision": self.precision,
            "accelerator": self.accelerator,
        }


@dataclass
class _PendingOffset:
    event_id: str
    revision: int
    pitch: int | None
    controller: int | None
    onset_sample: int
    velocity: int
    last_offset_sample: int


def _append_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False))
            handle.write("\n")
        handle.flush()


class CorrectedCommitLane:
    """Commit newly settled onset bands from overlapping trailing decodes."""

    name = "commit"

    def __init__(
        self,
        session: CorrectedSession,
        *,
        model: CommitModel,
        buffer_s: float = DEFAULT_COMMIT_BUFFER_S,
        hop_s: float = DEFAULT_COMMIT_HOP_S,
        maximum_hop_s: float | None = None,
        guard_s: float = DEFAULT_COMMIT_GUARD_S,
        minimum_context_s: float = DEFAULT_COMMIT_MIN_CONTEXT_S,
        onset_match_s: float = DEFAULT_COMMIT_ONSET_MATCH_S,
        debug_enabled: bool = True,
        debug_pruner: Callable[[], Any] | None = None,
    ) -> None:
        if not 0 < guard_s < buffer_s:
            raise ValueError("commit guard must be positive and shorter than buffer")
        resolved_maximum_hop_s = (
            min(DEFAULT_COMMIT_MAX_HOP_S, buffer_s - guard_s)
            if maximum_hop_s is None
            else maximum_hop_s
        )
        if (
            hop_s <= 0
            or resolved_maximum_hop_s < hop_s
            or resolved_maximum_hop_s > buffer_s - guard_s
            or minimum_context_s <= guard_s
        ):
            raise ValueError("commit scheduler timing is invalid")
        if onset_match_s <= 0:
            raise ValueError("commit onset match tolerance must be positive")
        self.session_id = session.session_id
        self.source_sample_rate_hz = session.sample_rate_hz
        self.model = model
        self.debug_enabled = debug_enabled
        self._debug_pruner = debug_pruner
        self.buffer_frames = round(buffer_s * session.sample_rate_hz)
        self.base_hop_frames = round(hop_s * session.sample_rate_hz)
        self.maximum_hop_frames = round(
            resolved_maximum_hop_s * session.sample_rate_hz
        )
        self.hop_frames = self.base_hop_frames
        self._hop_high_water_frames = self.hop_frames
        self._degraded_reason: str | None = None
        self._degraded_transition_count = 0
        self.guard_frames = round(guard_s * session.sample_rate_hz)
        self.minimum_context_frames = round(
            minimum_context_s * session.sample_rate_hz
        )
        self.onset_match_frames = round(onset_match_s * session.sample_rate_hz)
        if self.buffer_frames > session.ring.capacity_frames:
            raise ValueError("commit buffer exceeds corrected session PCM ring")
        self._next_decode_head = self.minimum_context_frames
        self._commit_sample = 0
        self._decode_index = 0
        self._event_ordinal = 0
        self._pending: dict[str, _PendingOffset] = {}
        self._emission_count = 0
        self._matched_count = 0
        self._added_count = 0
        self._retracted_count = 0
        self._closed_tail_count = 0
        self._max_pending_count = 0
        self._inference_s: list[float] = []
        self._decode_wall_s: list[float] = []
        self.diagnostics_directory = (
            session.directory / "diagnostics" / "lane-b"
        )
        if self.debug_enabled:
            self.diagnostics_directory.mkdir(parents=True, exist_ok=True)
        self.decode_path = self.diagnostics_directory / "decodes.jsonl"

    def _new_id(self, event: CommitModelEvent, decode_index: int) -> str:
        value = (
            f"{self.session_id}:commit:{decode_index}:{event.pitch}:"
            f"{event.onset_s:.9f}:{self._event_ordinal}"
        ).encode("ascii")
        self._event_ordinal += 1
        return hashlib.sha256(value).hexdigest()[:20]

    @staticmethod
    def _symbol(event: CommitModelEvent) -> tuple[int | None, int | None]:
        return (
            (event.pitch, None)
            if event.pitch > 0
            else (None, -event.pitch)
        )

    def _record(
        self,
        session: CorrectedSession,
        *,
        event_id: str,
        revision: int,
        lifecycle: str,
        pitch: int | None,
        controller: int | None,
        onset_sample: int,
        offset_sample: int | None,
        velocity: int,
        emitted_ns: int,
        band_start: int,
        band_end: int,
        decode_index: int,
        boundary_reason: str | None = None,
    ) -> dict[str, Any]:
        emitted_elapsed_s = (
            emitted_ns - session.origin_monotonic_ns
        ) / 1_000_000_000
        return {
            "schema_version": CORRECTED_EVENT_SCHEMA,
            "session_id": self.session_id,
            "event_id": event_id,
            "revision": revision,
            "lane": "commit",
            "lifecycle": lifecycle,
            "pitch": pitch,
            "controller": controller,
            "onset_sample": onset_sample,
            "offset_sample": offset_sample,
            "offset_state": "closed" if offset_sample is not None else "open",
            "velocity": velocity,
            "confidence": None,
            "emitted_at_monotonic_ns": emitted_ns,
            "emitted_elapsed_s": emitted_elapsed_s,
            "source_to_emission_latency_s": (
                emitted_elapsed_s - onset_sample / self.source_sample_rate_hz
                if session.realtime
                else None
            ),
            "window_index": None,
            "observation_count": None,
            "preview_internal_lifecycle": None,
            "commit_band": [band_start, band_end],
            "decode_index": decode_index,
            "boundary_reason": boundary_reason,
        }

    def _absolute_events(
        self,
        output: CommitModelOutput,
        *,
        source_start: int,
    ) -> list[tuple[CommitModelEvent, int, int]]:
        return [
            (
                event,
                source_start
                + round(event.onset_s * self.source_sample_rate_hz),
                source_start
                + round(event.offset_s * self.source_sample_rate_hz),
            )
            for event in output.events
        ]

    def _pending_matches(
        self,
        absolute: list[tuple[CommitModelEvent, int, int]],
    ) -> dict[str, tuple[CommitModelEvent, int, int]]:
        candidates: list[
            tuple[int, str, tuple[CommitModelEvent, int, int]]
        ] = []
        for pending in self._pending.values():
            for item in absolute:
                event, onset_sample, _ = item
                pitch, controller = self._symbol(event)
                if pitch != pending.pitch or controller != pending.controller:
                    continue
                distance = abs(onset_sample - pending.onset_sample)
                if distance <= self.onset_match_frames:
                    candidates.append((distance, pending.event_id, item))
        matches: dict[str, tuple[CommitModelEvent, int, int]] = {}
        used: set[tuple[int, int]] = set()
        for _, event_id, item in sorted(
            candidates,
            key=lambda value: (value[0], value[1], value[2][1]),
        ):
            key = (item[1], item[0].pitch)
            if event_id in matches or key in used:
                continue
            matches[event_id] = item
            used.add(key)
        return matches

    def _update_pending(
        self,
        session: CorrectedSession,
        absolute: list[tuple[CommitModelEvent, int, int]],
        *,
        source_start: int,
        band_start: int,
        band_end: int,
        emitted_ns: int,
        final: bool,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        matches = self._pending_matches(absolute)
        for event_id, pending in list(self._pending.items()):
            item = matches.get(event_id)
            if item is not None:
                _, _, observed_offset = item
                pending.last_offset_sample = max(
                    pending.last_offset_sample,
                    observed_offset,
                )
            should_close = final
            reason = "tail-flush" if final else None
            if item is not None and item[2] < band_end:
                should_close = True
                reason = "settled-offset"
            elif item is None and pending.onset_sample < source_start:
                should_close = True
                reason = "left-context-expired"
            if not should_close:
                continue
            pending.revision += 1
            closed_offset = min(
                max(pending.onset_sample + 1, pending.last_offset_sample),
                session.horizons.audio_head_sample,
            )
            records.append(
                self._record(
                    session,
                    event_id=pending.event_id,
                    revision=pending.revision,
                    lifecycle="committed",
                    pitch=pending.pitch,
                    controller=pending.controller,
                    onset_sample=pending.onset_sample,
                    offset_sample=closed_offset,
                    velocity=pending.velocity,
                    emitted_ns=emitted_ns,
                    band_start=band_start,
                    band_end=band_end,
                    decode_index=self._decode_index,
                    boundary_reason=reason,
                )
            )
            self._closed_tail_count += 1
            del self._pending[event_id]
        return records

    def _match_preview(
        self,
        preview: list[dict[str, Any]],
        candidates: list[tuple[CommitModelEvent, int, int]],
    ) -> tuple[dict[int, int], set[int]]:
        pairs: list[tuple[int, int, int]] = []
        for preview_index, event in enumerate(preview):
            if event.get("pitch") is None:
                continue
            for candidate_index, (candidate, onset_sample, _) in enumerate(candidates):
                if candidate.pitch != event["pitch"]:
                    continue
                distance = abs(onset_sample - event["onset_sample"])
                if distance <= self.onset_match_frames:
                    pairs.append((distance, preview_index, candidate_index))
        matches: dict[int, int] = {}
        used: set[int] = set()
        for _, preview_index, candidate_index in sorted(pairs):
            if preview_index in matches or candidate_index in used:
                continue
            matches[preview_index] = candidate_index
            used.add(candidate_index)
        return matches, used

    def _commit_band(
        self,
        session: CorrectedSession,
        absolute: list[tuple[CommitModelEvent, int, int]],
        *,
        band_start: int,
        band_end: int,
        emitted_ns: int,
        final: bool,
    ) -> list[dict[str, Any]]:
        candidates = [
            item
            for item in absolute
            if band_start <= item[1] < band_end
            and (item[0].pitch < 0 or 21 <= item[0].pitch <= 108)
        ]
        preview = [
            event
            for event in session.events.query_materialized(band_start, band_end)
            if event["lane"] == "preview" and event.get("pitch") is not None
        ]
        matches, used_candidates = self._match_preview(preview, candidates)
        records: list[dict[str, Any]] = []
        for preview_index, preview_event in enumerate(preview):
            if preview_index not in matches:
                records.append(
                    self._record(
                        session,
                        event_id=preview_event["event_id"],
                        revision=preview_event["revision"] + 1,
                        lifecycle="retracted",
                        pitch=preview_event.get("pitch"),
                        controller=None,
                        onset_sample=preview_event["onset_sample"],
                        offset_sample=preview_event.get("offset_sample"),
                        velocity=preview_event["velocity"],
                        emitted_ns=emitted_ns,
                        band_start=band_start,
                        band_end=band_end,
                        decode_index=self._decode_index,
                        boundary_reason="not-in-commit-model",
                    )
                )
                self._retracted_count += 1
                continue
            candidate, onset_sample, offset_sample = candidates[
                matches[preview_index]
            ]
            pitch, controller = self._symbol(candidate)
            event_id = preview_event["event_id"]
            revision = preview_event["revision"] + 1
            closed = final or offset_sample < band_end
            records.append(
                self._record(
                    session,
                    event_id=event_id,
                    revision=revision,
                    lifecycle="committed",
                    pitch=pitch,
                    controller=controller,
                    onset_sample=onset_sample,
                    offset_sample=(
                        min(offset_sample, session.horizons.audio_head_sample)
                        if closed
                        else None
                    ),
                    velocity=candidate.velocity,
                    emitted_ns=emitted_ns,
                    band_start=band_start,
                    band_end=band_end,
                    decode_index=self._decode_index,
                    boundary_reason="matched-preview",
                )
            )
            if not closed:
                self._pending[event_id] = _PendingOffset(
                    event_id=event_id,
                    revision=revision,
                    pitch=pitch,
                    controller=controller,
                    onset_sample=onset_sample,
                    velocity=candidate.velocity,
                    last_offset_sample=offset_sample,
                )
            self._matched_count += 1

        for candidate_index, (candidate, onset_sample, offset_sample) in enumerate(
            candidates
        ):
            if candidate_index in used_candidates:
                continue
            pitch, controller = self._symbol(candidate)
            event_id = self._new_id(candidate, self._decode_index)
            closed = final or offset_sample < band_end
            records.append(
                self._record(
                    session,
                    event_id=event_id,
                    revision=1,
                    lifecycle="committed",
                    pitch=pitch,
                    controller=controller,
                    onset_sample=onset_sample,
                    offset_sample=(
                        min(offset_sample, session.horizons.audio_head_sample)
                        if closed
                        else None
                    ),
                    velocity=candidate.velocity,
                    emitted_ns=emitted_ns,
                    band_start=band_start,
                    band_end=band_end,
                    decode_index=self._decode_index,
                    boundary_reason="commit-addition",
                )
            )
            if not closed:
                self._pending[event_id] = _PendingOffset(
                    event_id=event_id,
                    revision=1,
                    pitch=pitch,
                    controller=controller,
                    onset_sample=onset_sample,
                    velocity=candidate.velocity,
                    last_offset_sample=offset_sample,
                )
            self._added_count += 1
        return records

    def _decode(
        self,
        session: CorrectedSession,
        *,
        decode_head: int,
        final: bool,
    ) -> LaneUpdate:
        source_start = max(0, decode_head - self.buffer_frames)
        pcm = session.read_pcm(source_start, decode_head)
        padding_frames = self.guard_frames if final else 0
        if padding_frames:
            pcm += bytes(padding_frames * 2)
        decode_started_ns = time.perf_counter_ns()
        output = self.model.transcribe(
            pcm,
            source_sample_rate_hz=self.source_sample_rate_hz,
        )
        decode_wall_s = (
            time.perf_counter_ns() - decode_started_ns
        ) / 1_000_000_000
        if (
            not final
            and decode_wall_s * self.source_sample_rate_hz
            > self.hop_frames
            and self.hop_frames < self.maximum_hop_frames
        ):
            self.hop_frames = min(
                self.maximum_hop_frames,
                self.hop_frames + self.base_hop_frames,
            )
            self._hop_high_water_frames = max(
                self._hop_high_water_frames,
                self.hop_frames,
            )
            self._degraded_transition_count += 1
            self._degraded_reason = (
                "decode wall time exceeded the source scheduler hop"
            )
        emitted_ns = time.perf_counter_ns()
        band_start = self._commit_sample
        band_end = (
            decode_head
            if final
            else max(band_start, decode_head - self.guard_frames)
        )
        absolute = self._absolute_events(output, source_start=source_start)
        records = self._update_pending(
            session,
            absolute,
            source_start=source_start,
            band_start=band_start,
            band_end=band_end,
            emitted_ns=emitted_ns,
            final=final,
        )
        records.extend(
            self._commit_band(
                session,
                absolute,
                band_start=band_start,
                band_end=band_end,
                emitted_ns=emitted_ns,
                final=final,
            )
        )
        self._commit_sample = band_end
        self._emission_count += len(records)
        self._max_pending_count = max(self._max_pending_count, len(self._pending))
        self._inference_s.append(output.inference_s)
        self._decode_wall_s.append(decode_wall_s)
        if self.debug_enabled:
            _append_jsonl(
                self.decode_path,
                [
                    {
                    "schema_version": "atpiano.corrected-commit-decode.v1",
                    "decode_index": self._decode_index,
                    "source_start_sample": source_start,
                    "source_end_sample": decode_head,
                    "right_padding_frames": padding_frames,
                    "commit_band": [band_start, band_end],
                    "input_frame_count": output.source_frame_count,
                    "model_frame_count": output.model_frame_count,
                    "native_event_count": len(output.events),
                    "emission_count": len(records),
                    "pending_offset_count": len(self._pending),
                    "inference_s": output.inference_s,
                    "decode_wall_s": decode_wall_s,
                    "scheduler_hop_frames": self.hop_frames,
                    "degraded_mode": self.hop_frames > self.base_hop_frames,
                    "final": final,
                    "emitted_monotonic_ns": emitted_ns,
                    }
                ],
            )
            if self._debug_pruner is not None:
                self._debug_pruner()
        self._decode_index += 1
        return LaneUpdate(
            events=tuple(records),
            commit_sample=self._commit_sample,
        )

    def has_pending_work(self, session: CorrectedSession) -> bool:
        return session.horizons.audio_head_sample >= self._next_decode_head

    def process_available(
        self,
        session: CorrectedSession,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> LaneUpdate:
        del received_ns
        events: list[dict[str, Any]] = []
        commit_sample: int | None = None
        processed = 0
        while session.horizons.audio_head_sample >= self._next_decode_head:
            if max_work_items is not None and processed >= max_work_items:
                break
            update = self._decode(
                session,
                decode_head=self._next_decode_head,
                final=False,
            )
            events.extend(update.events)
            commit_sample = update.commit_sample
            self._next_decode_head += self.hop_frames
            processed += 1
        return LaneUpdate(events=tuple(events), commit_sample=commit_sample)

    def accept_block(
        self,
        session: CorrectedSession,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> LaneUpdate:
        del block
        return self.process_available(
            session,
            received_ns=received_ns,
            max_work_items=None,
        )

    def finalize(self, session: CorrectedSession) -> LaneUpdate:
        update = self._decode(
            session,
            decode_head=session.horizons.audio_head_sample,
            final=True,
        )
        if self.debug_enabled:
            write_json(
                self.diagnostics_directory / "commit.json",
                self.status(),
            )
            if self._debug_pruner is not None:
                self._debug_pruner()
        return update

    def status(self) -> dict[str, Any]:
        inference = self._inference_s
        return {
            "schema_version": COMMIT_LANE_SCHEMA,
            "name": self.name,
            "debug_enabled": self.debug_enabled,
            "model": self.model.provenance(),
            "scheduler": {
                "buffer_frames": self.buffer_frames,
                "hop_frames": self.hop_frames,
                "base_hop_frames": self.base_hop_frames,
                "maximum_hop_frames": self.maximum_hop_frames,
                "hop_high_water_frames": self._hop_high_water_frames,
                "guard_frames": self.guard_frames,
                "minimum_context_frames": self.minimum_context_frames,
                "onset_match_frames": self.onset_match_frames,
                "decode_count": self._decode_index,
                "next_decode_head": self._next_decode_head,
                "degraded_mode": self.hop_frames > self.base_hop_frames,
                "degraded_reason": self._degraded_reason,
                "degraded_transition_count": self._degraded_transition_count,
            },
            "commit_sample": self._commit_sample,
            "events": {
                "emissions": self._emission_count,
                "matched_preview": self._matched_count,
                "commit_additions": self._added_count,
                "preview_retractions": self._retracted_count,
                "closed_open_tails": self._closed_tail_count,
            },
            "retention": {
                "pending_offset_count": len(self._pending),
                "pending_offset_high_water": self._max_pending_count,
            },
            "inference_s": {
                "count": len(inference),
                "total": sum(inference),
                "mean": sum(inference) / len(inference) if inference else None,
                "max": max(inference) if inference else None,
            },
            "decode_wall_s": {
                "count": len(self._decode_wall_s),
                "total": sum(self._decode_wall_s),
                "mean": (
                    sum(self._decode_wall_s) / len(self._decode_wall_s)
                    if self._decode_wall_s
                    else None
                ),
                "max": (
                    max(self._decode_wall_s)
                    if self._decode_wall_s
                    else None
                ),
            },
            "recorded_at": utc_now(),
        }
