"""Ordered hook dispatch without global or request-persistent registrations."""

from __future__ import annotations

from dataclasses import dataclass

from rag_chat.application.hooks.progress import ProgressHook
from rag_chat.domain.models import ProgressEvent


@dataclass(frozen=True, slots=True)
class HookDispatcher:
    hooks: tuple[ProgressHook, ...] = ()

    def emit(self, event: ProgressEvent, *, on_progress: ProgressHook | None = None) -> None:
        """Call configured hooks in order, then the transient request callback.

        Exceptions propagate to the service, just like the original callback.
        """
        for hook in self.hooks:
            hook(event)
        if on_progress:
            on_progress(event)
