"""
In-memory session store with lazy TTL eviction.

Each session entry shape:
    {
        "dataframe":  pd.DataFrame | None,
        "anomalies":  list | None,
        "insights":   dict | None,
        "created_at": float,          # time.time() at creation
    }

TTL is controlled by the SESSION_TTL_SECONDS environment variable (default 3600).
No background thread is needed for a demo with <10 concurrent sessions — eviction
happens lazily at the top of get_session().
"""

import os
import time

from dotenv import load_dotenv

load_dotenv()

SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

_store: dict[str, dict] = {}


def set_session(session_id: str, data: dict) -> None:
    """Store or overwrite a session entry. Always stamps created_at."""
    _store[session_id] = {**data, "created_at": time.time()}


def get_session(session_id: str) -> dict | None:
    """Return the session entry, or None if not found / expired."""
    evict_expired()
    return _store.get(session_id)


def delete_session(session_id: str) -> None:
    """Remove a session entry if it exists."""
    _store.pop(session_id, None)


def evict_expired() -> None:
    """Delete all entries whose age exceeds SESSION_TTL_SECONDS."""
    now = time.time()
    expired = [
        sid
        for sid, entry in _store.items()
        if now - entry.get("created_at", 0) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _store[sid]
