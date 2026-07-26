from __future__ import annotations

import json
import struct
import wave
from pathlib import Path

import pytest

from atpiano.corrected import (
    CORRECTED_EVENT_SCHEMA,
    CorrectedSession,
    LaneUpdate,
    PcmRing,
    SegmentedEventStore,
    run_corrected_replay,
)
from atpiano.fixture import INPUT_SCHEMA
from atpiano.live import PcmBlock
from atpiano.util import read_json, sha256_file, write_json


def _pcm(values: list[int]) -> bytes:
    return struct.pack(f"<{len(values)}h", *values)


def _block(
    sequence: int,
    first_sample: int,
    values: list[int],
    *,
    sample_rate_hz: int = 8_000,
) -> PcmBlock:
    return PcmBlock(
        sequence=sequence,
        first_sample=first_sample,
        frame_count=len(values),
        sample_rate_hz=sample_rate_hz,
        page_sent_ms=0.0,
        worklet_time_s=0.0,
        pcm_s16le=_pcm(values),
    )


def _event(
    event_id: str,
    revision: int,
    onset_sample: int,
    *,
    lifecycle: str,
    lane: str = "preview",
    offset_sample: int | None = None,
) -> dict[str, object]:
    return {
        "schema_version": CORRECTED_EVENT_SCHEMA,
        "session_id": "test",
        "event_id": event_id,
        "revision": revision,
        "lane": lane,
        "lifecycle": lifecycle,
        "pitch": 60,
        "onset_sample": onset_sample,
        "offset_sample": offset_sample,
        "offset_state": "closed" if offset_sample is not None else "open",
        "velocity": 80,
        "confidence": 0.8,
    }


def test_pcm_ring_is_absolute_and_bounded() -> None:
    ring = PcmRing(10, capacity_s=0.5)
    ring.append(0, _pcm([0, 1, 2]))
    ring.append(3, _pcm([3, 4, 5, 6]))

    assert ring.start_sample == 2
    assert ring.end_sample == 7
    assert ring.frame_count == 5
    assert struct.unpack("<5h", ring.read(2, 7)) == (2, 3, 4, 5, 6)
    with pytest.raises(ValueError, match="outside retained"):
        ring.read(1, 3)
    with pytest.raises(ValueError, match="source gap"):
        ring.append(8, _pcm([7]))


def test_segmented_event_store_materializes_latest_revision(tmp_path: Path) -> None:
    store = SegmentedEventStore(tmp_path / "events", sample_rate_hz=10, segment_s=1)
    first = store.append(
        [
            _event("keep", 1, 2, lifecycle="provisional"),
            _event("drop", 1, 4, lifecycle="provisional"),
        ]
    )
    second = store.append(
        [
            _event("keep", 2, 2, lifecycle="committed", lane="commit", offset_sample=8),
            _event("drop", 2, 4, lifecycle="retracted", lane="commit"),
            _event("later", 1, 12, lifecycle="committed", lane="commit"),
        ]
    )
    concurrent = store.append(
        [
            _event(
                "keep",
                2,
                2,
                lifecycle="committed",
                lane="commit",
                offset_sample=9,
            )
        ]
    )

    assert [event["sequence"] for event in first + second + concurrent] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]
    assert concurrent[0]["lane_revision"] == 2
    assert concurrent[0]["revision"] == 3
    visible = store.query_materialized(0, 10)
    assert [event["event_id"] for event in visible] == ["keep"]
    assert visible[0]["offset_sample"] == 9
    assert [event["event_id"] for event in store.query_materialized(10, 20)] == [
        "later"
    ]
    assert [event["sequence"] for event in store.query_since(2)] == [3, 4, 5, 6]
    assert (tmp_path / "events" / "000000.jsonl").is_file()
    assert (tmp_path / "events" / "000001.jsonl").is_file()
    store.close()


def test_corrected_session_segments_audio_and_enforces_horizons(tmp_path: Path) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="replay",
        pcm_ring_s=0.001,
        segment_s=0.0005,
        minimum_free_bytes=0,
        horizon_snapshot_s=0.001,
    )
    session.accept_block(_block(0, 0, [1, 2, 3]), received_ns=1)
    session.accept_block(_block(1, 3, [4, 5, 6, 7]), received_ns=2)
    session.advance_provisional(6)
    session.advance_commit(4)
    with pytest.raises(ValueError, match="must advance"):
        session.advance_commit(3)
    manifest = session.finalize()

    assert manifest["status"] == "complete"
    assert manifest["source_frame_count"] == 7
    assert session.ring.frame_count <= session.ring.capacity_frames
    segment_paths = sorted((tmp_path / "session" / "audio").glob("*.wav"))
    assert len(segment_paths) == 2
    values: list[int] = []
    for path in segment_paths:
        with wave.open(str(path), "rb") as audio:
            raw = audio.readframes(audio.getnframes())
            values.extend(struct.unpack(f"<{len(raw) // 2}h", raw))
    assert values == [1, 2, 3, 4, 5, 6, 7]
    with pytest.raises(RuntimeError, match="closed"):
        session.advance_commit(5)


def test_corrected_session_accepts_pcm_before_processing_lanes(
    tmp_path: Path,
) -> None:
    class RecordingLane:
        name = "recording"

        def __init__(self) -> None:
            self.calls = 0

        def accept_block(
            self,
            session: CorrectedSession,
            block: PcmBlock,
            *,
            received_ns: int,
        ) -> LaneUpdate:
            del block, received_ns
            self.calls += 1
            return LaneUpdate(
                provisional_sample=session.horizons.audio_head_sample
            )

        def finalize(self, session: CorrectedSession) -> LaneUpdate:
            del session
            return LaneUpdate()

        def status(self) -> dict[str, object]:
            return {"name": self.name}

    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        pcm_ring_s=0.0005,
        segment_s=0.001,
        minimum_free_bytes=0,
    )
    lane = RecordingLane()
    session.add_lane(lane)

    session.accept_pcm(_block(0, 0, [1, 2, 3, 4]), received_ns=1)

    assert session.horizons.audio_head_sample == 4
    assert session.horizons.provisional_sample == 0
    assert lane.calls == 0

    session.process_lane(lane, received_ns=2)

    assert lane.calls == 1
    assert session.horizons.provisional_sample == 4


def test_corrected_session_reads_audio_older_than_pcm_ring(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="session",
        sample_rate_hz=8_000,
        source="microphone",
        pcm_ring_s=0.0005,
        segment_s=0.001,
        minimum_free_bytes=0,
    )
    first = list(range(8))
    second = list(range(8, 16))

    session.accept_pcm(_block(0, 0, first), received_ns=1)
    session.accept_pcm(_block(1, 8, second), received_ns=2)

    assert session.ring.start_sample == 12
    assert struct.unpack("<12h", session.read_pcm(2, 14)) == tuple(range(2, 14))
    assert session.audio.segment_count >= 2


def test_corrected_replay_repeats_one_continuous_sample_clock(tmp_path: Path) -> None:
    input_directory = tmp_path / "input"
    input_directory.mkdir()
    audio_path = input_directory / "fixture.wav"
    samples = [100, -100, 200, -200, 300]
    with wave.open(str(audio_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(_pcm(samples))
    write_json(
        input_directory / "input.json",
        {
            "schema_version": INPUT_SCHEMA,
            "input_id": "tiny-loop",
            "audio": {
                "path": audio_path.name,
                "sha256": sha256_file(audio_path),
                "format": "wav-pcm-s16le",
                "sample_rate_hz": 8_000,
                "channels": 1,
                "first_sample_index": 0,
                "frame_count": len(samples),
                "duration_s": len(samples) / 8_000,
            },
        },
    )

    session_directory = tmp_path / "replayed"
    result = run_corrected_replay(
        input_directory / "input.json",
        session_directory,
        repeat=3,
        silence_s=0.001,
        realtime=False,
        block_samples=2,
        pcm_ring_s=0.001,
        segment_s=0.0005,
        minimum_free_bytes=0,
    )

    assert result["status"] == "complete"
    assert result["source_frame_count"] == 31
    boundaries = [
        json.loads(line)
        for line in (session_directory / "boundaries.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [(row["start_sample"], row["end_sample"]) for row in boundaries] == [
        (0, 5),
        (5, 13),
        (13, 18),
        (18, 26),
        (26, 31),
    ]
    assert [row["kind"] for row in boundaries] == [
        "input",
        "inserted-silence",
        "input",
        "inserted-silence",
        "input",
    ]
    assert read_json(session_directory / "horizons.json")["audio_head_sample"] == 31
