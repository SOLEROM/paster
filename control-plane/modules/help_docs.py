"""The Help view's tree and pages over ``man/`` (the skeleton's docs API)."""
from __future__ import annotations

from pathlib import Path


def help_tree(base: Path, rel: str = "") -> list:
    """[{type, name, path, children?}] — dirs first, then files, sorted."""
    node = base / rel if rel else base
    out = []
    if not node.is_dir():
        return out
    for entry in sorted(node.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        path = f"{rel}/{entry.name}".strip("/")
        if entry.is_dir():
            out.append({"type": "dir", "name": entry.name, "path": path,
                        "children": help_tree(base, path)})
        elif entry.suffix.lower() == ".md":
            out.append({"type": "file", "name": entry.name, "path": path})
    return out


def safe_doc(base: Path, rel: str) -> Path | None:
    """A docs path that stays inside ``base``, or None."""
    try:
        target = (base / rel).resolve()
        target.relative_to(base.resolve())
    except (ValueError, OSError):
        return None
    return target if target.is_file() and target.suffix.lower() == ".md" else None
