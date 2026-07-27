"""Local filesystem, encoder, accounting, and debug-retention adapter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atpiano.application.storage import DebugRetentionPolicy
from atpiano.corrected_export import PLAYBACK_BITRATE, write_corrected_exports
from atpiano.util import read_json, sha256_file, utc_now, write_json

RECORDING_SCHEMA = "atpiano.recording.v1"
PHASE4_SESSION_SCHEMA = "atpiano.application-session.v1"
STORAGE_ACCOUNTING_SCHEMA = "atpiano.storage-accounting.v1"
PIPELINE_STATUS_MAX_BYTES = 64 * 1024
STORAGE_CATEGORIES = (
    "recordings",
    "events_indexes",
    "derived_artifacts",
    "debug",
    "temporary_raw",
    "trash",
)


class LocalStorageAdapter:
    """Execute application-owned storage policy on one local workspace."""

    def __init__(
        self,
        workspace_directory: Path,
        *,
        ffmpeg_executable: str | None = None,
        ffprobe_executable: str | None = None,
        process_runner: Callable[..., Any] = subprocess.run,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.workspace_directory = workspace_directory.resolve()
        self.workspace_directory.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_executable = (
            ffmpeg_executable
            if ffmpeg_executable is not None
            else shutil.which("ffmpeg")
        )
        self.ffprobe_executable = (
            ffprobe_executable
            if ffprobe_executable is not None
            else shutil.which("ffprobe")
        )
        self._run = process_runner
        self._now = now
        self._debug_lock = threading.Lock()

    def _session_directory(self, session_id: str) -> Path:
        directory = (self.workspace_directory / session_id).resolve()
        if (
            directory.parent != self.workspace_directory
            or not directory.is_dir()
        ):
            raise LookupError("storage session does not exist")
        return directory

    def initialize_session(
        self,
        session_id: str,
        *,
        compact_recording: bool,
        debug_policy: DebugRetentionPolicy,
    ) -> None:
        directory = self._session_directory(session_id)
        self._write_durable_json(
            directory / "application.json",
            {
                "schema_version": PHASE4_SESSION_SCHEMA,
                "created_at": utc_now(),
                "storage": {
                    "compact_recording": compact_recording,
                    "debug": {
                        "enabled": debug_policy.enabled,
                        "byte_cap": debug_policy.byte_cap,
                        "max_age_s": debug_policy.max_age_s,
                    },
                },
            },
        )

    @staticmethod
    def _write_durable_json(
        path: Path,
        document: dict[str, Any],
    ) -> None:
        write_json(path, document)
        with path.open("rb") as handle:
            try:
                os.fsync(handle.fileno())
            except OSError:
                return
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            return

    @staticmethod
    def _source_segments(
        directory: Path,
        *,
        expected_frames: int,
        sample_rate_hz: int,
    ) -> list[dict[str, Any]]:
        index_path = directory / "audio" / "segments.jsonl"
        if not index_path.is_file():
            raise ValueError("raw audio index is unavailable")
        rows: list[dict[str, Any]] = []
        cursor = 0
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            path = index_path.parent / str(row["path"])
            first_sample = int(row["first_sample"])
            frame_count = int(row["frame_count"])
            if (
                first_sample != cursor
                or frame_count <= 0
                or int(row["sample_rate_hz"]) != sample_rate_hz
                or not path.is_file()
                or str(row["sha256"]) != sha256_file(path)
            ):
                raise ValueError("raw audio segment mapping is invalid")
            with wave.open(str(path), "rb") as source:
                if (
                    source.getnchannels() != 1
                    or source.getsampwidth() != 2
                    or source.getframerate() != sample_rate_hz
                    or source.getnframes() != frame_count
                ):
                    raise ValueError("raw audio segment format is invalid")
            rows.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": str(row["sha256"]),
                    "first_sample": first_sample,
                    "frame_count": frame_count,
                    "byte_count": path.stat().st_size,
                }
            )
            cursor += frame_count
        if cursor != expected_frames:
            raise ValueError(
                "raw audio segments do not cover the accepted source"
            )
        return rows

    def _verify_playback(
        self,
        path: Path,
        *,
        frame_count: int,
        sample_rate_hz: int,
    ) -> dict[str, Any]:
        if self.ffmpeg_executable is None:
            raise RuntimeError("FFmpeg is unavailable")
        if self.ffprobe_executable is None:
            raise RuntimeError("FFprobe is unavailable")
        self._run(
            [
                self.ffmpeg_executable,
                "-hide_banner",
                "-loglevel",
                "error",
                "-xerror",
                "-nostdin",
                "-i",
                str(path),
                "-f",
                "null",
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        probe = self._run(
            [
                self.ffprobe_executable,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate,start_time,duration",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(probe.stdout)
        streams = payload.get("streams")
        if not isinstance(streams, list) or len(streams) != 1:
            raise ValueError("compact recording has no single audio stream")
        stream = streams[0]
        if (
            stream.get("codec_name") != "mp3"
            or int(stream["sample_rate"]) != sample_rate_hz
        ):
            raise ValueError("compact recording stream format is invalid")
        duration_s = float(
            stream.get("duration")
            or payload.get("format", {}).get("duration")
        )
        expected_duration_s = frame_count / sample_rate_hz
        tolerance_s = max(0.1, 2304 / sample_rate_hz)
        if abs(duration_s - expected_duration_s) > tolerance_s:
            raise ValueError(
                "compact recording duration does not cover the source range"
            )
        return {
            "decoded_complete": True,
            "codec": "mp3",
            "sample_rate_hz": sample_rate_hz,
            "probed_duration_s": duration_s,
            "expected_duration_s": expected_duration_s,
            "duration_tolerance_s": tolerance_s,
            "stream_start_time_s": float(stream.get("start_time") or 0.0),
            "verified_at": utc_now(),
        }

    @staticmethod
    def _recording_document(
        *,
        state: str,
        session_id: str,
        frame_count: int,
        sample_rate_hz: int,
        segments: list[dict[str, Any]],
        playback: dict[str, Any] | None,
        verification: dict[str, Any] | None,
        compact_enabled: bool,
        error: str | None,
        raw_state: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": RECORDING_SCHEMA,
            "session_id": session_id,
            "state": state,
            "updated_at": utc_now(),
            "compact_enabled": compact_enabled,
            "source": {
                "first_sample": 0,
                "frame_count": frame_count,
                "sample_rate_hz": sample_rate_hz,
                "mapping": (
                    "playback time seconds equals source sample divided by "
                    "sample_rate_hz"
                ),
                "segments": segments,
            },
            "recording": playback,
            "verification": verification,
            "raw_source": {
                "state": raw_state,
                "segment_count": len(segments),
                "byte_count": sum(
                    int(segment["byte_count"]) for segment in segments
                ),
            },
            "error": error,
        }

    def _finalize_recording(
        self,
        directory: Path,
        *,
        session_id: str,
        compact_recording: bool,
        playback: dict[str, Any] | None,
        frame_count: int,
        sample_rate_hz: int,
        retirement_blocker: str | None,
    ) -> dict[str, Any]:
        try:
            segments = self._source_segments(
                directory,
                expected_frames=frame_count,
                sample_rate_hz=sample_rate_hz,
            )
        except (OSError, ValueError) as error:
            document = self._recording_document(
                state="incomplete",
                session_id=session_id,
                frame_count=frame_count,
                sample_rate_hz=sample_rate_hz,
                segments=[],
                playback=playback,
                verification=None,
                compact_enabled=compact_recording,
                error=f"{type(error).__name__}: {error}",
                raw_state="retained",
            )
            self._write_durable_json(
                directory / "recording.json",
                document,
            )
            return document

        if not compact_recording:
            document = self._recording_document(
                state="raw-retained",
                session_id=session_id,
                frame_count=frame_count,
                sample_rate_hz=sample_rate_hz,
                segments=segments,
                playback=playback,
                verification=None,
                compact_enabled=False,
                error=None,
                raw_state="retained",
            )
            self._write_durable_json(
                directory / "recording.json",
                document,
            )
            return document

        if retirement_blocker is not None:
            document = self._recording_document(
                state="incomplete",
                session_id=session_id,
                frame_count=frame_count,
                sample_rate_hz=sample_rate_hz,
                segments=segments,
                playback=playback,
                verification=None,
                compact_enabled=True,
                error=retirement_blocker,
                raw_state="retained",
            )
            self._write_durable_json(
                directory / "recording.json",
                document,
            )
            return document

        try:
            if playback is None:
                if self.ffmpeg_executable is None:
                    raise RuntimeError("FFmpeg is unavailable")
                raise RuntimeError("FFmpeg did not publish playback audio")
            playback_path = directory / str(playback["path"])
            if (
                not playback_path.is_file()
                or str(playback["sha256"]) != sha256_file(playback_path)
            ):
                raise ValueError("published compact recording checksum failed")
            verification = self._verify_playback(
                playback_path,
                frame_count=frame_count,
                sample_rate_hz=sample_rate_hz,
            )
        except (
            OSError,
            RuntimeError,
            subprocess.CalledProcessError,
            ValueError,
        ) as error:
            document = self._recording_document(
                state="incomplete",
                session_id=session_id,
                frame_count=frame_count,
                sample_rate_hz=sample_rate_hz,
                segments=segments,
                playback=playback,
                verification=None,
                compact_enabled=True,
                error=f"{type(error).__name__}: {error}",
                raw_state="retained",
            )
            self._write_durable_json(
                directory / "recording.json",
                document,
            )
            return document

        enriched_playback = {
            **playback,
            "bitrate": PLAYBACK_BITRATE,
            "source_first_sample": 0,
            "source_frame_count": frame_count,
            "sample_rate_hz": sample_rate_hz,
            "encoder": {
                "name": "ffmpeg-libmp3lame",
                "bitrate": PLAYBACK_BITRATE,
                "xing_header": True,
            },
        }
        pending = self._recording_document(
            state="retirement-pending",
            session_id=session_id,
            frame_count=frame_count,
            sample_rate_hz=sample_rate_hz,
            segments=segments,
            playback=enriched_playback,
            verification=verification,
            compact_enabled=True,
            error=None,
            raw_state="retirement-pending",
        )
        self._write_durable_json(
            directory / "recording.json",
            pending,
        )
        remaining: list[str] = []
        retirement_error: str | None = None
        try:
            for segment in segments:
                (directory / str(segment["path"])).unlink(missing_ok=True)
            (directory / "audio" / "segments.jsonl").unlink(
                missing_ok=True
            )
        except OSError as error:
            retirement_error = f"{type(error).__name__}: {error}"
        for segment in segments:
            if (directory / str(segment["path"])).exists():
                remaining.append(str(segment["path"]))
        complete = not remaining and retirement_error is None
        document = self._recording_document(
            state="complete" if complete else "retirement-pending",
            session_id=session_id,
            frame_count=frame_count,
            sample_rate_hz=sample_rate_hz,
            segments=segments,
            playback=enriched_playback,
            verification=verification,
            compact_enabled=True,
            error=retirement_error,
            raw_state="retired" if complete else "retirement-pending",
        )
        if remaining:
            document["raw_source"]["remaining_paths"] = remaining
        self._write_durable_json(
            directory / "recording.json",
            document,
        )
        return document

    def finalize_session(
        self,
        session_id: str,
        *,
        compact_recording: bool,
        debug_policy: DebugRetentionPolicy,
        status: dict[str, Any],
    ) -> dict[str, Any]:
        directory = self._session_directory(session_id)
        session = read_json(directory / "session.json")
        frame_count = int(session["source_frame_count"])
        sample_rate_hz = int(session["sample_rate_hz"])
        exports = write_corrected_exports(
            directory,
            allow_settling=True,
            playback_ffmpeg_executable=self.ffmpeg_executable,
            process_runner=self._run,
        )
        recording = self._finalize_recording(
            directory,
            session_id=session_id,
            compact_recording=compact_recording,
            playback=(
                exports.get("playback")
                if isinstance(exports.get("playback"), dict)
                else None
            ),
            frame_count=frame_count,
            sample_rate_hz=sample_rate_hz,
            retirement_blocker=(
                str(
                    status.get("retention", {}).get(
                        "raw_retirement_blocker"
                    )
                )
                if not status.get("retention", {}).get(
                    "raw_retirement_ready",
                    False,
                )
                else None
            ),
        )
        if recording.get("recording") is not None:
            exports["playback"] = recording["recording"]
            write_json(directory / "exports" / "manifest.json", exports)

        if debug_policy.enabled:
            debug = self.prune_debug(
                byte_cap=debug_policy.byte_cap,
                max_age_s=debug_policy.max_age_s,
            )
        else:
            diagnostics = directory / "diagnostics"
            removed_bytes = self._tree_bytes(diagnostics)
            if diagnostics.exists():
                shutil.rmtree(diagnostics)
            debug = {
                "enabled": False,
                "removed_bytes": removed_bytes,
                "truncated": removed_bytes > 0,
            }

        stage_errors = session.get("processing", {}).get(
            "stage_errors",
            {},
        )
        lane_statuses = status.get("lanes", {})
        pipeline = session.get("pipeline")
        final_status = {
            **status,
            "recorded_at": utc_now(),
            "final_state": "complete",
            "versions": {
                "application": status.get("application"),
                "models": {
                    name: lane.get("model")
                    for name, lane in (
                        lane_statuses.items()
                        if isinstance(lane_statuses, dict)
                        else ()
                    )
                    if isinstance(lane, dict)
                },
                "decoders": {
                    name: lane.get("schema_version")
                    for name, lane in (
                        lane_statuses.items()
                        if isinstance(lane_statuses, dict)
                        else ()
                    )
                    if isinstance(lane, dict)
                },
                "encoder": (
                    recording["recording"].get("encoder")
                    if isinstance(recording.get("recording"), dict)
                    else None
                ),
            },
            "recording": {
                "state": recording["state"],
                "compact_enabled": compact_recording,
                "raw_source_state": recording["raw_source"]["state"],
                "error": recording["error"],
            },
            "debug": debug,
            "pipeline": pipeline,
            "aggregates": {
                "accepted_blocks": (
                    int(pipeline.get("accepted_blocks", 0))
                    if isinstance(pipeline, dict)
                    else 0
                ),
                "accepted_frames": (
                    int(pipeline.get("accepted_frames", 0))
                    if isinstance(pipeline, dict)
                    else frame_count
                ),
                "event_emissions": sum(
                    int(
                        lane.get(
                            "event_emission_count",
                            lane.get("events", {}).get(
                                "emissions",
                                0,
                            ),
                        )
                    )
                    for lane in (
                        lane_statuses.values()
                        if isinstance(lane_statuses, dict)
                        else ()
                    )
                    if isinstance(lane, dict)
                ),
                "stage_error_count": (
                    len(stage_errors)
                    if isinstance(stage_errors, dict)
                    else 0
                ),
            },
            "errors": [
                {"stage": str(stage), "error": str(error)}
                for stage, error in (
                    stage_errors.items()
                    if isinstance(stage_errors, dict)
                    else ()
                )
            ],
            "stages": [
                *status.get("stages", []),
                {
                    "name": "recording",
                    "state": (
                        "complete"
                        if recording["state"]
                        in {"complete", "raw-retained"}
                        else "incomplete"
                    ),
                },
                {"name": "debug-retention", "state": "complete"},
            ],
        }
        encoded = (
            json.dumps(final_status, sort_keys=True, allow_nan=False)
            .encode("utf-8")
        )
        if len(encoded) > PIPELINE_STATUS_MAX_BYTES:
            raise ValueError("compact pipeline status exceeds its size bound")
        self._write_durable_json(
            directory / "pipeline-status.json",
            final_status,
        )
        return final_status

    @staticmethod
    def _tree_bytes(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(
            child.stat().st_size
            for child in path.rglob("*")
            if child.is_file()
        )

    def _debug_sessions(self) -> list[tuple[Path, bool]]:
        sessions: list[tuple[Path, bool]] = []
        for marker in self.workspace_directory.glob(
            "*/application.json"
        ):
            diagnostics = marker.parent / "diagnostics"
            if diagnostics.is_dir():
                sessions.append(
                    (diagnostics, (diagnostics / ".pin.json").is_file())
                )
        return sessions

    def prune_debug(
        self,
        *,
        byte_cap: int,
        max_age_s: float,
    ) -> dict[str, Any]:
        if byte_cap <= 0 or max_age_s <= 0:
            raise ValueError("debug retention limits must be positive")
        with self._debug_lock:
            return self._prune_debug_unlocked(
                byte_cap=byte_cap,
                max_age_s=max_age_s,
            )

    def _prune_debug_unlocked(
        self,
        *,
        byte_cap: int,
        max_age_s: float,
    ) -> dict[str, Any]:
        cutoff = self._now() - max_age_s
        removed_bytes = 0
        removed_files = 0
        candidates: list[tuple[float, Path, int]] = []
        pinned_bytes = 0
        for diagnostics, pinned in self._debug_sessions():
            for path in diagnostics.rglob("*"):
                if not path.is_file() or path.name == ".pin.json":
                    continue
                try:
                    metadata = path.stat()
                except FileNotFoundError:
                    continue
                size = metadata.st_size
                if pinned:
                    pinned_bytes += size
                    continue
                if metadata.st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    removed_bytes += size
                    removed_files += 1
                else:
                    candidates.append(
                        (metadata.st_mtime, path, size)
                    )
        candidates.sort(key=lambda item: (item[0], item[1].as_posix()))
        retained_bytes = sum(item[2] for item in candidates)
        while candidates and retained_bytes > byte_cap:
            _, path, size = candidates.pop(0)
            path.unlink(missing_ok=True)
            retained_bytes -= size
            removed_bytes += size
            removed_files += 1
        return {
            "enabled": True,
            "byte_cap": byte_cap,
            "max_age_s": max_age_s,
            "retained_bytes": retained_bytes,
            "pinned_bytes": pinned_bytes,
            "removed_bytes": removed_bytes,
            "removed_files": removed_files,
            "truncated": removed_files > 0,
            "pinned_over_cap": pinned_bytes > byte_cap,
        }

    def pin_debug(self, session_id: str, *, pinned: bool) -> None:
        diagnostics = self._session_directory(session_id) / "diagnostics"
        marker = diagnostics / ".pin.json"
        if pinned:
            diagnostics.mkdir(parents=True, exist_ok=True)
            write_json(
                marker,
                {
                    "schema_version": "atpiano.debug-pin.v1",
                    "pinned_at": utc_now(),
                },
            )
        else:
            marker.unlink(missing_ok=True)

    def export_debug(self, session_id: str, destination: Path) -> Path:
        diagnostics = self._session_directory(session_id) / "diagnostics"
        if not diagnostics.is_dir():
            raise LookupError("session debug data does not exist")
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        archive_base = destination.with_suffix("")
        archive = Path(
            shutil.make_archive(
                str(archive_base),
                "zip",
                root_dir=diagnostics,
            )
        )
        if archive != destination:
            archive.replace(destination)
        return destination

    @staticmethod
    def _phase4_marker(directory: Path) -> dict[str, Any] | None:
        try:
            marker = read_json(directory / "application.json")
        except (OSError, ValueError):
            return None
        return (
            marker
            if marker.get("schema_version") == PHASE4_SESSION_SCHEMA
            else None
        )

    def recover_workspace(self) -> tuple[dict[str, Any], ...]:
        decisions: list[dict[str, Any]] = []
        for directory in sorted(
            path
            for path in self.workspace_directory.iterdir()
            if path.is_dir() and path.name != ".trash"
        ):
            marker = self._phase4_marker(directory)
            if marker is None:
                continue
            partial = directory / "playback" / ".session.mp3"
            if partial.is_file():
                byte_count = partial.stat().st_size
                partial.unlink()
                decisions.append(
                    {
                        "session_id": directory.name,
                        "action": "removed-partial-recording",
                        "byte_count": byte_count,
                    }
                )
            recording_path = directory / "recording.json"
            if not recording_path.is_file():
                continue
            try:
                recording = read_json(recording_path)
                if (
                    recording.get("schema_version") != RECORDING_SCHEMA
                    or recording.get("state") != "retirement-pending"
                ):
                    continue
                playback = recording.get("recording")
                source = recording["source"]
                if not isinstance(playback, dict):
                    continue
                playback_path = directory / str(playback["path"])
                self._verify_playback(
                    playback_path,
                    frame_count=int(source["frame_count"]),
                    sample_rate_hz=int(source["sample_rate_hz"]),
                )
                for segment in source.get("segments", []):
                    (directory / str(segment["path"])).unlink(
                        missing_ok=True
                    )
                (directory / "audio" / "segments.jsonl").unlink(
                    missing_ok=True
                )
                recording["state"] = "complete"
                recording["updated_at"] = utc_now()
                recording["raw_source"]["state"] = "retired"
                recording["raw_source"].pop("remaining_paths", None)
                recording["error"] = None
                self._write_durable_json(
                    recording_path,
                    recording,
                )
                decisions.append(
                    {
                        "session_id": directory.name,
                        "action": "completed-raw-retirement",
                    }
                )
            except (
                KeyError,
                OSError,
                RuntimeError,
                subprocess.CalledProcessError,
                TypeError,
                ValueError,
            ) as error:
                decisions.append(
                    {
                        "session_id": directory.name,
                        "action": "preserved-raw-after-recovery-failure",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
        return tuple(decisions)

    def _category(self, path: Path) -> str:
        relative = path.relative_to(self.workspace_directory)
        parts = relative.parts
        if parts[0] == ".trash":
            return "trash"
        if "diagnostics" in parts:
            return "debug"
        if path.name.startswith(".") or path.suffix == ".tmp":
            return "temporary_raw"
        session_directory = self.workspace_directory / parts[0]
        marker = self._phase4_marker(session_directory)
        compact_enabled = bool(
            marker
            and marker.get("storage", {}).get("compact_recording")
        )
        if len(parts) > 2 and parts[1] == "audio" and path.suffix == ".wav":
            return "temporary_raw" if compact_enabled else "recordings"
        if len(parts) > 2 and parts[1] == "playback":
            return "recordings"
        if len(parts) > 2 and parts[1] in {"exports", "score"}:
            return "derived_artifacts"
        return "events_indexes"

    def _usage(self, root: Path) -> dict[str, Any]:
        categories = {name: 0 for name in STORAGE_CATEGORIES}
        file_counts = {name: 0 for name in STORAGE_CATEGORIES}
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    size = path.stat().st_size
                except FileNotFoundError:
                    continue
                category = self._category(path)
                categories[category] += size
                file_counts[category] += 1
        return {
            "bytes": categories,
            "file_counts": file_counts,
            "total_bytes": sum(categories.values()),
        }

    def accounting(
        self,
        *,
        session_id: str | None,
        duration_s: float,
        minimum_free_bytes: int,
    ) -> dict[str, Any]:
        workspace = self._usage(self.workspace_directory)
        empty = {
            "bytes": {name: 0 for name in STORAGE_CATEGORIES},
            "file_counts": {
                name: 0 for name in STORAGE_CATEGORIES
            },
            "total_bytes": 0,
        }
        if session_id is None:
            current = empty
        else:
            try:
                current = self._usage(
                    self._session_directory(session_id)
                )
            except LookupError:
                # Replay claims an ID before its model-loading thread creates
                # the session directory. Warming-state accounting must remain
                # readable during that bounded interval.
                current = empty
        projected = {
            name: (
                value * 3600 / duration_s
                if duration_s >= 1.0
                else None
            )
            for name, value in current["bytes"].items()
        }
        free_bytes = shutil.disk_usage(self.workspace_directory).free
        return {
            "schema_version": STORAGE_ACCOUNTING_SCHEMA,
            "workspace": workspace,
            "current_session": {
                **current,
                "duration_s": duration_s,
                "projected_bytes_per_hour": projected,
            },
            "free_bytes": free_bytes,
            "minimum_free_bytes": minimum_free_bytes,
            "warning": (
                free_bytes < minimum_free_bytes * 5 // 4
            ),
            "must_stop": free_bytes < minimum_free_bytes,
        }
