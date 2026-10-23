"""Process-wide runtime state.

The project store is created once and shared by the API and the assistant. Code must call :func:`get_store` at request time instead of importing
a module-level instance, which keeps the database swappable in tests.

Only the store lives here on purpose: everything else is stateless and receives
what it needs as an argument.
"""
from __future__ import annotations

import threading
from typing import Optional

from . import config
from .storage import ProjectStore

_lock = threading.Lock()
_store: Optional[ProjectStore] = None
_support_lock = threading.Lock()


def get_store() -> ProjectStore:
    """Return the shared :class:`ProjectStore`, creating it on first use."""
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = ProjectStore(config.DATABASE_URL or config.DB_PATH)
    return _store


def set_store(store: ProjectStore) -> None:
    """Replace the shared store (used by tests to isolate each run)."""
    global _store
    with _lock:
        _store = store


def reset_store() -> None:
    """Forget the current store so the next call rebuilds it from config."""
    global _store
    with _lock:
        _store = None


def get_support_store():
    """Use the workspace database for customer knowledge and short-lived chats."""
    from .support.store import SupportStore
    workspace = get_store()
    with _support_lock:
        if not hasattr(workspace, "_support_store"):
            workspace._support_store = SupportStore(workspace._conn())
        return workspace._support_store
