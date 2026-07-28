from __future__ import annotations

import ast
from pathlib import Path

import pytest

from atpiano.adapters.local_sessions import (
    LOCAL_WORKSPACE_ID,
    LocalSessionConflictError,
    LocalSessionStore,
)
from atpiano.application.sessions import SessionApplicationService
from atpiano.corrected import CorrectedSession
from atpiano.live import PcmBlock


def _session(workspace: Path, session_id: str) -> CorrectedSession:
    session = CorrectedSession(
        workspace / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        minimum_free_bytes=0,
    )
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=8,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.001,
            pcm_s16le=b"\0\0" * 8,
        ),
        received_ns=1,
    )
    session.finalize()
    return session


def test_application_sessions_read_and_delete_without_http(
    tmp_path: Path,
) -> None:
    older_id = "20260726T100000-aaaaaaaaaaaa"
    newer_id = "20260726T100001-bbbbbbbbbbbb"
    _session(tmp_path, older_id)
    _session(tmp_path, newer_id)
    service = SessionApplicationService(
        LocalSessionStore(tmp_path),
        workspace_id=LOCAL_WORKSPACE_ID,
    )

    page = service.list_sessions(
        LOCAL_WORKSPACE_ID,
        limit=1,
        active_session_id=None,
    )
    historical = service.get_session(LOCAL_WORKSPACE_ID, older_id)
    annotation = service.update_session_annotation(
        LOCAL_WORKSPACE_ID,
        older_id,
        display_name="  Evening idea  ",
    )
    renamed = service.get_session(LOCAL_WORKSPACE_ID, older_id)

    assert [item.session_id for item in page.items] == [newer_id]
    assert historical.session_id == older_id
    assert annotation.display_name == "Evening idea"
    assert renamed.display_name == "Evening idea"
    assert (
        tmp_path / older_id / "application.json"
    ).read_text(encoding="utf-8").find('"Evening idea"') >= 0
    with pytest.raises(LookupError, match="workspace"):
        service.list_sessions("another-workspace")
    with pytest.raises(LocalSessionConflictError, match="active"):
        service.delete_session(
            LOCAL_WORKSPACE_ID,
            older_id,
            active_session_id=older_id,
            running_score_session_id=None,
        )
    result = service.delete_session(
        LOCAL_WORKSPACE_ID,
        older_id,
        active_session_id=None,
        running_score_session_id=None,
    )
    assert result.recoverable is True
    assert not (tmp_path / older_id).exists()


def test_application_package_has_no_transport_or_concrete_adapter_imports() -> None:
    root = Path(__file__).parents[1] / "src" / "atpiano" / "application"
    forbidden = {
        "atpiano.adapters",
        "atpiano.corrected_workbench",
        "fastapi",
        "http",
    }
    imports: set[tuple[Path, str]] = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update((path, module) for module in modules)
    assert not {
        (path, module)
        for path, module in imports
        for blocked in forbidden
        if module == blocked or module.startswith(f"{blocked}.")
    }
