"""A 2 s mtime poll over the files the popup reads, so an edit made in vim
shows up in an open GUI without a reload (plan §4). ``scan``/``diff`` are
pure; the thread is the thin loop around them.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from .paths import Paths

INTERVAL_S = 2.0
CONFIG_KEY = "config.yaml"
TABS_KEY = "tabs"


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict


def scan(paths: Paths) -> dict:
    """{key: fingerprint} for config.yaml, the tab folder set and each content.md."""
    state: dict = {}
    try:
        st = paths.config_file.stat()
        state[CONFIG_KEY] = (st.st_mtime_ns, st.st_size)
    except OSError:
        state[CONFIG_KEY] = None
    tabs = []
    if paths.entries_dir.is_dir():
        for folder in sorted(paths.entries_dir.iterdir()):
            content = folder / "content.md"
            if folder.is_dir() and not folder.name.startswith(".") and content.is_file():
                tabs.append(folder.name)
                try:
                    st = content.stat()
                    state[f"entries/{folder.name}/content.md"] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    pass
    state[TABS_KEY] = tuple(tabs)
    return state


def diff(old: dict, new: dict) -> tuple[Event, ...]:
    events = []
    if old.get(CONFIG_KEY) != new.get(CONFIG_KEY):
        events.append(Event("config_changed", {}))
    if old.get(TABS_KEY) != new.get(TABS_KEY):
        events.append(Event("tabs_changed", {}))
    for key, fp in new.items():
        if key.startswith("entries/") and old.get(key) not in (None, fp) and key in old:
            events.append(Event("entries_changed", {"tab": key.split("/")[1]}))
    return tuple(events)


class Watcher(threading.Thread):
    def __init__(self, paths: Paths, emit: Callable[[str, dict], None], interval: float = INTERVAL_S):
        super().__init__(name="paster-watcher", daemon=True)
        self._paths = paths
        self._emit = emit
        self._interval = interval
        self._stop = threading.Event()
        self._lock = threading.Lock()          # _last is touched by the poll thread and by routes
        self._last = scan(paths)

    def poll_once(self) -> tuple[Event, ...]:
        with self._lock:
            current = scan(self._paths)
            events = diff(self._last, current)
            self._last = current
        for event in events:
            try:
                self._emit(event.name, event.payload)
            except Exception:  # noqa: BLE001 — a push failure must not stop the poll
                pass
        return events

    def run(self) -> None:
        while not self._stop.wait(self._interval):
            self.poll_once()

    def mark_clean(self) -> None:
        """Forget the pending diff — the write that just happened was ours
        and its route already pushed the event."""
        with self._lock:
            self._last = scan(self._paths)

    def stop(self) -> None:
        self._stop.set()
