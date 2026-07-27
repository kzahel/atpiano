"""Local model-process lifecycle and capability selection."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from atpiano.backend_profile import (
    BackendSchedulerIdentity,
    read_backend_profile,
    select_profile_mode,
)
from atpiano.corrected_commit import CommitModel
from atpiano.live import LiveWindowModel
from atpiano.model_worker import CommitModelWorker, PreviewModelWorker


class LocalModelPool:
    """Own warmed local model adapters and their worker processes."""

    def __init__(
        self,
        *,
        preview_model_factory: Any,
        commit_model_factory: Any,
        isolate_models: bool,
        commit_threads: int | None,
        correction_mode: str,
        backend_profile_path: Path | None,
    ) -> None:
        self.preview_model_factory = preview_model_factory
        self.commit_model_factory = commit_model_factory
        self.isolate_models = isolate_models
        self.commit_threads = commit_threads
        self.correction_mode = correction_mode
        self.backend_profile_path = (
            backend_profile_path.resolve()
            if backend_profile_path is not None
            else None
        )
        self._lock = threading.Lock()
        self._preview_model: LiveWindowModel | None = None
        self._commit_model: CommitModel | None = None

    @staticmethod
    def _has_exited(model: Any) -> bool:
        status = getattr(model, "status", None)
        if status is None:
            return False
        try:
            document = status()
        except RuntimeError:
            return True
        return (
            isinstance(document, dict)
            and document.get("alive") is False
        )

    def preview(self) -> LiveWindowModel:
        with self._lock:
            if (
                self._preview_model is not None
                and self._has_exited(self._preview_model)
            ):
                close = getattr(self._preview_model, "close", None)
                if close is not None:
                    close()
                self._preview_model = None
            if self._preview_model is None:
                self._preview_model = (
                    PreviewModelWorker(self.preview_model_factory)
                    if self.isolate_models
                    else self.preview_model_factory()
                )
            return self._preview_model

    def commit(self) -> CommitModel:
        with self._lock:
            if (
                self._commit_model is not None
                and self._has_exited(self._commit_model)
            ):
                close = getattr(self._commit_model, "close", None)
                if close is not None:
                    close()
                self._commit_model = None
            if self._commit_model is None:
                self._commit_model = (
                    CommitModelWorker(
                        self.commit_model_factory,
                        thread_limit=self.commit_threads,
                    )
                    if self.isolate_models
                    else self.commit_model_factory()
                )
            return self._commit_model

    def models(self) -> tuple[LiveWindowModel, CommitModel]:
        return self.preview(), self.commit()

    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            models = (self._preview_model, self._commit_model)
        result: list[dict[str, Any]] = []
        for model in models:
            status = getattr(model, "status", None)
            if status is not None:
                result.append(status())
        return result

    def loaded(self) -> bool:
        with self._lock:
            return (
                self._preview_model is not None
                or self._commit_model is not None
            )

    def resolve_correction_mode(
        self,
        commit_model: CommitModel,
        *,
        scheduler: BackendSchedulerIdentity,
    ) -> tuple[str, str, str | None]:
        if self.correction_mode != "auto":
            return (
                self.correction_mode,
                "selected by explicit local configuration",
                None,
            )
        if self.backend_profile_path is None:
            return (
                "after-stop",
                "no backend profile is configured; using the conservative mode",
                None,
            )
        try:
            profile = read_backend_profile(self.backend_profile_path)
        except (OSError, TypeError, ValueError, ValidationError) as error:
            return (
                "after-stop",
                "backend profile is unavailable or invalid: "
                f"{type(error).__name__}: {error}",
                None,
            )
        selected, reason = select_profile_mode(
            profile,
            provenance=commit_model.provenance(),
            thread_limit=self.commit_threads,
            scheduler=scheduler,
        )
        return selected.value, reason, profile.profile_id

    def unload(self) -> None:
        with self._lock:
            models = (self._preview_model, self._commit_model)
            self._preview_model = None
            self._commit_model = None
        for model in models:
            close = getattr(model, "close", None)
            if close is not None:
                close()

    def close(self) -> None:
        self.unload()

    def inject_commit_for_test(self, model: CommitModel) -> None:
        with self._lock:
            self._commit_model = model
