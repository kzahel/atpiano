from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

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
