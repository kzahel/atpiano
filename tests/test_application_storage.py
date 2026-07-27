from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from atpiano.adapters.local_storage import LocalStorageAdapter
from atpiano.application.storage import (
    DebugRetentionPolicy,
    StorageApplicationService,
)
from atpiano.corrected import CorrectedSession
from atpiano.live import PcmBlock
from atpiano.util import read_json


def _complete_session(
    workspace: Path,
    session_id: str,
    *,
    frame_count: int = 8_000,
) -> CorrectedSession:
    session = CorrectedSession(
        workspace / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        segment_s=0.5,
        minimum_free_bytes=0,
    )
    session.accept_pcm(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=frame_count,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0,
            pcm_s16le=b"\0\0" * frame_count,
        ),
        received_ns=1,
    )
    session.advance_commit(frame_count)
    session.begin_settling()
    session.complete_settlement()
    return session


class _SuccessfulMediaRunner:
    def __call__(
        self,
        arguments: list[str],
        **_options: Any,
    ) -> subprocess.CompletedProcess[str]:
        executable = Path(arguments[0]).name
        if executable == "ffprobe":
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "mp3",
                                "sample_rate": "8000",
                                "start_time": "0.0",
                                "duration": "1.0",
                            }
                        ],
                        "format": {"duration": "1.0"},
                    }
                ),
                stderr="",
            )
        if arguments[-1] != "-":
            Path(arguments[-1]).write_bytes(b"verified-compact-audio")
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout="",
            stderr="",
        )


def test_storage_service_compacts_only_after_verified_publication(
    tmp_path: Path,
) -> None:
    session_id = "20260727T100000-aaaaaaaaaaaa"
    session = _complete_session(tmp_path, session_id)
    (session.directory / "diagnostics").mkdir()
    (session.directory / "diagnostics" / "trace.jsonl").write_bytes(
        b"debug"
    )
    service = StorageApplicationService(
        LocalStorageAdapter(
            tmp_path,
            ffmpeg_executable="/fake/ffmpeg",
            ffprobe_executable="/fake/ffprobe",
            process_runner=_SuccessfulMediaRunner(),
        ),
        compact_recordings=True,
    )
    service.initialize_session(session_id)

    service.finalize_session(session)

    recording = read_json(session.directory / "recording.json")
    assert recording["state"] == "complete"
    assert recording["source"]["first_sample"] == 0
    assert recording["source"]["frame_count"] == 8_000
    assert recording["recording"]["source_frame_count"] == 8_000
    assert recording["verification"]["decoded_complete"] is True
    assert recording["raw_source"]["state"] == "retired"
    assert not list((session.directory / "audio").glob("*.wav"))
    assert not (session.directory / "audio" / "segments.jsonl").exists()
    assert not (session.directory / "diagnostics").exists()
    assert (
        read_json(session.directory / "pipeline-status.json")[
            "recording"
        ]["state"]
        == "complete"
    )

    accounting = service.accounting(
        session_id=session_id,
        duration_s=1.0,
        minimum_free_bytes=0,
    )
    assert (
        accounting["workspace"]["total_bytes"]
        == sum(accounting["workspace"]["bytes"].values())
    )
    assert accounting["current_session"]["bytes"]["recordings"] > 0
    assert accounting["current_session"]["bytes"]["temporary_raw"] == 0


def test_storage_accounting_accepts_warming_session_claim(
    tmp_path: Path,
) -> None:
    service = StorageApplicationService(LocalStorageAdapter(tmp_path))

    accounting = service.accounting(
        session_id="20260727T100000-aaaaaaaaaaaa",
        duration_s=0.0,
        minimum_free_bytes=0,
    )

    assert accounting["current_session"]["total_bytes"] == 0
    assert accounting["current_session"]["duration_s"] == 0.0


def test_encoder_failure_preserves_raw_and_reports_incomplete(
    tmp_path: Path,
) -> None:
    session_id = "20260727T100001-bbbbbbbbbbbb"
    session = _complete_session(tmp_path, session_id)

    def fail_encoder(
        arguments: list[str],
        **_options: Any,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, arguments)

    service = StorageApplicationService(
        LocalStorageAdapter(
            tmp_path,
            ffmpeg_executable="/fake/ffmpeg",
            ffprobe_executable="/fake/ffprobe",
            process_runner=fail_encoder,
        ),
        compact_recordings=True,
    )
    service.initialize_session(session_id)

    service.finalize_session(session)

    recording = read_json(session.directory / "recording.json")
    assert recording["state"] == "incomplete"
    assert recording["raw_source"]["state"] == "retained"
    assert recording["error"] == (
        "RuntimeError: FFmpeg did not publish playback audio"
    )
    assert list((session.directory / "audio").glob("*.wav"))
    assert (session.directory / "audio" / "segments.jsonl").is_file()
    assert (
        read_json(session.directory / "pipeline-status.json")[
            "final_state"
        ]
        == "complete"
    )


def test_decode_verification_failure_preserves_raw_and_compact_copy(
    tmp_path: Path,
) -> None:
    session_id = "20260727T100007-222222222222"
    session = _complete_session(tmp_path, session_id)

    class DecodeFailureRunner(_SuccessfulMediaRunner):
        def __call__(
            self,
            arguments: list[str],
            **options: Any,
        ) -> subprocess.CompletedProcess[str]:
            if arguments[-1] == "-":
                raise subprocess.CalledProcessError(1, arguments)
            return super().__call__(arguments, **options)

    service = StorageApplicationService(
        LocalStorageAdapter(
            tmp_path,
            ffmpeg_executable="/fake/ffmpeg",
            ffprobe_executable="/fake/ffprobe",
            process_runner=DecodeFailureRunner(),
        ),
        compact_recordings=True,
    )
    service.initialize_session(session_id)

    service.finalize_session(session)

    recording = read_json(session.directory / "recording.json")
    assert recording["state"] == "incomplete"
    assert recording["raw_source"]["state"] == "retained"
    assert recording["recording"]["path"] == "playback/session.mp3"
    assert (session.directory / "playback" / "session.mp3").is_file()
    assert list((session.directory / "audio").glob("*.wav"))


def test_debug_retention_rotates_oldest_unpinned_and_exports_pin(
    tmp_path: Path,
) -> None:
    first_id = "20260727T100002-cccccccccccc"
    second_id = "20260727T100003-dddddddddddd"
    first = _complete_session(tmp_path, first_id, frame_count=8)
    second = _complete_session(tmp_path, second_id, frame_count=8)
    now = 2_000_000_000.0
    adapter = LocalStorageAdapter(tmp_path, now=lambda: now)
    policy = DebugRetentionPolicy(
        enabled=True,
        byte_cap=8,
        max_age_s=100,
    )
    service = StorageApplicationService(
        adapter,
        debug_policy=policy,
    )
    service.initialize_session(first_id)
    service.initialize_session(second_id)
    first_debug = first.directory / "diagnostics"
    second_debug = second.directory / "diagnostics"
    first_debug.mkdir()
    second_debug.mkdir()
    old = first_debug / "old.bin"
    recent = second_debug / "recent.bin"
    old.write_bytes(b"old-data")
    recent.write_bytes(b"new-data")
    os.utime(old, (now - 200, now - 200))
    os.utime(recent, (now - 1, now - 1))
    service.pin_debug(second_id)

    result = service.prune_debug()

    assert result["truncated"] is True
    assert not old.exists()
    assert recent.exists()
    archive = service.export_debug(
        second_id,
        tmp_path / "debug-export.zip",
    )
    assert archive.is_file()
    service.pin_debug(second_id, pinned=False)


def test_recovery_removes_known_partial_without_touching_old_sessions(
    tmp_path: Path,
) -> None:
    phase4_id = "20260727T100004-eeeeeeeeeeee"
    old_id = "20260727T100005-ffffffffffff"
    phase4 = _complete_session(tmp_path, phase4_id, frame_count=8)
    old = _complete_session(tmp_path, old_id, frame_count=8)
    initial = StorageApplicationService(LocalStorageAdapter(tmp_path))
    initial.initialize_session(phase4_id)
    partial = phase4.directory / "playback" / ".session.mp3"
    partial.parent.mkdir()
    partial.write_bytes(b"partial")
    old_wavs = list((old.directory / "audio").glob("*.wav"))

    restarted = StorageApplicationService(LocalStorageAdapter(tmp_path))

    assert not partial.exists()
    assert restarted.recovery_decisions == (
        {
            "session_id": phase4_id,
            "action": "removed-partial-recording",
            "byte_count": 7,
        },
    )
    assert not (old.directory / "application.json").exists()
    assert list((old.directory / "audio").glob("*.wav")) == old_wavs


def test_accounting_tolerates_atomic_temporary_file_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "20260727T100006-111111111111"
    session = _complete_session(tmp_path, session_id, frame_count=8)
    service = StorageApplicationService(LocalStorageAdapter(tmp_path))
    service.initialize_session(session_id)
    temporary = session.directory / ".horizons.json.tmp"
    temporary.write_bytes(b"temporary")
    original_stat = Path.stat
    target_calls = 0

    def racing_stat(path: Path, *args: Any, **kwargs: Any) -> Any:
        nonlocal target_calls
        if path == temporary:
            target_calls += 1
            if target_calls == 2:
                temporary.unlink()
                raise FileNotFoundError(temporary)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", racing_stat)

    report = service.accounting(
        session_id=session_id,
        duration_s=1.0,
        minimum_free_bytes=0,
    )

    assert report["current_session"]["total_bytes"] > 0


def test_sequential_compacted_sessions_leave_only_reported_files(
    tmp_path: Path,
) -> None:
    session_ids = (
        "20260727T100008-333333333333",
        "20260727T100009-444444444444",
    )
    sessions = [
        _complete_session(tmp_path, session_id)
        for session_id in session_ids
    ]
    service = StorageApplicationService(
        LocalStorageAdapter(
            tmp_path,
            ffmpeg_executable="/fake/ffmpeg",
            ffprobe_executable="/fake/ffprobe",
            process_runner=_SuccessfulMediaRunner(),
        ),
        compact_recordings=True,
    )

    for session in sessions:
        service.initialize_session(session.session_id)
        service.finalize_session(session)

    report = service.accounting(
        session_id=session_ids[-1],
        duration_s=1.0,
        minimum_free_bytes=0,
    )
    workspace = report["workspace"]
    assert workspace["file_counts"]["recordings"] == 2
    assert workspace["bytes"]["temporary_raw"] == 0
    assert workspace["bytes"]["debug"] == 0
    assert workspace["total_bytes"] == sum(
        workspace["bytes"].values()
    )
    assert not [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name.startswith(".")
    ]
