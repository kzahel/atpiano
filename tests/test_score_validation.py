from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import atpiano.score_validation as score_validation
from atpiano.application.errors import AuthenticationError
from atpiano.cli import build_parser
from atpiano.contracts.schemas import SessionStatus
from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.score_snapshot import generate_score_snapshot
from atpiano.util import sha256_file, write_json


def _event(session_id: str) -> dict[str, object]:
    return {
        "schema_version": CORRECTED_EVENT_SCHEMA,
        "session_id": session_id,
        "event_id": "validation-note",
        "revision": 1,
        "lane": "commit",
        "lifecycle": "committed",
        "pitch": 60,
        "onset_sample": 100,
        "offset_sample": 300,
        "offset_state": "closed",
        "velocity": 80,
        "confidence": 0.9,
    }


def _score_runner(
    input_midi: Path,
    input_notes: Path,
    output_musicxml: Path,
    output_alignment: Path,
    runtime_directory: Path,
) -> dict[str, Any]:
    assert input_midi.is_file()
    assert runtime_directory.name == "runtime"
    source = json.loads(input_notes.read_text(encoding="utf-8"))
    output_musicxml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>1</divisions></attributes>
    <note id="validation-note">
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>1</duration><voice>1</voice>
    </note>
  </measure></part>
</score-partwise>
""",
        encoding="utf-8",
    )
    note = source["notes"][0]
    write_json(
        output_alignment,
        {
            "schema_version": "atpiano.score-alignment.v2",
            "session_id": source["session_id"],
            "sample_rate_hz": source["sample_rate_hz"],
            "source": {
                "schema_version": source["schema_version"],
                "sha256": sha256_file(input_notes),
            },
            "musicxml": {"sha256": sha256_file(output_musicxml)},
            "mapping": {
                "algorithm": "monotonic-exact-pitch-lcs-v1",
                "source_order": "onset-sample,pitch,duration,source-index",
                "score_order": "attack-quarters,pitch,output-index",
            },
            "summary": {
                "source_notes": 1,
                "mapped_source_notes": 1,
                "unmatched_source_notes": 0,
                "musicxml_note_elements": 1,
                "inserted_score_note_elements": 0,
            },
            "rows": [
                {
                    "source_index": 0,
                    "event_id": note["event_id"],
                    "pitch": note["pitch"],
                    "onset_sample": note["onset_sample"],
                    "offset_sample": note["offset_sample"],
                    "status": "mapped",
                    "score_time_quarters": {
                        "numerator": 0,
                        "denominator": 1,
                    },
                    "segments": [
                        {
                            "musicxml_note_id": "validation-note",
                            "part": 1,
                            "pitch": note["pitch"],
                            "score_time_quarters": {
                                "numerator": 0,
                                "denominator": 1,
                            },
                            "score_duration_quarters": {
                                "numerator": 1,
                                "denominator": 1,
                            },
                            "tie": None,
                        }
                    ],
                }
            ],
            "inserted_score_segments": [],
        },
    )
    return {"schema_version": "test-score-runner.v1"}


def _completed_session(
    workspace: Path,
    session_id: str,
    *,
    score: bool,
) -> Path:
    directory = workspace / session_id
    session = CorrectedSession(
        directory,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        minimum_free_bytes=0,
    )
    session.append_events([_event(session_id)])
    if score:
        generate_score_snapshot(
            directory,
            workspace / "runtime",
            commit_sample=300,
            runner=_score_runner,
        )
    session.finalize()
    return directory


def test_structural_validator_reports_every_complete_session(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    scored = _completed_session(
        workspace,
        "20260728T170000-aaaaaaaaaaaa",
        score=True,
    )
    _completed_session(
        workspace,
        "20260728T170100-bbbbbbbbbbbb",
        score=False,
    )
    pointer = scored / "score" / "current.json"
    pointer_sha256 = sha256_file(pointer)

    output, report = score_validation.validate_score_workspace(
        workspace,
        structural_only=True,
        output_path=tmp_path / "report.json",
    )

    assert output == tmp_path / "report.json"
    assert report["status"] == "failed"
    assert report["inventory"] == {
        "complete_nontrashed_sessions": 2,
        "frozen_score_targets": 1,
    }
    assert report["summary"] == {
        "sessions": 2,
        "passed_sessions": 1,
        "failed_sessions": 1,
        "browser_checks": 0,
        "failure_count": 1,
    }
    scored_report = next(
        value
        for value in report["sessions"]
        if value["session_id"] == "20260728T170000-aaaaaaaaaaaa"
    )
    assert scored_report["status"] == "passed"
    assert scored_report["structural"]["cursor_samples"] == [100]
    missing_report = next(
        value
        for value in report["sessions"]
        if value["session_id"] == "20260728T170100-bbbbbbbbbbbb"
    )
    assert missing_report["failures"][0]["category"] == "missing-score"
    assert sha256_file(pointer) == pointer_sha256


def test_validator_detects_a_pointer_change_after_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    directory = _completed_session(
        workspace,
        "20260728T170200-cccccccccccc",
        score=True,
    )
    original = score_validation._freeze_score

    def freeze_then_change(store: Any, session: Any) -> Any:
        result = original(store, session)
        pointer = directory / "score" / "current.json"
        pointer.write_bytes(pointer.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(
        score_validation,
        "_freeze_score",
        freeze_then_change,
    )

    _, report = score_validation.validate_score_workspace(
        workspace,
        structural_only=True,
        output_path=tmp_path / "changed.json",
    )

    assert report["status"] == "failed"
    assert report["sessions"][0]["failures"][-1]["category"] == (
        "target-changed"
    )


def test_complete_inventory_follows_every_catalog_page() -> None:
    calls: list[str | None] = []
    complete = SimpleNamespace(status=SessionStatus.COMPLETE)
    recording = SimpleNamespace(status=SessionStatus.FAILED)

    class Store:
        def list_sessions(
            self,
            *,
            cursor: str | None,
            limit: int,
        ) -> SimpleNamespace:
            assert limit == 500
            calls.append(cursor)
            if cursor is None:
                return SimpleNamespace(
                    items=(complete, recording),
                    next_cursor="next",
                )
            assert cursor == "next"
            return SimpleNamespace(items=(complete,), next_cursor=None)

    assert score_validation._complete_sessions(Store()) == [
        complete,
        complete,
    ]
    assert calls == [None, "next"]


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("score alignment schema is unsupported", "alignment-compatibility"),
        ("score alignment source order is invalid", "alignment-order"),
        ("score alignment positions are not monotonic", "alignment-order"),
        ("score alignment belongs to another session", "alignment-compatibility"),
    ],
)
def test_alignment_failures_have_stable_categories(
    message: str,
    category: str,
) -> None:
    assert (
        score_validation._alignment_failure_category(ValueError(message))
        == category
    )


def test_validate_scores_cli_exposes_headed_and_structural_lanes() -> None:
    parser = build_parser()
    headed = parser.parse_args(
        [
            "validate-scores",
            "--browser",
            "chromium",
            "--browser",
            "webkit",
            "--base-url",
            "https://family.test",
            "--headed",
        ]
    )
    assert headed.browser == ["chromium", "webkit"]
    assert headed.headed is True
    structural = parser.parse_args(
        ["validate-scores", "--structural-only"]
    )
    assert structural.structural_only is True


@pytest.mark.parametrize(
    "category",
    sorted(score_validation.SCORE_FAILURE_CATEGORIES),
)
def test_score_failure_categories_are_stable(category: str) -> None:
    assert score_validation._failure(
        category,
        "synthetic failure",
        stage="test",
    )["category"] == category


class _FakeIdentity:
    def __init__(self) -> None:
        self.logout_tokens: list[str] = []

    def issue_local_operator_session(self, username: str | None) -> Any:
        assert username is None
        return SimpleNamespace(
            token="test-operator-token",
            principal=SimpleNamespace(username="owner"),
        )

    def logout(self, token: str) -> None:
        self.logout_tokens.append(token)

    def authenticate(self, token: str) -> None:
        assert token == "test-operator-token"
        raise AuthenticationError("revoked")


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


def _mock_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_FakeIdentity, _FakeEngine]:
    identity = _FakeIdentity()
    engine = _FakeEngine()
    monkeypatch.setattr(
        score_validation,
        "identity_service",
        lambda workspace: (identity, engine),
    )
    return identity, engine


def test_browser_timeout_revokes_operator_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    identity, engine = _mock_identity(monkeypatch)
    monkeypatch.setattr(
        score_validation.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired("node", 1)
        ),
    )

    report, operator = score_validation._run_browser_validation(
        workspace=tmp_path,
        base_url="https://family.test",
        targets=(),
        browsers=("chromium",),
        headed=False,
        timeout_s=1,
        failure_directory=tmp_path / "failures",
        username=None,
    )

    assert report["failures"][0]["category"] == "browser-runtime"
    assert operator["revoked"] is True
    assert identity.logout_tokens == ["test-operator-token"]
    assert engine.disposed is True


def test_browser_interrupt_revokes_operator_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    identity, engine = _mock_identity(monkeypatch)

    def interrupt(*args: Any, **kwargs: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(score_validation.subprocess, "run", interrupt)

    with pytest.raises(KeyboardInterrupt):
        score_validation._run_browser_validation(
            workspace=tmp_path,
            base_url="https://family.test",
            targets=(),
            browsers=("webkit",),
            headed=True,
            timeout_s=1,
            failure_directory=tmp_path / "failures",
            username=None,
        )

    assert identity.logout_tokens == ["test-operator-token"]
    assert engine.disposed is True


def test_score_validation_command_returns_nonzero_for_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        score_validation,
        "validate_score_workspace",
        lambda *args, **kwargs: (
            tmp_path / "report.json",
            {
                "status": "failed",
                "summary": {
                    "passed_sessions": 0,
                    "sessions": 1,
                    "browser_checks": 0,
                },
            },
        ),
    )
    args = SimpleNamespace(
        workspace=tmp_path,
        base_url=None,
        browser=[],
        headed=True,
        structural_only=True,
        output=None,
        timeout_seconds=45,
        as_user=None,
    )

    assert score_validation.run_score_validation(args) == 1
