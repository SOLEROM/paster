"""The in-memory activity ring the status bar's Log button reads.

Every write the front makes lands here with tab, count and rev, so the log
alone answers "what did the phone change at 14:02" (plan §7). ``emit`` is
the Socket.IO push; the ring is capped so a long-running unit stays small.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable

LIMIT = 2000
SOURCE = "paster"


class ActivityLog:
    def __init__(self, emit: Callable[[str, dict], None] | None = None, limit: int = LIMIT):
        self._entries: list[dict] = []
        self._emit = emit
        self._limit = limit
        self._lock = threading.Lock()

    def log(self, level: str, message: str, source: str = SOURCE) -> dict:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
                 "source": source, "message": message}
        with self._lock:
            self._entries = (self._entries + [entry])[-self._limit:]
        if self._emit is not None:
            try:
                self._emit("activity_logged", entry)
            except Exception:  # noqa: BLE001 — a push failure must never fail the write
                pass
        return entry

    def entries(self, limit: int = 500) -> list[dict]:
        limit = max(1, min(int(limit), self._limit))
        with self._lock:
            return list(self._entries[-limit:])
