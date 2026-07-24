from __future__ import annotations

from atpiano.midi import MidiNote
from atpiano.reconcile import Reconciler, WindowRegion


def _region(index: int, *, future: bool = True) -> WindowRegion:
    return WindowRegion(
        index=index,
        source_start_sample=index * 1000,
        source_end_sample=index * 1000 + 2000,
        left_guard_samples=200,
        right_guard_samples=200,
        is_first=index == 0,
        has_future=future,
    )


def test_right_edge_candidate_is_committed_on_corroboration() -> None:
    reconciler = Reconciler(
        session_id="test",
        sample_rate_hz=1000,
        session_origin_ns=1_000_000_000,
        realtime=True,
    )
    first = reconciler.process(
        [(MidiNote(1.85, 2.10, 60, 80), 0.8)],
        _region(0),
        emitted_ns=3_000_000_000,
        total_source_samples=5000,
    )
    second = reconciler.process(
        [(MidiNote(1.86, 2.15, 60, 82), 0.82)],
        _region(1),
        emitted_ns=4_000_000_000,
        total_source_samples=5000,
    )

    assert [event["lifecycle"] for event in first] == ["provisional"]
    assert [event["lifecycle"] for event in second] == ["committed"]
    assert first[0]["event_id"] == second[0]["event_id"]
    assert second[0]["revision"] == 2
    assert len(reconciler.final_tracks()) == 1


def test_uncorroborated_candidate_is_retracted() -> None:
    reconciler = Reconciler(
        session_id="test",
        sample_rate_hz=1000,
        session_origin_ns=1_000_000_000,
        realtime=True,
    )
    reconciler.process(
        [(MidiNote(1.85, 2.10, 60, 80), 0.8)],
        _region(0),
        emitted_ns=3_000_000_000,
        total_source_samples=5000,
    )
    records = reconciler.process(
        [],
        _region(1),
        emitted_ns=4_000_000_000,
        total_source_samples=5000,
    )

    assert [event["lifecycle"] for event in records] == ["retracted"]
    assert reconciler.final_tracks() == []


def test_center_candidate_commits_immediately() -> None:
    reconciler = Reconciler(
        session_id="test",
        sample_rate_hz=1000,
        session_origin_ns=1_000_000_000,
        realtime=False,
    )
    records = reconciler.process(
        [(MidiNote(0.5, 0.9, 60, 80), 0.8)],
        _region(0, future=False),
        emitted_ns=1_100_000_000,
        total_source_samples=2000,
    )

    assert records[0]["lifecycle"] == "committed"
    assert records[0]["source_to_emission_latency_s"] is None
    assert len(reconciler.final_tracks()) == 1
