from __future__ import annotations

import json
from pathlib import Path

from atpiano.cli import build_parser
from atpiano.migration_regression import (
    MIGRATION_REGRESSION_SCHEMA,
    RegressionLane,
    default_lanes,
    run_migration_regression,
)


def test_migration_regression_cli_has_explicit_output() -> None:
    args = build_parser().parse_args(
        ["migration-regression", "--output", "results/custom-report.json"]
    )

    assert args.command == "migration-regression"
    assert args.output == Path("results/custom-report.json")


def test_default_regression_lanes_cover_repository_checks() -> None:
    lanes = default_lanes()

    assert [lane.name for lane in lanes] == [
        "python-tests",
        "javascript-tests",
        "python-lint",
        "javascript-syntax",
        "git-whitespace",
    ]
    syntax_commands = next(
        lane.commands for lane in lanes if lane.name == "javascript-syntax"
    )
    checked_paths = {command[-1] for command in syntax_commands}
    assert "src/atpiano/web/app.js" in checked_paths
    assert "src/atpiano/web_v2/app.js" in checked_paths
    assert "tests/test_live_view.js" in checked_paths
    assert "tests/js/test_timeline.js" in checked_paths


def test_migration_regression_records_passes_and_manual_lanes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "report.json"
    lanes = (
        RegressionLane(
            "passing",
            (("git", "rev-parse", "--is-inside-work-tree"),),
        ),
    )

    path, report = run_migration_regression(output, lanes=lanes)

    assert path == output.resolve()
    assert report["schema_version"] == MIGRATION_REGRESSION_SCHEMA
    assert report["status"] == "passed"
    assert report["lanes"][0]["commands"][0]["exit_code"] == 0
    assert {lane["name"] for lane in report["not_run"]} == {
        "physical-microphone",
        "real-corrected-model",
        "internal-score-runtime",
        "long-soak",
    }
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_migration_regression_records_failure_and_stops_lane(
    tmp_path: Path,
) -> None:
    lanes = (
        RegressionLane(
            "failing",
            (
                ("git", "cat-file", "-e", "definitely-missing^{commit}"),
                ("git", "rev-parse", "HEAD"),
            ),
        ),
    )

    _, report = run_migration_regression(
        tmp_path / "failed.json",
        lanes=lanes,
    )

    assert report["status"] == "failed"
    assert report["lanes"][0]["status"] == "failed"
    assert len(report["lanes"][0]["commands"]) == 1
    assert report["lanes"][0]["commands"][0]["exit_code"] != 0
