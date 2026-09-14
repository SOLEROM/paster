"""Snapshot ring: the last 50 versions of every file the front rewrites.

Lives under ``<data dir>/history/<relpath>/<timestamp>`` — outside the
repo (plan D3), one folder per edited file. Restoring is itself a checked
write, so the version being replaced lands in the ring too.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import Paths

RING = 50
_TS_FORMAT = "%Y%m%dT%H%M%S.%f"


@dataclass(frozen=True)
class Snapshot:
    ts: str
    size: int


def history_root(paths: Paths, relpath: str) -> Path:
    return paths.history_dir / relpath


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime(_TS_FORMAT)


def snapshot(paths: Paths, relpath: str, source: Path) -> str | None:
    """Copy ``source`` into the ring; None when there is nothing to copy."""
    if not source.is_file():
        return None
    root = history_root(paths, relpath)
    root.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    target = root / ts
    n = 1
    while target.exists():                    # two writes in one microsecond
        target = root / f"{ts}-{n}"
        n += 1
    shutil.copyfile(source, target)
    _prune(root)
    return target.name


def _prune(root: Path) -> None:
    files = sorted(p for p in root.iterdir() if p.is_file())
    for stale in files[:-RING] if len(files) > RING else []:
        stale.unlink()


def list_snapshots(paths: Paths, relpath: str) -> tuple[Snapshot, ...]:
    root = history_root(paths, relpath)
    if not root.is_dir():
        return ()
    files = sorted((p for p in root.iterdir() if p.is_file()), reverse=True)
    return tuple(Snapshot(ts=p.name, size=p.stat().st_size) for p in files)


def read_snapshot(paths: Paths, relpath: str, ts: str) -> str:
    if "/" in ts or ts in ("", ".", "..") or ts.startswith("."):
        raise FileNotFoundError(ts)
    target = history_root(paths, relpath) / ts
    if not target.is_file():
        raise FileNotFoundError(ts)
    return target.read_text(encoding="utf-8", errors="replace")
