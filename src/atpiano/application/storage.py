"""Framework-independent local storage and retention coordination."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from atpiano import __version__
from atpiano.corrected import CorrectedSession


@dataclass(frozen=True)
class DebugRetentionPolicy:
    """Explicit bounded policy for disposable local diagnostics."""

    enabled: bool = False
    byte_cap: int = 64 * 1024**2
    max_age_s: float = 72 * 60 * 60

    def __post_init__(self) -> None:
        if self.byte_cap <= 0:
            raise ValueError("debug retention byte cap must be positive")
        if self.max_age_s <= 0:
            raise ValueError("debug retention age must be positive")


class StorageBackend(Protocol):
    """Filesystem/encoder operations used by storage policy."""

    def initialize_session(
        self,
        session_id: str,
        *,
        compact_recording: bool,
        debug_policy: DebugRetentionPolicy,
    ) -> None: ...

    def finalize_session(
        self,
        session_id: str,
        *,
        compact_recording: bool,
        debug_policy: DebugRetentionPolicy,
        status: dict[str, Any],
    ) -> dict[str, Any]: ...

    def accounting(
        self,
        *,
        session_id: str | None,
        duration_s: float,
        minimum_free_bytes: int,
    ) -> dict[str, Any]: ...

    def prune_debug(
        self,
        *,
        byte_cap: int,
        max_age_s: float,
    ) -> dict[str, Any]: ...

    def pin_debug(self, session_id: str, *, pinned: bool) -> None: ...

    def export_debug(self, session_id: str, destination: Path) -> Path: ...

    def recover_workspace(self) -> tuple[dict[str, Any], ...]: ...


class StorageApplicationService:
    """Own Phase 4 recording, accounting, and debug-retention policy."""

    def __init__(
        self,
        backend: StorageBackend,
        *,
        compact_recordings: bool = True,
        debug_policy: DebugRetentionPolicy = DebugRetentionPolicy(),
    ) -> None:
        self._backend = backend
        self.compact_recordings = compact_recordings
        self.debug_policy = debug_policy
        self.recovery_decisions = backend.recover_workspace()

    @property
    def debug_enabled(self) -> bool:
        return self.debug_policy.enabled

    def initialize_session(self, session_id: str) -> None:
        self._backend.initialize_session(
            session_id,
            compact_recording=self.compact_recordings,
            debug_policy=self.debug_policy,
        )

    def finalize_session(self, session: CorrectedSession) -> None:
        lanes = {
            lane.name: lane.status()
            for lane in session.lanes
        }
        commit = lanes.get("commit")
        raw_retirement_ready = (
            commit is None
            or int(commit.get("commit_sample", -1))
            == session.horizons.audio_head_sample
        )
        status = {
            "schema_version": "atpiano.pipeline-status.v1",
            "application": {
                "name": "atpiano",
                "version": __version__,
            },
            "final_state": "settling",
            "source": {
                "sample_rate_hz": session.sample_rate_hz,
                "first_sample": 0,
                "frame_count": session.horizons.audio_head_sample,
            },
            "horizons": session.horizons.document(
                sample_rate_hz=session.sample_rate_hz
            ),
            "processing": {
                "correction_mode": session.correction_mode,
                "correction_reason": session.correction_reason,
                "correction_profile_id": session.correction_profile_id,
            },
            "lanes": lanes,
            "stages": [
                {"name": "capture", "state": "complete"},
                {
                    "name": "transcription",
                    "state": "complete",
                    "lanes": sorted(lanes),
                },
            ],
            "gaps": [],
            "errors": [],
            "retention": {
                "raw_retirement_ready": raw_retirement_ready,
                "raw_retirement_blocker": (
                    None
                    if raw_retirement_ready
                    else (
                        "commit lane did not advance through the accepted "
                        "source range"
                    )
                ),
            },
        }
        self._backend.finalize_session(
            session.session_id,
            compact_recording=self.compact_recordings,
            debug_policy=self.debug_policy,
            status=status,
        )

    def accounting(
        self,
        *,
        session_id: str | None,
        duration_s: float,
        minimum_free_bytes: int,
    ) -> dict[str, Any]:
        report = self._backend.accounting(
            session_id=session_id,
            duration_s=duration_s,
            minimum_free_bytes=minimum_free_bytes,
        )
        return {
            **report,
            "recovery_decisions": list(self.recovery_decisions),
        }

    def prune_debug(self) -> dict[str, Any]:
        if not self.debug_policy.enabled:
            return {
                "enabled": False,
                "removed_bytes": 0,
                "truncated": False,
            }
        return self._backend.prune_debug(
            byte_cap=self.debug_policy.byte_cap,
            max_age_s=self.debug_policy.max_age_s,
        )

    def pin_debug(self, session_id: str, *, pinned: bool = True) -> None:
        self._backend.pin_debug(session_id, pinned=pinned)

    def export_debug(self, session_id: str, destination: Path) -> Path:
        return self._backend.export_debug(session_id, destination)
