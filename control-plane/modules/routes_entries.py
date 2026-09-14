"""Tabs, entries, search and the snapshot history (plan §4)."""
from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, current_app, jsonify, request

from . import entries_store as es
from . import fileio, history
from .webutil import BadInput, csrf_required, json_object

bp = Blueprint("entries", __name__, url_prefix="/api")


def _paths():
    return current_app.config["PATHS"]


def _log(level: str, message: str) -> None:
    current_app.config["ACTIVITY"].log(level, message)


def _emit(name: str, payload: dict | None = None) -> None:
    """Push a change and tell the watcher this write was ours."""
    sio = current_app.config.get("SOCKETIO")
    if sio is not None:
        sio.emit(name, payload or {})
    watcher = current_app.config.get("WATCHER")
    if watcher is not None:
        watcher.mark_clean()


def _base_rev(body: dict, key: str = "base_rev") -> str | None:
    rev = body.get(key)
    if rev is not None and not isinstance(rev, str):
        raise BadInput(f"'{key}' must be a string")
    return rev


# ---------------------------------------------------------------- tabs ---

@bp.get("/tabs")
def list_tabs():
    listing = es.list_tabs(_paths())
    return jsonify({"tabs": [asdict(t) for t in listing.tabs], "ignored": list(listing.ignored),
                    "unlabeled": list(listing.unlabeled)})


@bp.post("/tabs")
@csrf_required
def create_tab():
    body = json_object()
    name = body.get("name")
    after = body.get("after")
    if not isinstance(name, str):
        raise BadInput("'name' is required")
    if after is not None and not isinstance(after, str):
        raise BadInput("'after' must be a tab id")
    new_id, renames = es.create_tab(_paths(), name, after)
    _log("info", f"created tab {new_id}" + (f" (renumbered {len(renames)})" if renames else ""))
    _emit("tabs_changed")
    return jsonify({"id": new_id, "renames": [list(p) for p in renames]}), 201


@bp.patch("/tabs/<tab_id>")
@csrf_required
def rename_tab(tab_id: str):
    body = json_object()
    name = body.get("name")
    if not isinstance(name, str):
        raise BadInput("'name' is required")
    new_id = es.rename_tab(_paths(), tab_id, name)
    if new_id != tab_id:
        _log("info", f"renamed tab {tab_id} → {new_id}")
        _emit("tabs_changed")
    return jsonify({"id": new_id})


@bp.put("/tabs/order")
@csrf_required
def reorder_tabs():
    body = json_object()
    renames = es.reorder_tabs(_paths(), body.get("ids"))
    _log("info", f"reordered tabs ({len(renames)} renamed)")
    _emit("tabs_changed")
    return jsonify({"renames": [list(p) for p in renames]})


@bp.delete("/tabs/<tab_id>")
@csrf_required
def delete_tab(tab_id: str):
    trash = es.delete_tab(_paths(), tab_id)
    _log("warn", f"deleted tab {tab_id} → {trash}")
    _emit("tabs_changed")
    return jsonify({"ok": True, "trash": str(trash)})


# ---------------------------------------------------------------- entries ---

@bp.get("/tabs/<tab_id>/entries")
def read_entries(tab_id: str):
    tab = es.read_tab(_paths(), tab_id)
    return jsonify({"id": tab.id, "label": tab.label, "lines": list(tab.lines), "rev": tab.rev})


@bp.put("/tabs/<tab_id>/entries")
@csrf_required
def write_entries(tab_id: str):
    body = json_object()
    lines = body.get("lines")
    rev = es.write_tab(_paths(), tab_id, lines, _base_rev(body))
    count = len(es.normalize_lines(lines))
    _log("info", f"saved {tab_id}: {count} entries (rev {rev})")
    _emit("entries_changed", {"tab": tab_id})
    return jsonify({"rev": rev, "count": count})


@bp.post("/entries/move")
@csrf_required
def move_entry():
    body = json_object()
    src, dst = body.get("from"), body.get("to")
    if not isinstance(src, str) or not isinstance(dst, str):
        raise BadInput("'from' and 'to' are tab ids")
    index, position = body.get("index"), body.get("position")
    if not isinstance(index, int) or isinstance(index, bool):
        raise BadInput("'index' must be an integer")
    if position is not None and (not isinstance(position, int) or isinstance(position, bool)):
        raise BadInput("'position' must be an integer or null")
    rev_from, rev_to = es.move_entry(_paths(), src, index, dst, position,
                                     _base_rev(body, "base_from"), _base_rev(body, "base_to"))
    _log("info", f"moved entry {index} from {src} to {dst}")
    _emit("entries_changed", {"tab": src})
    _emit("entries_changed", {"tab": dst})
    return jsonify({"rev_from": rev_from, "rev_to": rev_to})


@bp.get("/search")
def search():
    hits = es.search(_paths(), request.args.get("q", ""))
    return jsonify({"hits": [asdict(h) for h in hits]})


# ---------------------------------------------------------------- history ---

def _relpath_arg(source: dict) -> str:
    rel = source.get("file")
    if not isinstance(rel, str):
        raise BadInput("'file' is required")
    fileio.resolve_relpath(_paths(), rel)      # confinement
    return rel


@bp.get("/history")
def list_history():
    rel = _relpath_arg(request.args)
    snaps = history.list_snapshots(_paths(), rel)
    return jsonify({"file": rel, "snapshots": [asdict(s) for s in snaps]})


@bp.get("/history/snapshot")
def read_snapshot():
    rel = _relpath_arg(request.args)
    ts = request.args.get("ts", "")
    return jsonify({"file": rel, "ts": ts, "content": history.read_snapshot(_paths(), rel, ts)})


@bp.post("/history/restore")
@csrf_required
def restore_snapshot():
    body = json_object()
    rel = _relpath_arg(body)
    ts = body.get("ts")
    if not isinstance(ts, str):
        raise BadInput("'ts' is required")
    content = history.read_snapshot(_paths(), rel, ts)
    rev = fileio.checked_write(_paths(), rel, content, _base_rev(body))
    _log("warn", f"restored {rel} from snapshot {ts}")
    _emit("config_changed" if rel == fileio.CONFIG_RELPATH else "entries_changed",
          {} if rel == fileio.CONFIG_RELPATH else {"tab": rel.split("/")[1]})
    return jsonify({"rev": rev})
