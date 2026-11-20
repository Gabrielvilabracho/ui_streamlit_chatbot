"""The callback contract shared by configured hooks and request presenters."""

from collections.abc import Callable

from rag_chat.domain.models import ProgressEvent

ProgressHook = Callable[[ProgressEvent], None]
