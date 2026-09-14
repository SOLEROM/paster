"""The tab-label rules of ``bin/toggle.sh``, as pure functions.

``toggle.sh --list-tabs`` is the truth the front shows (plan D4); these
mirror it for pre-flight feedback ("that name would collide") and for the
renumbering the front does when tabs are created or reordered. The parity
test in tests/test_tab_labels.py keeps the two in step.
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence

PREFIX_RE = re.compile(r"^[0-9]+_")
ROFI_UNSAFE = ",:'\""
# A name the front creates: readable, one line, no path characters.
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
NAME_RULE = "letters, digits, spaces, _ . - (1-64 characters, starting with a letter or digit)"
STEP = 10


def is_safe_id(folder: str) -> bool:
    """A folder name the store may look up: one path segment, no dotfile."""
    return (bool(folder) and len(folder) <= 120 and "/" not in folder and "\0" not in folder
            and folder not in (".", "..") and not folder.startswith("."))


def prefix_of(folder: str) -> int | None:
    m = PREFIX_RE.match(folder)
    return int(m.group(0)[:-1]) if m else None


def base_of(folder: str) -> str:
    return PREFIX_RE.sub("", folder, count=1)


def label_for(folder: str) -> str:
    """The label rofi shows for one folder, before collision suffixes."""
    label = base_of(folder)
    return "".join(ch for ch in label if ch not in ROFI_UNSAFE)


def labels_for(folders: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """(folder, label) in tab order, collisions suffixed like toggle.sh
    (``Coding``, ``Coding 2``); folders whose label empties out are dropped."""
    out: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for folder in sorted(folders):
        label = label_for(folder)
        if not label:
            continue
        if label in seen:
            seen[label] += 1
            label = f"{label} {seen[label]}"
        seen[label] = 1
        out.append((folder, label))
    return tuple(out)


def validate_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not NAME_RE.match(cleaned):
        raise ValueError(f"tab name must be {NAME_RULE}")
    return cleaned


def collides_with(name: str, existing_folders: Iterable[str]) -> str | None:
    """The existing folder whose rofi label equals the label ``name`` would
    get, or None. Refused rather than silently suffixed (plan §4)."""
    wanted = label_for(name)
    for folder in existing_folders:
        if label_for(folder) == wanted:
            return folder
    return None


def plan_renumber(ordered: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """(old, new) folder names that give ``ordered`` canonical ``NN_`` prefixes
    (10, 20, 30 …), widening the padding when the count needs it so
    ``100_`` never sorts before ``20_``. Unchanged names are omitted."""
    width = max(2, len(str(len(ordered) * STEP)))
    pairs = []
    for i, old in enumerate(ordered):
        new = f"{(i + 1) * STEP:0{width}d}_{base_of(old)}"
        if new != old:
            pairs.append((old, new))
    return tuple(pairs)
