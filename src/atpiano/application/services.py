"""Composition root for framework-independent application services."""

from __future__ import annotations

from dataclasses import dataclass

from atpiano.application.capture import CaptureApplicationService
from atpiano.application.scores import ScoreApplicationService
from atpiano.application.sessions import SessionApplicationService
from atpiano.application.storage import StorageApplicationService


@dataclass(frozen=True)
class ApplicationServices:
    """Application operations exposed to transport adapters."""

    capture: CaptureApplicationService
    sessions: SessionApplicationService
    scores: ScoreApplicationService
    storage: StorageApplicationService
