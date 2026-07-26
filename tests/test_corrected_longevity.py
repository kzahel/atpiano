from __future__ import annotations

import resource
import time
from pathlib import Path

import numpy as np

from atpiano.corrected import CorrectedSession
from atpiano.corrected_commit import (
    CommitModelEvent,
    CommitModelOutput,
    CorrectedCommitLane,
)
from atpiano.corrected_export import query_history_index, query_materialized_index
from atpiano.corrected_preview import CorrectedPreviewLane
from atpiano.live import LiveModelOutput, PcmBlock
from atpiano.midi import MidiNote
from atpiano.util import utc_now, write_json

SOURCE_DURATION_S = 30 * 60
SAMPLE_RATE_HZ = 100
BLOCK_FRAMES = 500


class _LongevityPreviewModel:
    sample_rate_hz = SAMPLE_RATE_HZ
    window_samples = SAMPLE_RATE_HZ
    fft_hop_samples = 1
    overlapping_frames = 0
    left_guard_samples = 2
    right_guard_samples = 5

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, audio: np.ndarray) -> LiveModelOutput:
        self.calls += 1
        return LiveModelOutput(
            candidates=[
                (
                    MidiNote(
                        onset_s=0.5,
                        offset_s=0.8,
                        pitch=48 + self.calls % 24,
                        velocity=84,
                    ),
                    0.9,
                )
            ],
            raw={"onset": np.array([[self.calls]], dtype=np.float32)},
            inference_s=0.0001,
            decode_s=0.0001,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "longevity-preview", "calls": self.calls}


class _LongevityCommitModel:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(
        self,
        pcm_s16le: bytes,
        *,
        source_sample_rate_hz: int,
    ) -> CommitModelOutput:
        assert source_sample_rate_hz == SAMPLE_RATE_HZ
        self.calls += 1
        duration_s = len(pcm_s16le) / 2 / source_sample_rate_hz
        onset_s = max(0.0, duration_s - 6.0)
        events = [
            CommitModelEvent(
                onset_s=onset_s,
                offset_s=min(duration_s, onset_s + 1.5),
                pitch=48 + self.calls % 24,
                velocity=88,
            )
        ]
        if self.calls % 8 == 0:
            events.append(
                CommitModelEvent(
                    onset_s=onset_s,
                    offset_s=min(duration_s, onset_s + 3.0),
                    pitch=-64,
                    velocity=127,
                )
            )
        return CommitModelOutput(
            events=tuple(events),
            inference_s=0.0002,
            source_frame_count=len(pcm_s16le) // 2,
            model_frame_count=len(pcm_s16le) // 2,
        )

    def provenance(self) -> dict[str, object]:
        return {"name": "longevity-commit", "calls": self.calls}


def _rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    return int(value if value > 10_000_000 else value * 1024)


def test_two_lane_state_is_bounded_over_thirty_minute_source_clock(
    tmp_path: Path,
) -> None:
    session = CorrectedSession(
        tmp_path / "session",
        session_id="longevity-test",
        sample_rate_hz=SAMPLE_RATE_HZ,
        source="replay",
        realtime=False,
        pcm_ring_s=40.0,
        segment_s=60.0,
        minimum_free_bytes=0,
        horizon_snapshot_s=60.0,
    )
    preview_model = _LongevityPreviewModel()
    commit_model = _LongevityCommitModel()
    preview = CorrectedPreviewLane(
        session,
        model=preview_model,
        hop_s=1.0,
        native_retention_windows=4,
        identity_retention_s=40.0,
    )
    commit = CorrectedCommitLane(session, model=commit_model)
    session.add_lane(preview)
    session.add_lane(commit)

    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    rss_before = _rss_bytes()
    total_frames = SOURCE_DURATION_S * SAMPLE_RATE_HZ
    for first_sample in range(0, total_frames, BLOCK_FRAMES):
        values = np.full(BLOCK_FRAMES, 12_000, dtype=np.int16)
        if first_sample == 0:
            values.fill(0)
        session.accept_block(
            PcmBlock(
                sequence=first_sample // BLOCK_FRAMES,
                first_sample=first_sample,
                frame_count=BLOCK_FRAMES,
                sample_rate_hz=SAMPLE_RATE_HZ,
                page_sent_ms=0.0,
                worklet_time_s=0.0,
                pcm_s16le=values.astype("<i2").tobytes(),
            ),
            received_ns=time.perf_counter_ns(),
        )

    preview_status = preview.status()
    commit_status = commit.status()
    assert session.horizons.audio_head_sample == total_frames
    assert session.ring.frame_count == 40 * SAMPLE_RATE_HZ
    assert preview_status["retention"]["native_windows_retained"] == 4
    assert preview_status["retention"]["active_identity_count"] <= 42
    assert commit_status["retention"]["pending_offset_count"] <= 2
    assert commit_status["retention"]["pending_offset_high_water"] <= 2
    session.finalize()

    database_path = session.directory / "event-index.sqlite3"
    old_range = query_materialized_index(
        database_path,
        start_sample=60 * SAMPLE_RATE_HZ,
        end_sample=75 * SAMPLE_RATE_HZ,
    )
    history_page = query_history_index(
        database_path,
        after_sequence=0,
        limit=128,
    )
    disk_bytes = sum(
        path.stat().st_size
        for path in session.directory.rglob("*")
        if path.is_file()
    )
    evidence = {
        "schema_version": "atpiano.corrected-longevity-evidence.v1",
        "recorded_at": utc_now(),
        "source": {
            "duration_s": SOURCE_DURATION_S,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "frame_count": total_frames,
            "block_count": total_frames // BLOCK_FRAMES,
        },
        "runtime": {
            "wall_s": time.perf_counter() - started_wall,
            "cpu_s": time.process_time() - started_cpu,
            "rss_before_bytes": rss_before,
            "rss_high_water_bytes": _rss_bytes(),
        },
        "storage": {
            "total_bytes": disk_bytes,
            "bytes_per_source_second": disk_bytes / SOURCE_DURATION_S,
            "audio_pcm_bytes_per_source_second_at_48khz": 96_000,
        },
        "horizons": session.horizons.document(
            sample_rate_hz=SAMPLE_RATE_HZ
        ),
        "preview": preview_status,
        "commit": commit_status,
        "delivery": {
            "in_memory_retry_rows": 0,
            "indexed_history_page_limit": 4_096,
            "sample_history_page_rows": len(history_page),
        },
        "old_range": {
            "start_s": 60,
            "end_s": 75,
            "materialized_rows": len(old_range),
        },
    }
    write_json(session.directory / "longevity.json", evidence)

    assert history_page
    assert disk_bytes < 32 * 1024**2
