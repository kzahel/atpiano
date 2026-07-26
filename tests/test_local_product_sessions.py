from __future__ import annotations

import ast
from pathlib import Path

import pytest

from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.corrected_export import write_corrected_exports
from atpiano.live import PcmBlock
from atpiano.product.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalProductConflictError,
    LocalProductNotFoundError,
    LocalSessionStore,
)


def _session(
    workspace: Path,
    session_id: str,
    *,
    source_frames: int = 8,
) -> CorrectedSession:
    session = CorrectedSession(
        workspace / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        minimum_free_bytes=0,
    )
    if source_frames:
        session.accept_block(
            PcmBlock(
                sequence=0,
                first_sample=0,
                frame_count=source_frames,
                sample_rate_hz=8_000,
                page_sent_ms=0.0,
                worklet_time_s=source_frames / 8_000,
                pcm_s16le=b"\0\0" * source_frames,
            ),
            received_ns=1,
        )
    return session


def test_local_catalog_paginates_and_reads_explicit_sessions(
    tmp_path: Path,
) -> None:
    older_id = "20260726T100000-aaaaaaaaaaaa"
    newer_id = "20260726T100001-bbbbbbbbbbbb"
    older = _session(tmp_path, older_id)
    older.finalize()
    newer = _session(tmp_path, newer_id)
    newer.finalize()
    store = LocalSessionStore(tmp_path)

    first = store.list_sessions(limit=1, active_session_id=None)
    second = store.list_sessions(
        limit=1,
        cursor=first.next_cursor,
        active_session_id=None,
    )

    assert first.workspace_id == LOCAL_WORKSPACE_ID
    assert [item.session_id for item in first.items] == [newer_id]
    assert [item.session_id for item in second.items] == [older_id]
    assert second.next_cursor is None
    assert store.get_session(older_id).source_frame_count == 8
    assert store.workspace().mode.value == "local"


def test_local_reader_converts_events_and_horizons_to_product_contract(
    tmp_path: Path,
) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    session = _session(tmp_path, session_id, source_frames=100)
    session.append_events(
        [
            {
                "schema_version": CORRECTED_EVENT_SCHEMA,
                "session_id": session_id,
                "event_id": "note-c4",
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
    session.advance_provisional(90)
    session.advance_commit(80)
    session.finalize()
    store = LocalSessionStore(tmp_path)

    events = store.events(
        session_id,
        start_sample=0,
        end_sample=100,
    )
    horizon = store.horizon(session_id)

    assert events.session_id == session_id
    assert events.items[0].event_id == "note-c4"
    assert events.items[0].onset_sample == 10
    assert events.items[0].transcription_run_id.endswith(session_id)
    assert horizon.audio_head_sample == 100
    assert horizon.commit_sample == 80


def test_local_artifacts_are_explicit_and_path_safe(tmp_path: Path) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    session = _session(tmp_path, session_id)
    session.finalize()
    write_corrected_exports(session.directory)
    store = LocalSessionStore(tmp_path)

    page = store.list_artifacts(session_id)
    midi = next(item for item in page.items if item.filename == "session.mid")
    resolved, path = store.get_artifact_with_path(session_id, midi.artifact_id)

    assert resolved.session_id == session_id
    assert path == session.directory / "exports" / "session.mid"
    assert path.is_relative_to(session.directory)
    with pytest.raises(LocalProductNotFoundError):
        store.get_artifact_with_path(session_id, "artifact:missing")
    with pytest.raises(LocalProductNotFoundError):
        store.resolve("../outside")


def test_recoverable_delete_guards_targets_and_moves_only_session(
    tmp_path: Path,
) -> None:
    first_id = "20260726T100000-aaaaaaaaaaaa"
    second_id = "20260726T100001-bbbbbbbbbbbb"
    first = _session(tmp_path, first_id)
    first.finalize()
    second = _session(tmp_path, second_id)
    second.finalize()
    store = LocalSessionStore(tmp_path)

    with pytest.raises(LocalProductConflictError, match="active"):
        store.trash_session(
            first_id,
            active_session_id=first_id,
            running_score_session_id=None,
        )
    with pytest.raises(LocalProductConflictError, match="score"):
        store.trash_session(
            first_id,
            active_session_id=None,
            running_score_session_id=first_id,
        )
    result = store.trash_session(
        first_id,
        active_session_id=None,
        running_score_session_id=None,
    )

    assert result.recoverable is True
    assert not (tmp_path / first_id).exists()
    assert (tmp_path / second_id / "session.json").is_file()
    trash_entries = list((tmp_path / ".trash").iterdir())
    assert len(trash_entries) == 1
    assert trash_entries[0].name.startswith(first_id)


def test_stale_active_manifest_is_read_as_failed(tmp_path: Path) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    _session(tmp_path, session_id)
    store = LocalSessionStore(tmp_path)

    stale = store.get_session(session_id, active_session_id=None)
    active = store.get_session(session_id, active_session_id=session_id)

    assert stale.status.value == "failed"
    assert stale.completed_at is None
    assert active.status.value == "active"
    assert active.active_capture_id is not None


def test_domain_and_application_packages_have_inward_dependencies() -> None:
    root = Path(__file__).parents[1] / "src" / "atpiano" / "product"
    forbidden = {
        "atpiano.corrected",
        "atpiano.corrected_workbench",
        "atpiano.product.adapters",
        "http",
        "pathlib",
    }
    for package in ("domain", "application"):
        for path in (root / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            } | {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            assert not any(
                imported == blocked or imported.startswith(f"{blocked}.")
                for imported in imports
                for blocked in forbidden
            ), (path, imports)
