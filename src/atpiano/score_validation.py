"""Read-only structural and headed-browser validation of retained scores."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from atpiano.adapters.local_sessions import LocalSessionStore
from atpiano.application.errors import AuthenticationError
from atpiano.contracts.schemas import SessionStatus
from atpiano.family_server import LOCAL_SESSION_COOKIE, SECURE_SESSION_COOKIE
from atpiano.identity_cli import identity_service
from atpiano.notation import summarize_musicxml
from atpiano.score_alignment import (
    SCORE_ALIGNMENT_MAPPING,
    SCORE_ALIGNMENT_SCHEMA,
    validate_score_alignment,
)
from atpiano.score_snapshot import SCORE_SNAPSHOT_SCHEMA
from atpiano.util import (
    git_revision,
    git_worktree_dirty,
    read_json,
    sha256_file,
    write_json,
)

SCORE_VALIDATION_REPORT_SCHEMA = "atpiano.score-validation-report.v1"
SCORE_BROWSER_REPORT_SCHEMA = "atpiano.score-browser-validation.v1"
SCORE_FAILURE_CATEGORIES = frozenset(
    {
        "missing-score",
        "artifact-integrity",
        "musicxml-parse",
        "alignment-compatibility",
        "alignment-order",
        "inline-render",
        "cursor-movement",
        "reader-render",
        "browser-runtime",
        "target-changed",
        "operator-cleanup",
    }
)


@dataclass(frozen=True)
class FrozenScoreTarget:
    session_id: str
    display_name: str
    pointer_path: Path
    pointer_sha256: str
    musicxml_path: Path
    alignment_path: Path
    source_notes_path: Path
    browser: dict[str, Any]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _running_origin(value: str) -> str:
    parsed = urlsplit(value)
    loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if (
        parsed.scheme not in ({"http", "https"} if loopback else {"https"})
        or parsed.hostname is None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base URL must be an HTTPS origin or an HTTP loopback origin"
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def _failure(
    category: str,
    message: str,
    *,
    stage: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if category not in SCORE_FAILURE_CATEGORIES:
        raise ValueError(f"unknown score validation category: {category}")
    return {
        "category": category,
        "stage": stage,
        "message": message,
        "details": details or {},
    }


def _resolved_session_path(
    session_directory: Path,
    relative: object,
    *,
    field: str,
) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"{field} path is missing")
    candidate = (session_directory / relative).resolve()
    if (
        candidate == session_directory
        or not candidate.is_relative_to(session_directory)
    ):
        raise ValueError(f"{field} path leaves its session")
    return candidate


def _selected_score_record(pointer: dict[str, Any]) -> dict[str, Any]:
    variants = [
        *(
            [pointer["baseline"]]
            if isinstance(pointer.get("baseline"), dict)
            else []
        ),
        *(
            pointer["variants"]
            if isinstance(pointer.get("variants"), list)
            else []
        ),
    ]
    if variants:
        selected_id = pointer.get("selected_variant_id")
        selected = next(
            (
                value
                for value in variants
                if isinstance(value, dict)
                and value.get("variant_id") == selected_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("selected score variant is missing")
        return selected
    return pointer


def _verify_declared_artifact(
    record: object,
    path: Path,
    *,
    field: str,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"{field} metadata is missing")
    if not path.is_file():
        raise FileNotFoundError(f"{field} artifact does not exist")
    expected_sha256 = record.get("sha256")
    actual_sha256 = sha256_file(path)
    if expected_sha256 != actual_sha256:
        raise ValueError(f"{field} SHA-256 differs")
    expected_bytes = record.get("bytes")
    if expected_bytes is not None and expected_bytes != path.stat().st_size:
        raise ValueError(f"{field} byte count differs")
    return {
        "path": str(path),
        "sha256": actual_sha256,
        "byte_count": path.stat().st_size,
    }


def _alignment_failure_category(error: Exception) -> str:
    message = str(error).lower()
    if any(
        fragment in message
        for fragment in (
            "order",
            "monotonic",
            "source identity differs",
            "source note row",
            "must account for every source note",
        )
    ):
        return "alignment-order"
    return "alignment-compatibility"


def _cursor_samples(alignment: dict[str, Any]) -> list[int]:
    samples = sorted(
        {
            int(row["onset_sample"])
            for row in alignment.get("rows", [])
            if isinstance(row, dict)
            and row.get("status") == "mapped"
            and isinstance(row.get("onset_sample"), int)
        }
    )
    if not samples:
        raise ValueError("score alignment has no mapped cursor attacks")
    selected = [samples[0], samples[len(samples) // 2], samples[-1]]
    return list(dict.fromkeys(selected))


def _complete_sessions(store: LocalSessionStore) -> list[Any]:
    sessions: list[Any] = []
    cursor = None
    while True:
        page = store.list_sessions(cursor=cursor, limit=500)
        sessions.extend(
            session
            for session in page.items
            if session.status is SessionStatus.COMPLETE
        )
        if page.next_cursor is None:
            return sessions
        cursor = page.next_cursor


def _freeze_score(
    store: LocalSessionStore,
    session: Any,
) -> tuple[dict[str, Any], FrozenScoreTarget | None]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "session_id": session.session_id,
        "display_name": session.display_name or session.session_id,
        "sample_rate_hz": session.sample_rate_hz,
        "source_frame_count": session.source_frame_count,
        "note_count": session.corrected_note_count,
        "status": "failed",
        "duration_s": 0.0,
        "failures": [],
        "warnings": [],
        "structural": None,
        "browsers": [],
    }
    session_directory = store.resolve(session.session_id)
    pointer_path = session_directory / "score" / "current.json"
    if not pointer_path.is_file():
        result["failures"].append(
            _failure(
                "missing-score",
                "session has no current score snapshot",
                stage="inventory",
            )
        )
        result["duration_s"] = time.perf_counter() - started
        return result, None
    try:
        pointer_sha256 = sha256_file(pointer_path)
        pointer = read_json(pointer_path)
        if (
            pointer.get("schema_version") != SCORE_SNAPSHOT_SCHEMA
            or pointer.get("session_id") != session.session_id
        ):
            raise ValueError("current score snapshot identity is incompatible")
        if pointer.get("note_count") != session.corrected_note_count:
            raise ValueError("current score note count differs from its session")
        commit_sample = pointer.get("commit_sample")
        if (
            not isinstance(commit_sample, int)
            or commit_sample < 0
            or (
                session.source_frame_count > 0
                and commit_sample > session.source_frame_count
            )
        ):
            raise ValueError("current score horizon differs from its session")
        selected = _selected_score_record(pointer)
        musicxml_record = selected.get("musicxml")
        alignment_record = selected.get("alignment")
        source_record = pointer.get("source_notes")
        if not isinstance(musicxml_record, dict):
            raise ValueError("selected MusicXML metadata is missing")
        if not isinstance(alignment_record, dict):
            raise ValueError("selected alignment metadata is missing")
        if not isinstance(source_record, dict):
            raise ValueError("source-note metadata is missing")
        musicxml_path = _resolved_session_path(
            session_directory,
            musicxml_record.get("path"),
            field="MusicXML",
        )
        alignment_path = _resolved_session_path(
            session_directory,
            alignment_record.get("path"),
            field="alignment",
        )
        source_notes_path = _resolved_session_path(
            session_directory,
            source_record.get("path"),
            field="source notes",
        )
        musicxml_artifact = _verify_declared_artifact(
            musicxml_record,
            musicxml_path,
            field="MusicXML",
        )
        alignment_artifact = _verify_declared_artifact(
            alignment_record,
            alignment_path,
            field="alignment",
        )
        source_artifact = _verify_declared_artifact(
            source_record,
            source_notes_path,
            field="source notes",
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        result["failures"].append(
            _failure(
                "artifact-integrity",
                str(error),
                stage="artifact-integrity",
            )
        )
        result["duration_s"] = time.perf_counter() - started
        return result, None

    try:
        musicxml_summary = summarize_musicxml(musicxml_path.read_bytes())
        if (
            musicxml_summary["root"] != "score-partwise"
            or int(musicxml_summary["pitched_note_elements"]) <= 0
        ):
            raise ValueError(
                "MusicXML must be a partwise score with pitched content"
            )
    except (OSError, TypeError, ValueError) as error:
        result["failures"].append(
            _failure(
                "musicxml-parse",
                str(error),
                stage="musicxml",
            )
        )
        result["duration_s"] = time.perf_counter() - started
        return result, None

    try:
        alignment = read_json(alignment_path)
        source_notes = read_json(source_notes_path)
        if alignment.get("schema_version") != SCORE_ALIGNMENT_SCHEMA:
            raise ValueError("score alignment schema is unsupported")
        if alignment.get("mapping") != SCORE_ALIGNMENT_MAPPING:
            raise ValueError("score alignment mapping is unsupported")
        if alignment.get("session_id") != session.session_id:
            raise ValueError("score alignment belongs to another session")
        if alignment.get("sample_rate_hz") != session.sample_rate_hz:
            raise ValueError("score alignment sample rate differs")
        if source_notes.get("session_id") != session.session_id:
            raise ValueError("score source notes belong to another session")
        alignment_musicxml = alignment.get("musicxml")
        if not isinstance(alignment_musicxml, dict):
            raise ValueError("score alignment MusicXML identity is missing")
        if (
            alignment_musicxml.get("sha256")
            != musicxml_artifact["sha256"]
        ):
            raise ValueError("score alignment belongs to another MusicXML")
        alignment_summary = validate_score_alignment(
            alignment,
            source_notes_path=source_notes_path,
            musicxml_path=musicxml_path,
        )
        cursor_samples = _cursor_samples(alignment)
    except (KeyError, OSError, TypeError, ValueError) as error:
        result["failures"].append(
            _failure(
                _alignment_failure_category(error),
                str(error),
                stage="alignment",
            )
        )
        result["duration_s"] = time.perf_counter() - started
        return result, None

    try:
        variants = store.score_variants(session.session_id)
        selected_variant = next(
            (variant for variant in variants.items if variant.selected),
            None,
        )
        if selected_variant is None:
            raise ValueError("selected score variant is absent from the catalog")
        musicxml_catalog = store.get_artifact(
            session.session_id,
            selected_variant.musicxml_artifact_id,
        )
        alignment_catalog = store.get_artifact(
            session.session_id,
            selected_variant.alignment_artifact_id,
        )
        if (
            musicxml_catalog.sha256 != musicxml_artifact["sha256"]
            or musicxml_catalog.byte_count != musicxml_artifact["byte_count"]
            or alignment_catalog.sha256 != alignment_artifact["sha256"]
            or alignment_catalog.byte_count != alignment_artifact["byte_count"]
        ):
            raise ValueError("selected score artifacts differ from the catalog")
        freshness = variants.freshness.model_dump(mode="json")
        producer = (
            variants.producer.model_dump(mode="json")
            if variants.producer is not None
            else None
        )
        if freshness["status"] != "current":
            result["warnings"].append(
                {
                    "category": "score-freshness",
                    "message": (
                        "selected score is "
                        f"{freshness['status']}: {freshness['reason']}"
                    ),
                }
            )
    except (KeyError, OSError, TypeError, ValueError) as error:
        result["failures"].append(
            _failure(
                "artifact-integrity",
                str(error),
                stage="catalog",
            )
        )
        result["duration_s"] = time.perf_counter() - started
        return result, None

    browser = {
        "session_id": session.session_id,
        "display_name": result["display_name"],
        "source_frame_count": session.source_frame_count,
        "sample_rate_hz": session.sample_rate_hz,
        "source_horizon_sample": int(pointer["commit_sample"]),
        "musicxml_artifact_id": selected_variant.musicxml_artifact_id,
        "musicxml_sha256": musicxml_artifact["sha256"],
        "cursor_samples": cursor_samples,
    }
    result["structural"] = {
        "pointer_sha256": pointer_sha256,
        "commit_sample": int(pointer["commit_sample"]),
        "note_count": int(pointer["note_count"]),
        "variant_id": selected_variant.score_variant_id,
        "musicxml_artifact_id": selected_variant.musicxml_artifact_id,
        "alignment_artifact_id": selected_variant.alignment_artifact_id,
        "musicxml": {
            **musicxml_artifact,
            "summary": musicxml_summary,
        },
        "alignment": {
            **alignment_artifact,
            "summary": alignment_summary,
        },
        "source_notes": source_artifact,
        "cursor_samples": cursor_samples,
        "freshness": freshness,
        "producer": producer,
    }
    result["status"] = "passed"
    result["duration_s"] = time.perf_counter() - started
    return result, FrozenScoreTarget(
        session_id=session.session_id,
        display_name=result["display_name"],
        pointer_path=pointer_path,
        pointer_sha256=pointer_sha256,
        musicxml_path=musicxml_path,
        alignment_path=alignment_path,
        source_notes_path=source_notes_path,
        browser=browser,
    )


def _browser_runner_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "app"
        / "scripts"
        / "validate-scores.mjs"
    )


def _run_browser_validation(
    *,
    workspace: Path,
    base_url: str,
    targets: Sequence[FrozenScoreTarget],
    browsers: Sequence[str],
    headed: bool,
    timeout_s: float,
    failure_directory: Path,
    username: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    origin = _running_origin(base_url)
    identity, engine = identity_service(workspace)
    issued = None
    operator: dict[str, Any] = {
        "issued": False,
        "username": None,
        "revoked": False,
    }
    browser_report: dict[str, Any] = {
        "schema_version": SCORE_BROWSER_REPORT_SCHEMA,
        "status": "failed",
        "browsers": [],
        "failures": [],
    }
    try:
        issued = identity.issue_local_operator_session(username)
        operator["issued"] = True
        operator["username"] = issued.principal.username
        payload = {
            "schema_version": SCORE_BROWSER_REPORT_SCHEMA,
            "base_url": origin,
            "cookie_name": (
                SECURE_SESSION_COOKIE
                if urlsplit(origin).scheme == "https"
                else LOCAL_SESSION_COOKIE
            ),
            "token": issued.token,
            "browsers": list(browsers),
            "headless": not headed,
            "timeout_ms": round(timeout_s * 1000),
            "failure_directory": str(failure_directory),
            "targets": [target.browser for target in targets],
        }
        process_timeout = max(
            60.0,
            timeout_s * max(1, len(targets)) * max(1, len(browsers))
            + 60.0,
        )
        try:
            completed = subprocess.run(
                ["node", str(_browser_runner_path())],
                cwd=Path(__file__).resolve().parents[2],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False,
                timeout=process_timeout,
            )
        except subprocess.TimeoutExpired:
            browser_report["failures"].append(
                _failure(
                    "browser-runtime",
                    f"browser validator exceeded {process_timeout:.0f} seconds",
                    stage="browser-process",
                )
            )
            return browser_report, operator
        try:
            parsed = json.loads(completed.stdout)
            if parsed.get("schema_version") != SCORE_BROWSER_REPORT_SCHEMA:
                raise ValueError("browser report schema is incompatible")
            browser_report = parsed
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            detail = completed.stderr.strip()[-2000:]
            browser_report["failures"].append(
                _failure(
                    "browser-runtime",
                    f"browser validator returned no valid report: {error}",
                    stage="browser-process",
                    details={"stderr": detail},
                )
            )
        return browser_report, operator
    finally:
        if issued is not None:
            try:
                identity.logout(issued.token)
                try:
                    identity.authenticate(issued.token)
                except AuthenticationError:
                    operator["revoked"] = True
                else:
                    operator["cleanup_error"] = (
                        "local operator session remained authenticated"
                    )
            except Exception as error:
                operator["cleanup_error"] = str(error)
        engine.dispose()


def _merge_browser_results(
    session_reports: list[dict[str, Any]],
    browser_report: dict[str, Any],
) -> None:
    by_session = {
        report["session_id"]: report
        for report in session_reports
    }
    for browser in browser_report.get("browsers", []):
        browser_name = browser.get("name")
        for result in browser.get("sessions", []):
            session = by_session.get(result.get("session_id"))
            if session is None:
                continue
            session["browsers"].append(
                {
                    **result,
                    "browser": browser_name,
                    "browser_version": browser.get("version"),
                }
            )
            session["failures"].extend(result.get("failures", []))
            if result.get("status") != "passed":
                session["status"] = "failed"


def validate_score_workspace(
    workspace_directory: Path,
    *,
    base_url: str | None = None,
    browsers: Sequence[str] = (),
    headed: bool = True,
    structural_only: bool = False,
    output_path: Path | None = None,
    timeout_s: float = 45.0,
    username: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Validate one frozen inventory without changing retained session data."""

    started_clock = time.perf_counter()
    started_at = datetime.now(timezone.utc)
    workspace = workspace_directory.resolve()
    repository_root = Path(__file__).resolve().parents[2]
    if timeout_s <= 0:
        raise ValueError("score validation timeout must be positive")
    unknown_browsers = set(browsers) - {"chromium", "webkit"}
    if unknown_browsers:
        raise ValueError(
            "unsupported score validation browsers: "
            + ", ".join(sorted(unknown_browsers))
        )
    if structural_only and browsers:
        raise ValueError("structural-only validation cannot launch browsers")
    if browsers and base_url is None:
        raise ValueError("browser validation requires --base-url")
    if not structural_only and not browsers:
        structural_only = True
    report_path = (
        output_path.resolve()
        if output_path is not None
        else (
            repository_root
            / "results"
            / "score-validation"
            / _timestamp()
            / "report.json"
        )
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    failure_directory = report_path.parent / "failures"

    store = LocalSessionStore(workspace)
    sessions = _complete_sessions(store)
    session_reports: list[dict[str, Any]] = []
    targets: list[FrozenScoreTarget] = []
    for session in sessions:
        session_report, target = _freeze_score(store, session)
        session_reports.append(session_report)
        if target is not None:
            targets.append(target)

    browser_report = None
    operator = {
        "issued": False,
        "username": None,
        "revoked": False,
    }
    global_failures: list[dict[str, Any]] = []
    if not structural_only:
        try:
            browser_report, operator = _run_browser_validation(
                workspace=workspace,
                base_url=str(base_url),
                targets=targets,
                browsers=browsers,
                headed=headed,
                timeout_s=timeout_s,
                failure_directory=failure_directory,
                username=username,
            )
        except Exception as error:
            browser_report = {
                "schema_version": SCORE_BROWSER_REPORT_SCHEMA,
                "status": "failed",
                "browsers": [],
                "failures": [
                    _failure(
                        "browser-runtime",
                        str(error),
                        stage="browser-process",
                    )
                ],
            }
        _merge_browser_results(session_reports, browser_report)
        global_failures.extend(browser_report.get("failures", []))
        if operator.get("issued") and not operator.get("revoked"):
            global_failures.append(
                _failure(
                    "operator-cleanup",
                    str(
                        operator.get(
                            "cleanup_error",
                            "operator session revocation was not verified",
                        )
                    ),
                    stage="operator-cleanup",
                )
            )

    for target in targets:
        try:
            current_sha256 = sha256_file(target.pointer_path)
        except OSError as error:
            current_sha256 = None
            message = str(error)
        else:
            message = "current score pointer changed during validation"
        if current_sha256 != target.pointer_sha256:
            session_report = next(
                value
                for value in session_reports
                if value["session_id"] == target.session_id
            )
            session_report["status"] = "failed"
            session_report["failures"].append(
                _failure(
                    "target-changed",
                    message,
                    stage="target-recheck",
                    details={
                        "expected_pointer_sha256": target.pointer_sha256,
                        "actual_pointer_sha256": current_sha256,
                    },
                )
            )

    failures = [
        failure
        for session in session_reports
        for failure in session["failures"]
    ]
    failures.extend(global_failures)
    completed_at = datetime.now(timezone.utc)
    report = {
        "schema_version": SCORE_VALIDATION_REPORT_SCHEMA,
        "status": "passed" if not failures else "failed",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_s": time.perf_counter() - started_clock,
        "arguments": {
            "workspace": str(workspace),
            "base_url": base_url,
            "browsers": list(browsers),
            "headed": headed,
            "structural_only": structural_only,
            "timeout_s": timeout_s,
        },
        "application": {
            "revision": git_revision(cwd=repository_root),
            "dirty": git_worktree_dirty(cwd=repository_root),
        },
        "inventory": {
            "complete_nontrashed_sessions": len(sessions),
            "frozen_score_targets": len(targets),
        },
        "operator": operator,
        "browser_run": browser_report,
        "sessions": session_reports,
        "failures": global_failures,
        "summary": {
            "sessions": len(session_reports),
            "passed_sessions": sum(
                session["status"] == "passed"
                for session in session_reports
            ),
            "failed_sessions": sum(
                session["status"] != "passed"
                for session in session_reports
            ),
            "browser_checks": sum(
                len(session["browsers"])
                for session in session_reports
            ),
            "failure_count": len(failures),
        },
    }
    write_json(report_path, report)
    return report_path, report


def run_score_validation(args: object) -> int:
    output_path, report = validate_score_workspace(
        Path(getattr(args, "workspace")),
        base_url=getattr(args, "base_url"),
        browsers=tuple(getattr(args, "browser")),
        headed=bool(getattr(args, "headed")),
        structural_only=bool(getattr(args, "structural_only")),
        output_path=getattr(args, "output"),
        timeout_s=float(getattr(args, "timeout_seconds")),
        username=getattr(args, "as_user"),
    )
    print(output_path)
    print(
        "score validation: "
        f"{report['status']} "
        f"({report['summary']['passed_sessions']}/"
        f"{report['summary']['sessions']} sessions, "
        f"{report['summary']['browser_checks']} browser checks)"
    )
    return 0 if report["status"] == "passed" else 1
