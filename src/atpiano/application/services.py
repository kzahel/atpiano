"""Composition root for framework-independent application services."""

from __future__ import annotations

from dataclasses import dataclass

from atpiano.application.sessions import SessionApplicationService


@dataclass(frozen=True)
class ApplicationServices:
    """Application operations exposed to transport adapters."""

    sessions: SessionApplicationService
