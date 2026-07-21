"""
core/memory.py — In-memory conversation history per session_id.

Stores the last 10 message pairs per session and expires sessions
that have been idle for longer than the configured timeout.
"""

import time
from threading import Lock
from typing import Any

# Default session expiry — overridden by ultron_config.json on startup
_SESSION_TIMEOUT_SECONDS: int = 30 * 60  # 30 minutes
_MAX_PAIRS: int = 10  # keep last N user+assistant pairs


class ConversationMemory:
    """Thread-safe, in-memory conversation store keyed by session_id."""

    def __init__(self, session_timeout_minutes: int = 30) -> None:
        self._timeout = session_timeout_minutes * 60
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session history and refresh the timestamp."""
        with self._lock:
            self._ensure_session(session_id)
            self._store[session_id]["messages"].append(
                {"role": role, "content": content}
            )
            self._trim(session_id)
            self._store[session_id]["last_active"] = time.time()

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Return the message list for the given session (empty list if unknown)."""
        with self._lock:
            self._purge_expired()
            session = self._store.get(session_id)
            if session is None:
                return []
            session["last_active"] = time.time()
            return list(session["messages"])

    def clear_session(self, session_id: str) -> None:
        """Delete all history for a session."""
        with self._lock:
            self._store.pop(session_id, None)

    def clear_all(self) -> None:
        """Wipe every session — called on mode switch so old tone doesn't bleed through."""
        with self._lock:
            self._store.clear()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_session(self, session_id: str) -> None:
        if session_id not in self._store:
            self._store[session_id] = {
                "messages": [],
                "last_active": time.time(),
            }

    def _trim(self, session_id: str) -> None:
        """Keep only the last _MAX_PAIRS * 2 messages (user + assistant per pair)."""
        msgs = self._store[session_id]["messages"]
        max_msgs = _MAX_PAIRS * 2
        if len(msgs) > max_msgs:
            self._store[session_id]["messages"] = msgs[-max_msgs:]

    def _purge_expired(self) -> None:
        """Remove sessions that have been idle past the timeout."""
        now = time.time()
        expired = [
            sid
            for sid, data in self._store.items()
            if now - data["last_active"] > self._timeout
        ]
        for sid in expired:
            del self._store[sid]


# ── Module-level singleton ────────────────────────────────────────────────────
# Imported and used throughout the backend.  main.py sets the timeout on startup.
memory = ConversationMemory()
