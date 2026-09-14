"""Tabs and entries — the editing core over ``entries/<NN_Tab>/content.md``.

The format is the popup's (plan D3): one folder per tab, one non-empty
line per entry, nothing else. Labels come from ``toggle.sh --list-tabs``
(bash_bridge), every write goes through ``fileio.checked_write`` (rev
check + snapshot + atomic replace), and a deleted tab moves to the trash
folder under the data dir — nothing here calls ``rm -rf``.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from . import bash_bridge, fileio, tab_labels
from .paths import Paths

MAX_LINE = 4000          # rofi copes with far more; this stops a pasted file
LONG_LINE = 300          # the "long" chip threshold in the GUI (plan §4)


class NotFound(LookupError):
    """No such tab (or the id is not a safe folder name)."""


class Invalid(ValueError):
    """Bad input — refused at the boundary with the reason."""


class Conflict(Exception):
    """A name or label clash (a stale revision is fileio.StaleRevision)."""


@dataclass(frozen=True)
class Tab:
    id: str
    label: str
    count: int
    rev: str
    mtime: float


@dataclass(frozen=True)
class Listing:
    tabs: tuple[Tab, ...]
    ignored: tuple[str, ...]      # folders without a content.md
    unlabeled: tuple[str, ...]    # folders whose label empties out — rofi skips them


@dataclass(frozen=True)
class TabContent:
    id: str
    label: str
    lines: tuple[str, ...]
    rev: str


@dataclass(frozen=True)
class Hit:
    tab: str
    label: str
    index: int
    line: str


def relpath_of(tab_id: str) -> str:
    return f"entries/{tab_id}/content.md"


# ---------------------------------------------------------------- lookup ---

def _subfolders(paths: Paths) -> list[Path]:
    if not paths.entries_dir.is_dir():
        return []
    return sorted(p for p in paths.entries_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def tab_folders(paths: Paths) -> list[str]:
    """Folder names that ARE tabs (they hold a content.md), in tab order."""
    return [p.name for p in _subfolders(paths) if (p / "content.md").is_file()]


def tab_dir(paths: Paths, tab_id: str) -> Path:
    if not tab_labels.is_safe_id(tab_id):
        raise NotFound(f"no such tab: {tab_id!r}")
    target = paths.entries_dir / tab_id
    if paths.entries_dir.resolve() not in target.resolve().parents:
        raise NotFound(f"no such tab: {tab_id!r}")
    if not target.is_dir() or not (target / "content.md").is_file():
        raise NotFound(f"no such tab: {tab_id!r}")
    return target


def parse_lines(text: str) -> tuple[str, ...]:
    """The entries of a content.md: every non-blank line, ``\\r`` dropped."""
    return tuple(line.replace("\r", "") for line in text.splitlines() if line.strip())


def normalize_lines(lines: object) -> tuple[str, ...]:
    """Validate a client's line list: strings, one line each, blanks dropped."""
    if not isinstance(lines, list):
        raise Invalid("'lines' must be a list of strings")
    out = []
    for i, raw in enumerate(lines):
        if not isinstance(raw, str):
            raise Invalid(f"line {i + 1} is not a string")
        line = raw.replace("\r", "")
        if "\n" in line:
            raise Invalid(f"line {i + 1} contains a newline — one entry is one line")
        if len(line) > MAX_LINE:
            raise Invalid(f"line {i + 1} is longer than {MAX_LINE} characters")
        if line.strip():
            out.append(line)
    return tuple(out)


def render_lines(lines: Sequence[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


def _label_map(paths: Paths) -> dict[str, str]:
    return {folder.name: label for label, folder in bash_bridge.list_tabs(paths)}


def list_tabs(paths: Paths) -> Listing:
    labels = _label_map(paths)
    tabs, ignored, unlabeled = [], [], []
    for folder in _subfolders(paths):
        content = folder / "content.md"
        if not content.is_file():
            ignored.append(folder.name)
            continue
        label = labels.get(folder.name)
        if label is None:
            unlabeled.append(folder.name)
            continue
        text, rev = fileio.read_text(content)
        tabs.append(Tab(id=folder.name, label=label, count=len(parse_lines(text)),
                        rev=rev, mtime=content.stat().st_mtime))
    return Listing(tabs=tuple(tabs), ignored=tuple(ignored), unlabeled=tuple(unlabeled))


def _read_lines(paths: Paths, tab_id: str) -> tuple[tuple[str, ...], str]:
    """(lines, rev) of one tab, without asking bash for its label."""
    folder = tab_dir(paths, tab_id)
    text, rev = fileio.read_text(folder / "content.md")
    return parse_lines(text), rev


def read_tab(paths: Paths, tab_id: str, label: str | None = None) -> TabContent:
    lines, rev = _read_lines(paths, tab_id)
    if label is None:
        label = _label_map(paths).get(tab_id, tab_labels.label_for(tab_id))
    return TabContent(id=tab_id, label=label, lines=lines, rev=rev)


# ---------------------------------------------------------------- writes ---

def write_tab(paths: Paths, tab_id: str, lines: object, base_rev: str | None) -> str:
    tab_dir(paths, tab_id)
    clean = normalize_lines(lines)
    return fileio.checked_write(paths, relpath_of(tab_id), render_lines(clean), base_rev)


def move_entry(paths: Paths, from_id: str, index: int, to_id: str, position: int | None,
               base_from: str | None, base_to: str | None) -> tuple[str, str]:
    """Take line ``index`` out of one tab and put it into another at
    ``position`` (None = the end). Both revs are checked before either
    write, so a stale client changes nothing."""
    if from_id == to_id:
        raise Invalid("source and target tab are the same — reorder instead")
    with fileio.LOCK:
        src = read_tab(paths, from_id, label="")
        dst = read_tab(paths, to_id, label="")
        if base_from is not None and base_from != src.rev:
            raise fileio.StaleRevision(src.rev)
        if base_to is not None and base_to != dst.rev:
            raise fileio.StaleRevision(dst.rev)
        if not 0 <= index < len(src.lines):
            raise Invalid(f"no entry at index {index}")
        line = src.lines[index]
        new_src = src.lines[:index] + src.lines[index + 1:]
        at = len(dst.lines) if position is None else max(0, min(int(position), len(dst.lines)))
        new_dst = dst.lines[:at] + (line,) + dst.lines[at:]
        rev_src = fileio.checked_write(paths, relpath_of(from_id), render_lines(new_src), src.rev)
        try:
            rev_dst = fileio.checked_write(paths, relpath_of(to_id), render_lines(new_dst), dst.rev)
        except Exception:
            # The line is already out of the source file: put it back before
            # reporting, so a failed move never loses an entry.
            fileio.atomic_write_text(paths.entries_dir / from_id / "content.md", render_lines(src.lines))
            raise
        return rev_src, rev_dst


def _all_folder_names(paths: Paths) -> list[str]:
    return [p.name for p in _subfolders(paths)]


def _check_new_name(paths: Paths, name: str, *, except_folder: str | None = None) -> str:
    try:
        clean = tab_labels.validate_name(name)
    except ValueError as exc:
        raise Invalid(str(exc)) from exc
    others = [f for f in _all_folder_names(paths) if f != except_folder]
    clash = tab_labels.collides_with(clean, [f for f in others if (paths.entries_dir / f / "content.md").is_file()])
    if clash is not None:
        raise Conflict(f"a tab named {tab_labels.label_for(clash)!r} already exists ({clash})")
    return clean


def _apply_renames(paths: Paths, pairs: Sequence[tuple[str, str]]) -> None:
    """Rename folders in two phases through temporary names, so a plan that
    swaps two prefixes never tramples a folder that is still in use."""
    if not pairs:
        return
    for _, new in pairs:
        if (paths.entries_dir / new).exists() and new not in {old for old, _ in pairs}:
            raise Conflict(f"a folder named {new!r} is in the way")
    temps = []
    for old, new in pairs:
        tmp = paths.entries_dir / f".renaming-{uuid.uuid4().hex}"
        (paths.entries_dir / old).rename(tmp)
        temps.append((tmp, paths.entries_dir / new))
    for tmp, final in temps:
        tmp.rename(final)


def create_tab(paths: Paths, name: str, after: str | None = None) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Create ``NN_<name>`` after tab ``after`` (None = last). Returns the
    new folder name and the renames made to keep the prefixes canonical."""
    with fileio.LOCK:
        clean = _check_new_name(paths, name)
        ordered = tab_folders(paths)
        if after is not None:
            if after not in ordered:
                raise NotFound(f"no such tab: {after!r}")
            at = ordered.index(after) + 1
        else:
            at = len(ordered)
        placeholder = f"0_{clean}"
        plan = tab_labels.plan_renumber(ordered[:at] + [placeholder] + ordered[at:])
        new_name = dict(plan).get(placeholder, placeholder)
        renames = tuple((old, new) for old, new in plan if old != placeholder)
        _apply_renames(paths, renames)
        folder = paths.entries_dir / new_name
        if folder.exists():
            raise Conflict(f"a folder named {new_name!r} is in the way")
        folder.mkdir(parents=True)
        fileio.atomic_write_text(folder / "content.md", "")
        return new_name, renames


def rename_tab(paths: Paths, tab_id: str, name: str) -> str:
    with fileio.LOCK:
        tab_dir(paths, tab_id)
        clean = _check_new_name(paths, name, except_folder=tab_id)
        prefix = tab_labels.prefix_of(tab_id)
        new_name = clean if prefix is None else f"{tab_id[:len(tab_id) - len(tab_labels.base_of(tab_id))]}{clean}"
        if new_name == tab_id:
            return tab_id
        _apply_renames(paths, [(tab_id, new_name)])
        return new_name


def reorder_tabs(paths: Paths, ids: Sequence[str]) -> tuple[tuple[str, str], ...]:
    with fileio.LOCK:
        current = tab_folders(paths)
        if not isinstance(ids, list) or sorted(ids) != sorted(current) or len(set(ids)) != len(ids):
            raise Invalid("'ids' must list every tab exactly once")
        plan = tab_labels.plan_renumber(ids)
        _apply_renames(paths, plan)
        return plan


def delete_tab(paths: Paths, tab_id: str) -> Path:
    with fileio.LOCK:
        folder = tab_dir(paths, tab_id)
        paths.trash_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        target = paths.trash_dir / f"{stamp}_{tab_id}"
        n = 1
        while target.exists():
            target = paths.trash_dir / f"{stamp}_{tab_id}-{n}"
            n += 1
        shutil.move(str(folder), str(target))
        return target


# ---------------------------------------------------------------- reads ---

def search(paths: Paths, query: str) -> tuple[Hit, ...]:
    q = (query or "").strip().lower()
    hits = []
    for tab in list_tabs(paths).tabs:              # one bash spawn for every tab's label
        lines, _ = _read_lines(paths, tab.id)
        for i, line in enumerate(lines):
            if not q or q in line.lower():
                hits.append(Hit(tab=tab.id, label=tab.label, index=i, line=line))
    return tuple(hits)


def health(paths: Paths) -> dict:
    """Facts the Doctor shows: counts, empty tabs, duplicates, long lines."""
    listing = list_tabs(paths)
    seen: dict[str, str] = {}
    duplicates, long_lines, empty = [], [], []
    total = 0
    for tab in listing.tabs:
        lines, _ = _read_lines(paths, tab.id)
        total += len(lines)
        if not lines:
            empty.append(tab.id)
        for line in lines:
            if len(line) > LONG_LINE:
                long_lines.append({"tab": tab.id, "line": line[:80]})
            if line in seen and seen[line] != tab.id:
                duplicates.append({"line": line[:80], "tabs": [seen[line], tab.id]})
            seen.setdefault(line, tab.id)
    return {"tabs": len(listing.tabs), "entries": total, "empty_tabs": empty,
            "ignored": list(listing.ignored), "unlabeled": list(listing.unlabeled),
            "duplicates": duplicates, "long_lines": long_lines}
