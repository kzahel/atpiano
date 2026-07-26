"""Reproducible regression report for the product migration baseline."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atpiano.util import runtime_provenance, utc_now, write_json

MIGRATION_REGRESSION_SCHEMA = "atpiano.migration-regression.v1"


@dataclass(frozen=True)
class RegressionLane:
    name: str
    commands: tuple[tuple[str, ...], ...]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _javascript_paths(root: Path) -> tuple[Path, ...]:
    paths = (
        *root.glob("src/atpiano/web/*.js"),
        *root.glob("src/atpiano/web_v2/*.js"),
        *root.glob("tests/*.js"),
        *root.glob("tests/js/*.js"),
    )
    return tuple(sorted(path.relative_to(root) for path in paths))


def default_lanes(root: Path | None = None) -> tuple[RegressionLane, ...]:
    root = (root or _repository_root()).resolve()
    javascript = _javascript_paths(root)
    return (
        RegressionLane(
            "python-tests",
            ((sys.executable, "-m", "pytest", "-q"),),
        ),
        RegressionLane(
            "javascript-tests",
            (
                ("node", "tests/test_live_view.js"),
                ("node", "tests/js/test_timeline.js"),
            ),
        ),
        RegressionLane(
            "python-lint",
            ((sys.executable, "-m", "ruff", "check", "."),),
        ),
        RegressionLane(
            "javascript-syntax",
            tuple(("node", "--check", str(path)) for path in javascript),
        ),
        RegressionLane(
            "git-whitespace",
            (("git", "diff", "--check"),),
        ),
    )


def _run_command(
    command: Sequence[str],
    *,
    root: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"
    try:
        completed = subprocess.run(
            list(command),
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return {
            "command": list(command),
            "status": "failed",
            "exit_code": None,
            "duration_s": time.perf_counter() - started,
            "stdout": "",
            "stderr": f"{type(error).__name__}: {error}",
        }
    return {
        "command": list(command),
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "duration_s": time.perf_counter() - started,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _default_output_path(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / "results" / "migration-regression" / stamp / "report.json"


def run_migration_regression(
    output_path: Path | None = None,
    *,
    root: Path | None = None,
    lanes: Sequence[RegressionLane] | None = None,
) -> tuple[Path, dict[str, Any]]:
    root = (root or _repository_root()).resolve()
    output_path = (output_path or _default_output_path(root)).resolve()
    started_at = utc_now()
    lane_results: list[dict[str, Any]] = []
    overall_passed = True

    for lane in lanes or default_lanes(root):
        commands: list[dict[str, Any]] = []
        lane_passed = True
        for command in lane.commands:
            result = _run_command(command, root=root)
            commands.append(result)
            if result["status"] != "passed":
                lane_passed = False
                overall_passed = False
                break
        lane_results.append(
            {
                "name": lane.name,
                "status": "passed" if lane_passed else "failed",
                "commands": commands,
            }
        )

    report = {
        "schema_version": MIGRATION_REGRESSION_SCHEMA,
        "status": "passed" if overall_passed else "failed",
        "started_at": started_at,
        "completed_at": utc_now(),
        "repository_root": str(root),
        "runtime": runtime_provenance(),
        "lanes": lane_results,
        "not_run": [
            {
                "name": "physical-microphone",
                "reason": "requires a consenting human and target audio device",
            },
            {
                "name": "real-corrected-model",
                "reason": "requires the optional corrected dependency and checkpoint",
            },
            {
                "name": "internal-score-runtime",
                "reason": "requires an ignored runtime with unresolved upstream license",
            },
            {
                "name": "long-soak",
                "reason": "machine- and duration-dependent evidence is run separately",
            },
        ],
    }
    write_json(output_path, report)
    return output_path, report
