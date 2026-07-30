from __future__ import annotations

import ast
from pathlib import Path

import pytest

from atpiano.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalSessionConflictError,
    LocalSessionNotFoundError,
    LocalSessionStore,
    _score_snapshot_provenance,
)
from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.corrected_export import write_corrected_exports
from atpiano.live import PcmBlock
from atpiano.util import sha256_file, write_json


def _producer(revision: int) -> dict[str, object]:
    return {
        "schema_version": "atpiano.score-producer.v1",
        "pipeline_revision": revision,
        "pipeline_fingerprint": "a" * 64,
        "application_version": "0.1.0",
        "application_revision": "b" * 40,
        "application_dirty": False,
        "execution": "pinned-runtime",
        "adapter_schema": "atpiano.midi2score-adapter.v1",
        "alignment_schema": "atpiano.score-alignment.v2",
        "postprocessor_version": "deterministic-engraving-v1",
        "model_repository_commit": "c" * 40,
        "model_checkpoint_sha256": "d" * 64,
    }


@pytest.mark.parametrize(
    ("alignment_schema", "producer", "status", "reason", "refresh"),
    [
        (
            "atpiano.score-alignment.v2",
            _producer(3),
            "current",
            "current",
            False,
        ),
        (
            "atpiano.score-alignment.v2",
            _producer(2),
            "older-compatible",
            "pipeline-outdated",
            True,
        ),
        (
            "atpiano.score-alignment.v2",
            _producer(4),
            "incompatible",
            "pipeline-newer",
            False,
        ),
        (
            "atpiano.score-alignment.v2",
            None,
            "legacy-unknown",
            "legacy-provenance-missing",
            True,
        ),
        (
            "atpiano.score-alignment.v1",
            None,
            "incompatible",
            "alignment-schema-unsupported",
            True,
        ),
        (
            "atpiano.score-alignment.v2",
            {"schema_version": "atpiano.score-producer.v9"},
            "incompatible",
            "producer-schema-unsupported",
            True,
        ),
    ],
)
def test_score_snapshot_provenance_classifies_retained_evidence(
    alignment_schema: str,
    producer: dict[str, object] | None,
    status: str,
    reason: str,
    refresh: bool,
) -> None:
    pointer: dict[str, object] = {
        "alignment": {"schema_version": alignment_schema},
    }
    if producer is not None:
        pointer["producer"] = producer

    parsed, freshness = _score_snapshot_provenance(pointer)

    assert freshness.status.value == status
    assert freshness.reason.value == reason
    assert freshness.refresh_recommended is refresh
    assert (parsed.pipeline_revision if parsed else None) == (
        producer.get("pipeline_revision")
        if producer is not None
        and producer.get("schema_version") == "atpiano.score-producer.v1"
        else None
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
    workspace = store.workspace()
    assert workspace.mode.value == "local"
    assert workspace.name == "On this device"


def test_local_reader_converts_events_and_horizons_to_contract(
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
    summary = store.get_session(session_id)
    assert summary.recognized_note_count == 1
    assert summary.corrected_note_count == 1


def test_local_annotations_preserve_application_metadata(
    tmp_path: Path,
) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    session = _session(tmp_path, session_id)
    session.finalize()
    write_json(
        session.directory / "application.json",
        {
            "schema_version": "atpiano.application-session.v1",
            "created_at": "2026-07-26T10:00:00Z",
            "storage": {"compact_recording": True},
        },
    )
    store = LocalSessionStore(tmp_path)

    result = store.update_session_annotation(
        session_id,
        display_name="  Quiet chords  ",
    )
    application = store.read_document(session_id, "application.json")

    assert result.display_name == "Quiet chords"
    assert store.get_session(session_id).display_name == "Quiet chords"
    assert application["storage"] == {"compact_recording": True}
    assert application["annotations"]["display_name"] == "Quiet chords"


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
    with pytest.raises(LocalSessionNotFoundError):
        store.get_artifact_with_path(session_id, "artifact:missing")


def test_exact_retained_score_artifact_survives_current_refresh(
    tmp_path: Path,
) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    session = _session(tmp_path, session_id)
    session.finalize()
    score_root = session.directory / "score"

    def snapshot(commit_sample: int, pitch: str) -> tuple[dict[str, object], Path]:
        relative_root = Path("score") / "snapshots" / f"{commit_sample:016d}"
        directory = session.directory / relative_root
        directory.mkdir(parents=True)
        musicxml = directory / "score.musicxml"
        musicxml.write_text(
            "<score-partwise version=\"4.0\">"
            f"<part-list/><part id=\"P1\"><measure number=\"1\">{pitch}</measure>"
            "</part></score-partwise>",
            encoding="utf-8",
        )
        midi = directory / "committed.mid"
        midi.write_bytes(b"MThd")
        alignment = directory / "alignment.json"
        write_json(alignment, {"snapshot": commit_sample})
        manifest: dict[str, object] = {
            "schema_version": "atpiano.committed-score-snapshot.v1",
            "session_id": session_id,
            "commit_sample": commit_sample,
            "note_count": 1,
            "midi": {
                "path": (relative_root / midi.name).as_posix(),
                "sha256": sha256_file(midi),
            },
            "musicxml": {
                "path": (relative_root / musicxml.name).as_posix(),
                "sha256": sha256_file(musicxml),
                "summary": {"pitched_note_elements": 1},
            },
            "alignment": {
                "path": (relative_root / alignment.name).as_posix(),
                "sha256": sha256_file(alignment),
            },
        }
        write_json(directory / "manifest.json", manifest)
        return manifest, musicxml

    _, first_path = snapshot(40, "<pitch>C4</pitch>")
    second_manifest, second_path = snapshot(80, "<pitch>D4</pitch>")
    write_json(score_root / "current.json", second_manifest)
    store = LocalSessionStore(tmp_path)

    current = next(
        artifact
        for artifact in store.list_artifacts(session_id).items
        if artifact.kind.value == "musicxml"
    )
    first_id = f"artifact:{sha256_file(first_path)[:24]}"
    retained, retained_path = store.get_artifact_with_path(session_id, first_id)
    first_alignment = first_path.with_name("alignment.json")
    first_alignment_id = f"artifact:{sha256_file(first_alignment)[:24]}"
    retained_alignment, retained_alignment_path = (
        store.get_artifact_with_path(session_id, first_alignment_id)
    )

    assert current.sha256 == sha256_file(second_path)
    assert current.artifact_id != first_id
    assert retained.sha256 == sha256_file(first_path)
    assert retained.source_horizon_sample == 40
    assert retained_path == first_path
    assert retained_alignment.kind.value == "score-alignment"
    assert retained_alignment.source_horizon_sample == 40
    assert retained_alignment_path == first_alignment
    assert all(
        artifact.artifact_id != first_id
        for artifact in store.list_artifacts(session_id).items
    )


def test_audio_artifacts_expose_each_segment_source_horizon(tmp_path: Path) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    session = CorrectedSession(
        tmp_path / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        segment_s=0.001,
        minimum_free_bytes=0,
    )
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=12,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0015,
            pcm_s16le=b"\0\0" * 12,
        ),
        received_ns=1,
    )
    session.finalize()

    audio = [
        artifact
        for artifact in LocalSessionStore(tmp_path).list_artifacts(session_id).items
        if artifact.kind.value == "audio"
    ]

    assert [artifact.filename for artifact in audio] == ["000000.wav", "000001.wav"]
    assert [artifact.source_horizon_sample for artifact in audio] == [8, 12]


def test_local_catalog_hides_pathological_score_snapshot(tmp_path: Path) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    session = _session(tmp_path, session_id)
    session.finalize()
    score_root = tmp_path / session_id / "score"
    score_root.mkdir()
    write_json(
        score_root / "current.json",
        {
            "note_count": 13,
            "musicxml": {
                "summary": {
                    "pitched_note_elements": 491,
                }
            },
        },
    )
    store = LocalSessionStore(tmp_path)

    assert "musicxml" not in {
        kind.value for kind in store.get_session(session_id).available_artifact_kinds
    }
    assert all(
        artifact.kind.value != "musicxml"
        for artifact in store.list_artifacts(session_id).items
    )
    with pytest.raises(LocalSessionNotFoundError):
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

    with pytest.raises(LocalSessionConflictError, match="active"):
        store.trash_session(
            first_id,
            active_session_id=first_id,
            running_score_session_id=None,
        )
    with pytest.raises(LocalSessionConflictError, match="score"):
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


def test_contract_schemas_do_not_depend_on_adapters() -> None:
    root = Path(__file__).parents[1] / "src" / "atpiano" / "contracts"
    forbidden = {
        "atpiano.adapters",
        "atpiano.corrected",
        "atpiano.corrected_workbench",
        "http",
        "pathlib",
    }
    path = root / "schemas.py"
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
