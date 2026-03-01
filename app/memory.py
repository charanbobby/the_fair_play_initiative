"""
app/memory.py
-------------
In-memory session store keyed by session_id.

Each session holds an ordered list of LangChain message dicts:
    {"role": "human" | "ai", "content": "..."}

Thread-safety: a threading.Lock guards all mutations so this is safe
under uvicorn's default single-process, multi-thread workers.

TODO (future): replace with Redis-backed store for multi-instance deployments.
"""

import threading
from typing import TypeAlias

# Simple message type alias
Message: TypeAlias = dict[str, str]   # {"role": "human"|"ai", "content": "..."}


class SessionMemory:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}
        self._lock = threading.Lock()

    def get_history(self, session_id: str) -> list[Message]:
        """Return the full conversation history for a session (read-only copy)."""
        with self._lock:
            return list(self._store.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append a message to a session's history."""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = []
            self._store[session_id].append({"role": role, "content": content})

    def clear(self, session_id: str) -> None:
        """Delete all history for a session."""
        with self._lock:
            self._store.pop(session_id, None)

    def session_ids(self) -> list[str]:
        """Return all active session IDs."""
        with self._lock:
            return list(self._store.keys())


# Singleton instance shared across the app process
session_memory = SessionMemory()
