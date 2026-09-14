"""The one write path: revision check → snapshot → atomic replace.

Every file the front edits goes through ``checked_write``. A ``rev`` is the
sha256 of the bytes on disk; a client sends back the rev it loaded, and a
mismatch is refused (plan D5) so an edit made in vim meanwhile is never
overwritten. The snapshot ring (history.py) is taken before the write.
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

from . import history
from .paths import Paths
from .tab_labels import is_safe_id

# One lock for every mutation of entries/ and config.yaml — the process is
# the only writer the front knows about, and the operations are milliseconds.
LOCK = threading.RLock()

CONFIG_RELPATH = "config.yaml"


class StaleRevision(Exception):
    """The file changed since the client read it; ``current`` is its rev now."""

    def __init__(self, current: str):
        super().__init__("changed on disk since it was loaded")
        self.current = current


class BadRelpath(ValueError):
    """Not one of the files the front is allowed to touch."""


def rev_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def resolve_relpath(paths: Paths, relpath: str) -> Path:
    """``config.yaml`` or ``entries/<tab>/content.md`` → its absolute path.

    Anything else — a parent reference, an absolute path, a dotfile, a
    fourth segment — is refused before it ever reaches the filesystem.
    """
    if relpath == CONFIG_RELPATH:
        return paths.config_file
    parts = relpath.split("/")
    if len(parts) == 3 and parts[0] == "entries" and parts[2] == "content.md" and is_safe_id(parts[1]):
        target = (paths.entries_dir / parts[1] / "content.md")
        root = paths.entries_dir.resolve()
        if root in target.resolve().parents:
            return target
    raise BadRelpath(f"not an editable file: {relpath!r}")


def read_text(path: Path) -> tuple[str, str]:
    """(text, rev) of a file; raises FileNotFoundError when it is absent."""
    data = path.read_bytes()
    return data.decode("utf-8", errors="replace"), rev_of(data)


def atomic_write_text(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return rev_of(data)


def checked_write(paths: Paths, relpath: str, text: str, base_rev: str | None,
                  *, allow_create: bool = False) -> str:
    """Write ``text`` to ``relpath`` if its rev is still ``base_rev``.

    ``base_rev=None`` skips the check (a caller that has just created the
    file). Returns the new rev. The snapshot is taken first, so every
    version that ever existed on disk is in the history ring.
    """
    target = resolve_relpath(paths, relpath)
    with LOCK:
        try:
            _, current = read_text(target)
        except FileNotFoundError:
            if not allow_create:
                raise
            current = ""
        if base_rev is not None and base_rev != current:
            raise StaleRevision(current)
        history.snapshot(paths, relpath, target)
        return atomic_write_text(target, text)
