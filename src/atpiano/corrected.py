"""Bounded corrected-note session storage and deterministic replay."""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
import wave
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from atpiano.fixture import INPUT_SCHEMA
from atpiano.live import MAX_PCM_BLOCK_FRAMES, PcmBlock
from atpiano.util import read_json, sha256_file, utc_now, write_json

CORRECTED_SESSION_SCHEMA = "atpiano.corrected-session.v1"
CORRECTED_EVENT_SCHEMA = "atpiano.corrected-note-event.v1"
CORRECTED_HORIZONS_SCHEMA = "atpiano.corrected-horizons.v1"
CORRECTED_BOUNDARY_SCHEMA = "atpiano.corrected-source-boundary.v1"
DEFAULT_PCM_RING_S = 40.0
DEFAULT_SEGMENT_S = 60.0
DEFAULT_MINIMUM_FREE_BYTES = 2 * 1024**3
DEFAULT_HORIZON_SNAPSHOT_S = 5.0


def _append_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False))
            handle.write("\n")
        handle.flush()


class PcmRing:
    """A contiguous PCM16 ring addressed by absolute source samples."""

    def __init__(self, sample_rate_hz: int, *, capacity_s: float) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("PCM ring sample rate must be positive")
        if capacity_s <= 0:
            raise ValueError("PCM ring capacity must be positive")
        self.sample_rate_hz = sample_rate_hz
        self.capacity_frames = max(1, round(capacity_s * sample_rate_hz))
        self.start_sample = 0
        self.end_sample = 0
        self._pcm = bytearray()

    @property
    def frame_count(self) -> int:
        return self.end_sample - self.start_sample

    @property
    def byte_count(self) -> int:
        return len(self._pcm)

    def append(self, first_sample: int, pcm_s16le: bytes) -> None:
        if len(pcm_s16le) % 2:
            raise ValueError("PCM ring payload must contain complete PCM16 frames")
        if first_sample != self.end_sample:
            raise ValueError(
                f"PCM ring source gap: expected {self.end_sample}, got {first_sample}"
            )
        frame_count = len(pcm_s16le) // 2
        self._pcm.extend(pcm_s16le)
        self.end_sample += frame_count
        excess_frames = self.frame_count - self.capacity_frames
        if excess_frames > 0:
            del self._pcm[: excess_frames * 2]
            self.start_sample += excess_frames

    def read(self, start_sample: int, end_sample: int) -> bytes:
        if not self.start_sample <= start_sample <= end_sample <= self.end_sample:
            raise ValueError(
                "PCM ring range is outside retained samples "
                f"[{self.start_sample}, {self.end_sample})"
            )
        relative_start = (start_sample - self.start_sample) * 2
        relative_end = (end_sample - self.start_sample) * 2
        return bytes(self._pcm[relative_start:relative_end])


@dataclass(frozen=True)
class LaneUpdate:
    events: tuple[dict[str, Any], ...] = ()
    provisional_sample: int | None = None
    commit_sample: int | None = None


class CorrectedSessionLane(Protocol):
    name: str

    def has_pending_work(self, session: CorrectedSession) -> bool: ...

    def process_available(
        self,
        session: CorrectedSession,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> LaneUpdate: ...

    def accept_block(
        self,
        session: CorrectedSession,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> LaneUpdate: ...

    def finalize(self, session: CorrectedSession) -> LaneUpdate: ...

    def status(self) -> dict[str, Any]: ...


class SegmentedAudioLog:
    """Append contiguous PCM16 to independently readable WAV segments."""

    def __init__(
        self,
        directory: Path,
        *,
        sample_rate_hz: int,
        segment_s: float = DEFAULT_SEGMENT_S,
        minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    ) -> None:
        if segment_s <= 0:
            raise ValueError("audio segment duration must be positive")
        if minimum_free_bytes < 0:
            raise ValueError("minimum free bytes cannot be negative")
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sample_rate_hz = sample_rate_hz
        self.segment_frames = max(1, round(segment_s * sample_rate_hz))
        self.minimum_free_bytes = minimum_free_bytes
        self.index_path = self.directory / "segments.jsonl"
        self.next_sample = 0
        self.segment_count = 0
        self._segment_first_sample = 0
        self._segment_frames_written = 0
        self._path: Path | None = None
        self._wave: wave.Wave_write | None = None
        self._segments: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self.last_free_bytes: int | None = None

    def _open_segment_unlocked(self) -> None:
        usage = shutil.disk_usage(self.directory)
        self.last_free_bytes = usage.free
        if usage.free < self.minimum_free_bytes:
            raise OSError(
                "corrected session stopped before disk exhaustion: "
                f"{usage.free} bytes free is below the configured "
                f"{self.minimum_free_bytes}-byte reserve"
            )
        self._segment_first_sample = self.next_sample
        self._segment_frames_written = 0
        self._path = self.directory / f"{self.segment_count:06d}.wav"
        if self._path.exists():
            raise FileExistsError(f"audio segment already exists: {self._path}")
        output = wave.open(str(self._path), "wb")
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(self.sample_rate_hz)
        self._wave = output

    def _close_segment_unlocked(self) -> None:
        if self._wave is None or self._path is None:
            return
        self._wave.close()
        row = {
            "schema_version": "atpiano.corrected-audio-segment.v1",
            "segment_index": self.segment_count,
            "path": self._path.name,
            "sha256": sha256_file(self._path),
            "first_sample": self._segment_first_sample,
            "frame_count": self._segment_frames_written,
            "sample_rate_hz": self.sample_rate_hz,
        }
        _append_jsonl(self.index_path, [row])
        self._segments.append(row)
        self.segment_count += 1
        self._wave = None
        self._path = None
        self._segment_frames_written = 0

    def append(self, first_sample: int, pcm_s16le: bytes) -> None:
        if len(pcm_s16le) % 2:
            raise ValueError("audio segment payload must contain complete PCM16 frames")
        if first_sample != self.next_sample:
            raise ValueError(
                f"audio segment source gap: expected {self.next_sample}, "
                f"got {first_sample}"
            )
        with self._lock:
            remaining = memoryview(pcm_s16le)
            while remaining:
                if self._wave is None:
                    self._open_segment_unlocked()
                available_frames = (
                    self.segment_frames - self._segment_frames_written
                )
                write_frames = min(len(remaining) // 2, available_frames)
                write_bytes = write_frames * 2
                assert self._wave is not None
                self._wave.writeframesraw(remaining[:write_bytes])
                remaining = remaining[write_bytes:]
                self._segment_frames_written += write_frames
                self.next_sample += write_frames
                if self._segment_frames_written == self.segment_frames:
                    self._close_segment_unlocked()

    def read(self, start_sample: int, end_sample: int) -> bytes:
        """Read an accepted source range, closing an overlapping active segment."""
        with self._lock:
            if not 0 <= start_sample <= end_sample <= self.next_sample:
                raise ValueError(
                    "audio segment range is outside accepted samples "
                    f"[0, {self.next_sample})"
                )
            if start_sample == end_sample:
                return b""
            if (
                self._wave is not None
                and end_sample > self._segment_first_sample
            ):
                self._close_segment_unlocked()
            parts: list[bytes] = []
            cursor = start_sample
            for row in self._segments:
                segment_start = int(row["first_sample"])
                segment_end = segment_start + int(row["frame_count"])
                if segment_end <= cursor:
                    continue
                if segment_start > cursor:
                    break
                read_end = min(end_sample, segment_end)
                path = self.directory / str(row["path"])
                with wave.open(str(path), "rb") as source:
                    if (
                        source.getnchannels() != 1
                        or source.getsampwidth() != 2
                        or source.getframerate() != self.sample_rate_hz
                    ):
                        raise ValueError(
                            f"audio segment format changed: {path}"
                        )
                    source.setpos(cursor - segment_start)
                    payload = source.readframes(read_end - cursor)
                if len(payload) != (read_end - cursor) * 2:
                    raise ValueError(f"audio segment ended early: {path}")
                parts.append(payload)
                cursor = read_end
                if cursor == end_sample:
                    return b"".join(parts)
            raise ValueError(
                "audio segment index does not cover requested samples "
                f"[{start_sample}, {end_sample})"
            )

    def close(self) -> None:
        with self._lock:
            self._close_segment_unlocked()


class SegmentedEventStore:
    """Append JSONL evidence and maintain a rebuildable SQLite query index."""

    def __init__(
        self,
        directory: Path,
        *,
        sample_rate_hz: int,
        segment_s: float = DEFAULT_SEGMENT_S,
    ) -> None:
        if segment_s <= 0:
            raise ValueError("event segment duration must be positive")
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sample_rate_hz = sample_rate_hz
        self.segment_frames = max(1, round(segment_s * sample_rate_hz))
        self.database_path = self.directory.parent / "event-index.sqlite3"
        self._lock = threading.Lock()
        self._database = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
        )
        self._database.execute("PRAGMA journal_mode=WAL")
        self._database.execute("PRAGMA synchronous=NORMAL")
        self._database.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY,
                event_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                onset_sample INTEGER NOT NULL,
                offset_sample INTEGER,
                lane TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(event_id, revision)
            );
            CREATE INDEX IF NOT EXISTS events_visible
                ON events(onset_sample, event_id, revision);
            CREATE INDEX IF NOT EXISTS events_identity
                ON events(event_id, revision);
            CREATE TABLE IF NOT EXISTS materialized_events (
                event_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL,
                onset_sample INTEGER NOT NULL,
                offset_sample INTEGER,
                lane TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS materialized_events_visible
                ON materialized_events(onset_sample, offset_sample, event_id);
            """
        )
        materialized_count = self._database.execute(
            "SELECT COUNT(*) FROM materialized_events"
        ).fetchone()
        event_count = self._database.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()
        if int(materialized_count[0]) == 0 and int(event_count[0]) > 0:
            self._database.execute(
                """
                INSERT INTO materialized_events (
                    event_id, revision, onset_sample, offset_sample,
                    lane, lifecycle, payload
                )
                SELECT latest.event_id, latest.revision, latest.onset_sample,
                       latest.offset_sample, latest.lane, latest.lifecycle,
                       latest.payload
                FROM events AS latest
                JOIN (
                    SELECT event_id, MAX(revision) AS revision
                    FROM events
                    GROUP BY event_id
                ) AS selected
                  ON latest.event_id = selected.event_id
                 AND latest.revision = selected.revision
                """
            )
            self._database.commit()
        row = self._database.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM events"
        ).fetchone()
        self.next_sequence = int(row[0]) + 1

    @staticmethod
    def _validate(event: dict[str, Any]) -> None:
        required = {
            "schema_version",
            "event_id",
            "revision",
            "lane",
            "lifecycle",
            "onset_sample",
        }
        missing = sorted(required - event.keys())
        if missing:
            raise ValueError(f"corrected event is missing: {', '.join(missing)}")
        if event["schema_version"] != CORRECTED_EVENT_SCHEMA:
            raise ValueError("corrected event has unsupported schema")
        if event["lane"] not in {"preview", "commit"}:
            raise ValueError("corrected event lane is invalid")
        if event["lifecycle"] not in {"provisional", "committed", "retracted"}:
            raise ValueError("corrected event lifecycle is invalid")
        if not isinstance(event["onset_sample"], int):
            raise ValueError("corrected event onset sample must be an integer")
        offset = event.get("offset_sample")
        if offset is not None and not isinstance(offset, int):
            raise ValueError("corrected event offset sample must be an integer or null")

    def append(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        assigned: list[dict[str, Any]] = []
        by_segment: dict[int, list[dict[str, Any]]] = {}
        with self._lock:
            pending_events = list(events)
            for event in pending_events:
                self._validate(event)
            event_ids = sorted({str(event.get("event_id")) for event in pending_events})
            latest_revisions: dict[str, int] = {}
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                rows = self._database.execute(
                    f"""
                    SELECT event_id, MAX(revision)
                    FROM events
                    WHERE event_id IN ({placeholders})
                    GROUP BY event_id
                    """,
                    event_ids,
                ).fetchall()
                latest_revisions = {
                    str(event_id): int(revision)
                    for event_id, revision in rows
                }
            for event in pending_events:
                row = dict(event)
                event_id = str(row["event_id"])
                requested_revision = int(row["revision"])
                row["lane_revision"] = requested_revision
                row["revision"] = max(
                    requested_revision,
                    latest_revisions.get(event_id, 0) + 1,
                )
                latest_revisions[event_id] = row["revision"]
                row["sequence"] = self.next_sequence
                self.next_sequence += 1
                assigned.append(row)
                segment_index = max(0, row["onset_sample"] // self.segment_frames)
                by_segment.setdefault(segment_index, []).append(row)
            if not assigned:
                return []
            for segment_index, rows in by_segment.items():
                _append_jsonl(self.directory / f"{segment_index:06d}.jsonl", rows)
            try:
                self._database.executemany(
                    """
                    INSERT INTO events (
                        sequence, event_id, revision, onset_sample, offset_sample,
                        lane, lifecycle, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row["sequence"],
                            row["event_id"],
                            row["revision"],
                            row["onset_sample"],
                            row.get("offset_sample"),
                            row["lane"],
                            row["lifecycle"],
                            json.dumps(row, sort_keys=True, allow_nan=False),
                        )
                        for row in assigned
                    ],
                )
                self._database.executemany(
                    """
                    INSERT INTO materialized_events (
                        event_id, revision, onset_sample, offset_sample,
                        lane, lifecycle, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        revision = excluded.revision,
                        onset_sample = excluded.onset_sample,
                        offset_sample = excluded.offset_sample,
                        lane = excluded.lane,
                        lifecycle = excluded.lifecycle,
                        payload = excluded.payload
                    WHERE excluded.revision > materialized_events.revision
                    """,
                    [
                        (
                            row["event_id"],
                            row["revision"],
                            row["onset_sample"],
                            row.get("offset_sample"),
                            row["lane"],
                            row["lifecycle"],
                            json.dumps(row, sort_keys=True, allow_nan=False),
                        )
                        for row in assigned
                    ],
                )
                self._database.commit()
            except Exception:
                self._database.rollback()
                self.next_sequence -= len(assigned)
                raise
        return assigned

    def query_materialized(
        self,
        start_sample: int,
        end_sample: int,
    ) -> list[dict[str, Any]]:
        if start_sample < 0 or end_sample < start_sample:
            raise ValueError("event query range is invalid")
        with self._lock:
            rows = self._database.execute(
                """
                SELECT payload
                FROM materialized_events
                WHERE lifecycle != 'retracted'
                  AND onset_sample < ?
                  AND (
                    offset_sample IS NULL
                    OR offset_sample >= ?
                  )
                ORDER BY onset_sample, event_id
                """,
                (end_sample, start_sample),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def query_since(self, sequence: int, *, limit: int = 1024) -> list[dict[str, Any]]:
        if sequence < 0 or limit <= 0:
            raise ValueError("event sequence query is invalid")
        with self._lock:
            rows = self._database.execute(
                """
                SELECT payload
                FROM events
                WHERE sequence > ?
                ORDER BY sequence
                LIMIT ?
                """,
                (sequence, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def iter_latest_committed(self) -> Iterable[dict[str, Any]]:
        with self._lock:
            rows = self._database.execute(
                """
                SELECT latest.payload
                FROM events AS latest
                JOIN (
                    SELECT event_id, MAX(revision) AS revision
                    FROM events
                    GROUP BY event_id
                ) AS selected
                  ON latest.event_id = selected.event_id
                 AND latest.revision = selected.revision
                WHERE latest.lifecycle = 'committed'
                ORDER BY latest.onset_sample, latest.event_id
                """
            ).fetchall()
        for row in rows:
            yield json.loads(row[0])

    def close(self) -> None:
        with self._lock:
            self._database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._database.close()


@dataclass
class CorrectedHorizons:
    audio_head_sample: int = 0
    provisional_sample: int = 0
    commit_sample: int = 0

    def document(self, *, sample_rate_hz: int) -> dict[str, Any]:
        return {
            "schema_version": CORRECTED_HORIZONS_SCHEMA,
            "sample_rate_hz": sample_rate_hz,
            "audio_head_sample": self.audio_head_sample,
            "provisional_sample": self.provisional_sample,
            "commit_sample": self.commit_sample,
            "lag_s": {
                "provisional": (
                    self.audio_head_sample - self.provisional_sample
                )
                / sample_rate_hz,
                "commit": (self.audio_head_sample - self.commit_sample)
                / sample_rate_hz,
            },
        }


class CorrectedSession:
    """One bounded v2 session shared by replay and microphone sources."""

    def __init__(
        self,
        directory: Path,
        *,
        session_id: str,
        sample_rate_hz: int,
        source: str,
        realtime: bool = True,
        pcm_ring_s: float = DEFAULT_PCM_RING_S,
        segment_s: float = DEFAULT_SEGMENT_S,
        minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
        horizon_snapshot_s: float = DEFAULT_HORIZON_SNAPSHOT_S,
    ) -> None:
        if source not in {"replay", "microphone"}:
            raise ValueError("corrected session source is invalid")
        self.directory = directory.resolve()
        if self.directory.exists() and any(self.directory.iterdir()):
            raise FileExistsError(
                f"corrected session directory is not empty: {self.directory}"
            )
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.sample_rate_hz = sample_rate_hz
        self.source = source
        self.realtime = realtime
        self.origin_monotonic_ns = time.perf_counter_ns()
        self.started_at = utc_now()
        self.next_sequence = 0
        self.closed = False
        self.ring = PcmRing(sample_rate_hz, capacity_s=pcm_ring_s)
        self.audio = SegmentedAudioLog(
            self.directory / "audio",
            sample_rate_hz=sample_rate_hz,
            segment_s=segment_s,
            minimum_free_bytes=minimum_free_bytes,
        )
        self.events = SegmentedEventStore(
            self.directory / "events",
            sample_rate_hz=sample_rate_hz,
            segment_s=segment_s,
        )
        self.horizons = CorrectedHorizons()
        self.lanes: list[CorrectedSessionLane] = []
        self.horizons_path = self.directory / "horizons.jsonl"
        self.boundaries_path = self.directory / "boundaries.jsonl"
        self._snapshot_interval_frames = max(
            1,
            round(horizon_snapshot_s * sample_rate_hz),
        )
        self._next_head_snapshot = 0
        self._last_snapshot: tuple[int, int, int] | None = None
        self._state_lock = threading.RLock()
        self._latest_block: PcmBlock | None = None
        self._capture_closed = False
        self._write_session(status="active")
        self._record_horizons(force=True)

    def _write_session(self, *, status: str, error: str | None = None) -> None:
        document = {
            "schema_version": CORRECTED_SESSION_SCHEMA,
            "session_id": self.session_id,
            "status": status,
            "source": self.source,
            "realtime": self.realtime,
            "sample_rate_hz": self.sample_rate_hz,
            "started_at": self.started_at,
            "completed_at": (
                utc_now() if status in {"complete", "failed"} else None
            ),
            "error": error,
            "source_frame_count": self.horizons.audio_head_sample,
            "retention": {
                "pcm_ring_frames": self.ring.capacity_frames,
                "audio_segment_frames": self.audio.segment_frames,
                "event_segment_frames": self.events.segment_frames,
                "minimum_free_bytes": self.audio.minimum_free_bytes,
            },
            "lanes": [lane.status() for lane in self.lanes],
            "artifacts": {
                "audio_index": "audio/segments.jsonl",
                "event_segments": "events/",
                "event_index": "event-index.sqlite3",
                "horizons": "horizons.jsonl",
                "boundaries": "boundaries.jsonl",
            },
        }
        write_json(self.directory / "session.json", document)

    def add_lane(self, lane: CorrectedSessionLane) -> None:
        if self.closed:
            raise RuntimeError("corrected session is closed")
        if self.horizons.audio_head_sample:
            raise RuntimeError("corrected lanes must attach before audio")
        if any(existing.name == lane.name for existing in self.lanes):
            raise ValueError(f"corrected lane already attached: {lane.name}")
        self.lanes.append(lane)
        self._write_session(status="active")

    def _apply_lane_update(self, update: LaneUpdate) -> list[dict[str, Any]]:
        with self._state_lock:
            assigned = self.events.append(update.events)
            if update.provisional_sample is not None:
                self.advance_provisional(update.provisional_sample)
            if update.commit_sample is not None:
                self.advance_commit(update.commit_sample)
            return assigned

    def _record_horizons(self, *, force: bool = False) -> None:
        state = (
            self.horizons.audio_head_sample,
            self.horizons.provisional_sample,
            self.horizons.commit_sample,
        )
        if not force and state == self._last_snapshot:
            return
        row = self.horizons.document(sample_rate_hz=self.sample_rate_hz) | {
            "recorded_at": utc_now()
        }
        _append_jsonl(self.horizons_path, [row])
        write_json(self.directory / "horizons.json", row)
        self._last_snapshot = state

    def accept_pcm(
        self,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> None:
        """Accept and persist one PCM block without executing a model lane."""
        del received_ns
        with self._state_lock:
            if self.closed or self._capture_closed:
                raise RuntimeError("corrected session is closed")
            if block.sample_rate_hz != self.sample_rate_hz:
                raise ValueError("corrected session sample rate changed")
            if block.sequence != self.next_sequence:
                raise ValueError(
                    "corrected session sequence gap: expected "
                    f"{self.next_sequence}, got {block.sequence}"
                )
            if block.first_sample != self.horizons.audio_head_sample:
                raise ValueError(
                    "corrected session source gap: expected "
                    f"{self.horizons.audio_head_sample}, got {block.first_sample}"
                )
            if not 0 < block.frame_count <= MAX_PCM_BLOCK_FRAMES:
                raise ValueError("corrected session PCM block size is invalid")
            if len(block.pcm_s16le) != block.frame_count * 2:
                raise ValueError(
                    "corrected session PCM payload length is invalid"
                )
            self.audio.append(block.first_sample, block.pcm_s16le)
            self.ring.append(block.first_sample, block.pcm_s16le)
            self.next_sequence += 1
            self.horizons.audio_head_sample += block.frame_count
            self._latest_block = block
            if self.horizons.audio_head_sample >= self._next_head_snapshot:
                self._record_horizons()
                self._next_head_snapshot = (
                    self.horizons.audio_head_sample
                    + self._snapshot_interval_frames
                )

    def process_lane(
        self,
        lane: CorrectedSessionLane,
        *,
        received_ns: int,
        max_work_items: int | None = None,
    ) -> list[dict[str, Any]]:
        """Advance one lane over all currently eligible accepted audio."""
        with self._state_lock:
            if self.closed:
                raise RuntimeError("corrected session is closed")
            block = self._latest_block
        if block is None:
            return []
        update = lane.process_available(
            self,
            received_ns=received_ns,
            max_work_items=max_work_items,
        )
        return self._apply_lane_update(update)

    def accept_block(
        self,
        block: PcmBlock,
        *,
        received_ns: int,
    ) -> list[dict[str, Any]]:
        """Compatibility composition for synchronous deterministic replay."""
        self.accept_pcm(block, received_ns=received_ns)
        assigned: list[dict[str, Any]] = []
        for lane in self.lanes:
            assigned.extend(
                self.process_lane(
                    lane,
                    received_ns=received_ns,
                    max_work_items=None,
                )
            )
        return assigned

    def read_pcm(self, start_sample: int, end_sample: int) -> bytes:
        """Read accepted PCM from memory when possible, otherwise durable audio."""
        with self._state_lock:
            if not 0 <= start_sample <= end_sample <= self.horizons.audio_head_sample:
                raise ValueError(
                    "corrected PCM range is outside the accepted audio horizon"
                )
            if (
                self.ring.start_sample <= start_sample
                and end_sample <= self.ring.end_sample
            ):
                return self.ring.read(start_sample, end_sample)
            return self.audio.read(start_sample, end_sample)

    def begin_settling(self) -> dict[str, Any]:
        with self._state_lock:
            if self.closed or self._capture_closed:
                raise RuntimeError("corrected session capture is already closed")
            self._capture_closed = True
            self.audio.close()
            self._record_horizons(force=True)
            self._write_session(status="stopping")
            return read_json(self.directory / "session.json")

    def finalize_lane(
        self,
        lane: CorrectedSessionLane,
    ) -> list[dict[str, Any]]:
        with self._state_lock:
            if self.closed:
                raise RuntimeError("corrected session is closed")
            if not self._capture_closed:
                raise RuntimeError(
                    "corrected session cannot finalize a lane during capture"
                )
        return self._apply_lane_update(lane.finalize(self))

    def complete_settlement(self) -> dict[str, Any]:
        with self._state_lock:
            if self.closed:
                raise RuntimeError("corrected session is already closed")
            if not self._capture_closed:
                raise RuntimeError(
                    "corrected session capture is still accepting audio"
                )
            self._record_horizons(force=True)
            self.events.close()
            self.closed = True
            self._write_session(status="complete")
            return read_json(self.directory / "session.json")

    def append_events(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.closed:
            raise RuntimeError("corrected session is closed")
        return self.events.append(events)

    def advance_provisional(self, sample: int) -> None:
        if self.closed:
            raise RuntimeError("corrected session is closed")
        if not self.horizons.provisional_sample <= sample <= self.horizons.audio_head_sample:
            raise ValueError("provisional horizon must advance within captured audio")
        self.horizons.provisional_sample = sample
        self._record_horizons()

    def advance_commit(self, sample: int) -> None:
        if self.closed:
            raise RuntimeError("corrected session is closed")
        if not self.horizons.commit_sample <= sample <= self.horizons.audio_head_sample:
            raise ValueError("commit horizon must advance within captured audio")
        self.horizons.commit_sample = sample
        self._record_horizons()

    def record_boundary(
        self,
        *,
        repetition: int,
        start_sample: int,
        end_sample: int,
        input_id: str,
        audio_sha256: str | None,
        kind: str = "input",
    ) -> None:
        if start_sample < 0 or end_sample < start_sample:
            raise ValueError("corrected source boundary is invalid")
        if kind not in {"input", "inserted-silence"}:
            raise ValueError("corrected source boundary kind is invalid")
        _append_jsonl(
            self.boundaries_path,
            [
                {
                    "schema_version": CORRECTED_BOUNDARY_SCHEMA,
                    "repetition": repetition,
                    "start_sample": start_sample,
                    "end_sample": end_sample,
                    "kind": kind,
                    "input_id": input_id,
                    "audio_sha256": audio_sha256,
                }
            ],
        )

    def finalize(self) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("corrected session is already closed")
        if not self._capture_closed:
            self.begin_settling()
        for lane in self.lanes:
            self.finalize_lane(lane)
        return self.complete_settlement()

    def abort(self, error: Exception) -> None:
        if self.closed:
            return
        self._capture_closed = True
        self.audio.close()
        self.events.close()
        self.closed = True
        self._write_session(status="failed", error=f"{type(error).__name__}: {error}")


def _validate_replay_input(manifest: dict[str, Any], path: Path) -> tuple[Path, int, int]:
    if manifest.get("schema_version") != INPUT_SCHEMA:
        raise ValueError(f"{path} has unsupported schema_version")
    audio = manifest.get("audio")
    if not isinstance(audio, dict):
        raise ValueError(f"{path} is missing audio")
    audio_path = (path.parent / str(audio.get("path", ""))).resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"replay audio does not exist: {audio_path}")
    if sha256_file(audio_path) != audio.get("sha256"):
        raise ValueError("replay audio hash does not match input manifest")
    sample_rate_hz = int(audio["sample_rate_hz"])
    frame_count = int(audio["frame_count"])
    return audio_path, sample_rate_hz, frame_count


def run_corrected_replay(
    input_manifest_path: Path,
    session_directory: Path,
    *,
    repeat: int = 1,
    silence_s: float = 0.0,
    realtime: bool = True,
    block_samples: int = 4096,
    pcm_ring_s: float = DEFAULT_PCM_RING_S,
    segment_s: float = DEFAULT_SEGMENT_S,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
    preview_model: Any | None = None,
    commit_model: Any | None = None,
    session_callback: Callable[[CorrectedSession], None] | None = None,
) -> dict[str, Any]:
    if repeat <= 0:
        raise ValueError("corrected replay repetition count must be positive")
    if silence_s < 0:
        raise ValueError("corrected replay silence cannot be negative")
    if not 0 < block_samples <= MAX_PCM_BLOCK_FRAMES:
        raise ValueError("corrected replay block size is invalid")
    input_manifest_path = input_manifest_path.resolve()
    manifest = read_json(input_manifest_path)
    audio_path, sample_rate_hz, expected_frames = _validate_replay_input(
        manifest,
        input_manifest_path,
    )
    with wave.open(str(audio_path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("corrected replay requires mono PCM16 WAV")
        if source.getframerate() != sample_rate_hz:
            raise ValueError("corrected replay WAV sample rate does not match manifest")
        if source.getnframes() != expected_frames:
            raise ValueError("corrected replay WAV frame count does not match manifest")

    session = CorrectedSession(
        session_directory,
        session_id=session_directory.name,
        sample_rate_hz=sample_rate_hz,
        source="replay",
        realtime=realtime,
        pcm_ring_s=pcm_ring_s,
        segment_s=segment_s,
        minimum_free_bytes=minimum_free_bytes,
    )
    if preview_model is not None:
        from atpiano.corrected_preview import CorrectedPreviewLane

        session.add_lane(CorrectedPreviewLane(session, model=preview_model))
    if commit_model is not None:
        from atpiano.corrected_commit import CorrectedCommitLane

        session.add_lane(CorrectedCommitLane(session, model=commit_model))
    if session_callback is not None:
        session_callback(session)
    sequence = 0
    session_origin_ns = time.perf_counter_ns()

    def accept_pcm(pcm: bytes) -> None:
        nonlocal sequence
        frame_count = len(pcm) // 2
        first_sample = session.horizons.audio_head_sample
        source_end = first_sample + frame_count
        scheduled_ns = session_origin_ns + round(
            source_end / sample_rate_hz * 1_000_000_000
        )
        if realtime:
            remaining_s = (
                scheduled_ns - time.perf_counter_ns()
            ) / 1_000_000_000
            if remaining_s > 0:
                time.sleep(remaining_s)
        session.accept_block(
            PcmBlock(
                sequence=sequence,
                first_sample=first_sample,
                frame_count=frame_count,
                sample_rate_hz=sample_rate_hz,
                page_sent_ms=source_end / sample_rate_hz * 1000,
                worklet_time_s=source_end / sample_rate_hz,
                pcm_s16le=pcm,
            ),
            received_ns=time.perf_counter_ns(),
        )
        sequence += 1

    try:
        for repetition in range(repeat):
            repetition_start = session.horizons.audio_head_sample
            with wave.open(str(audio_path), "rb") as source:
                while True:
                    pcm = source.readframes(block_samples)
                    if not pcm:
                        break
                    accept_pcm(pcm)
            session.record_boundary(
                repetition=repetition,
                start_sample=repetition_start,
                end_sample=session.horizons.audio_head_sample,
                input_id=str(manifest.get("input_id", input_manifest_path.stem)),
                audio_sha256=str(manifest["audio"]["sha256"]),
            )
            silence_frames = round(silence_s * sample_rate_hz)
            if repetition + 1 < repeat and silence_frames:
                silence_start = session.horizons.audio_head_sample
                remaining_frames = silence_frames
                while remaining_frames:
                    frames = min(remaining_frames, block_samples)
                    accept_pcm(bytes(frames * 2))
                    remaining_frames -= frames
                session.record_boundary(
                    repetition=repetition,
                    start_sample=silence_start,
                    end_sample=session.horizons.audio_head_sample,
                    input_id="inserted-silence",
                    audio_sha256=None,
                    kind="inserted-silence",
                )
        return session.finalize()
    except Exception as error:
        session.abort(error)
        raise
