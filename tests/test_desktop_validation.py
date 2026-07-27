from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from atpiano.desktop_validation import (
    compare_replays,
    normalized_event_digest,
)


def _write_events(root: Path, emitted_ns: int) -> None:
    exports = root / "exports"
    exports.mkdir(parents=True)
    events = [
        {
            "schema_version": "atpiano.corrected-note-event.v1",
            "session_id": f"session-{emitted_ns}",
            "event_id": f"event-{emitted_ns}-{pitch}",
            "sequence": index,
            "lane": "commit",
            "lifecycle": "commit",
            "pitch": pitch,
            "onset_sample": 1_000,
            "offset_sample": 2_000,
            "emitted_at_monotonic_ns": emitted_ns,
            "emitted_elapsed_s": emitted_ns / 1e9,
            "source_to_emission_latency_s": 0.5,
        }
        for index, pitch in enumerate((60, 64), start=1)
    ]
    if emitted_ns > 1_000:
        events.reverse()
    (exports / "session.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def test_normalized_event_digest_ignores_delivery_timing(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_events(first, 1_000)
    _write_events(second, 9_000)

    assert normalized_event_digest(first) == normalized_event_digest(second)


def test_replay_comparison_requires_product_parity() -> None:
    packaged = {
        "session_id": "packaged",
        "source": {"frame_count": 1},
        "horizons": {"commit_sample": 1},
        "events": {
            "preview_emissions": 2,
            "commit_emissions": 2,
            "normalized_export_count": 4,
            "normalized_export_sha256": "a",
        },
        "final_notes": [
            {
                "onset_s": 1.0,
                "offset_s": 2.0,
                "pitch": 60,
                "velocity": 80,
            }
        ],
        "models": {"commit_device": "cpu"},
        "artifacts": {"mp3_files": ["playback/session.mp3"]},
        "timing": {"total_s": 2.0},
    }
    direct = deepcopy(packaged)
    direct["session_id"] = "direct"
    direct["timing"]["total_s"] = 3.0

    comparison = compare_replays(packaged, direct)

    assert comparison["status"] == "passed"
    direct["final_notes"][0]["pitch"] = 61
    with pytest.raises(RuntimeError, match="products differ"):
        compare_replays(packaged, direct)
