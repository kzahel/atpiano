"""Contract tests for the macOS-only public sharing service."""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT / "scripts" / "share-atpiano",
    ROOT / "scripts" / "share-atpiano-service",
    ROOT / "scripts" / "share-atpiano-service-runner",
)
PLIST_TEMPLATE = (
    ROOT
    / "scripts"
    / "launchd"
    / "com.graehlarts.atpiano-share.plist.in"
)


@pytest.mark.parametrize("script", SCRIPTS)
def test_share_scripts_fail_clearly_off_macos(
    tmp_path: Path,
    script: Path,
) -> None:
    fake_uname = tmp_path / "uname"
    fake_uname.write_text("#!/bin/sh\nprintf 'Linux\\n'\n")
    fake_uname.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment['PATH']}"

    result = subprocess.run(
        [script, "status"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 69
    assert "requires macOS" in result.stderr
    assert "detected Linux" in result.stderr


@pytest.mark.parametrize("script", SCRIPTS)
def test_share_scripts_have_valid_bash_syntax(script: Path) -> None:
    subprocess.run(["bash", "-n", script], check=True)


def test_launchd_template_is_on_demand_and_supervised() -> None:
    with PLIST_TEMPLATE.open("rb") as stream:
        job = plistlib.load(stream)

    assert job["Label"] == "com.graehlarts.atpiano-share"
    assert job["KeepAlive"] is True
    assert "RunAtLoad" not in job
    assert job["ProcessType"] == "Interactive"
    assert job["ProgramArguments"] == ["__ATPIANO_RUNNER__"]
    assert job["StandardOutPath"] == "/dev/null"
    assert job["StandardErrorPath"] == "/dev/null"
    assert (
        job["EnvironmentVariables"]["ATPIANO_SERVICE_STDOUT_LOG"]
        == "__ATPIANO_STDOUT_LOG__"
    )
    assert (
        job["EnvironmentVariables"]["ATPIANO_SERVICE_STDERR_LOG"]
        == "__ATPIANO_STDERR_LOG__"
    )
    assert (
        job["EnvironmentVariables"]["ATPIANO_SHARE_SCRIPT"]
        == "__ATPIANO_SHARE_SCRIPT__"
    )
    assert (
        job["EnvironmentVariables"]["ATPIANO_MODEL_IDLE_TIMEOUT_SECONDS"]
        == "__ATPIANO_MODEL_IDLE_TIMEOUT_SECONDS__"
    )
    assert (
        job["EnvironmentVariables"]["ATPIANO_BACKEND_PROFILE"]
        == "__ATPIANO_BACKEND_PROFILE__"
    )
    assert (
        job["EnvironmentVariables"]["ATPIANO_FAMILY_AUTH"]
        == "__ATPIANO_FAMILY_AUTH__"
    )
    assert (
        job["EnvironmentVariables"]["ATPIANO_SCORE_RUNTIME"]
        == "__ATPIANO_SCORE_RUNTIME__"
    )
