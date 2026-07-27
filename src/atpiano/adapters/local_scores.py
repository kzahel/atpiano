"""Local score-process adapter for application score services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atpiano.score_snapshot import (
    ScoreRunner,
    ScoreVariantRunner,
    generate_score_snapshot,
    generate_score_variant,
    inspect_score_runtime,
)


@dataclass(frozen=True)
class LocalScoreExecutor:
    """Execute the isolated local score runtime behind an application port."""

    runtime_directory: Path
    score_runner: ScoreRunner | None = None
    score_variant_runner: ScoreVariantRunner | None = None

    def runtime_state(self) -> dict[str, Any]:
        if self.score_runner is not None:
            return {
                "available": True,
                "directory": str(self.runtime_directory),
                "injected_runner": True,
            }
        return inspect_score_runtime(self.runtime_directory)

    def generate_snapshot(
        self,
        session_directory: Path,
        *,
        commit_sample: int,
    ) -> dict[str, Any]:
        return generate_score_snapshot(
            session_directory,
            self.runtime_directory,
            commit_sample=commit_sample,
            runner=self.score_runner,
        )

    def generate_variant(
        self,
        session_directory: Path,
        *,
        baseline_musicxml_path: Path,
        baseline_alignment_path: Path,
        clef_policy: str,
        target_key_fifths: int | None,
    ) -> dict[str, Any]:
        return generate_score_variant(
            session_directory,
            self.runtime_directory,
            baseline_musicxml_path=baseline_musicxml_path,
            baseline_alignment_path=baseline_alignment_path,
            clef_policy=clef_policy,
            target_key_fifths=target_key_fifths,
            runner=self.score_variant_runner,
        )
