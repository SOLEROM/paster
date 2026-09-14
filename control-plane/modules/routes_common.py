"""Health, help pages and the activity log."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from . import help_docs
from .webutil import APP_NAME, error

bp = Blueprint("common", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    cfg = current_app.config
    return jsonify({"ok": True, "app": APP_NAME, "webterm": bool(cfg.get("WEBTERM_ENABLED")),
                    "display": bool(cfg.get("DISPLAY_AVAILABLE")), "port": cfg.get("PORT")})


@bp.get("/help/tree")
def help_tree():
    man = current_app.config["PATHS"].man_dir
    return jsonify({"tree": help_docs.help_tree(man), "root": man.name, "missing": not man.is_dir()})


@bp.get("/help/page")
def help_page():
    man = current_app.config["PATHS"].man_dir
    target = help_docs.safe_doc(man, request.args.get("file", ""))
    if target is None:
        return error("no such page", 404)
    return jsonify({"content": target.read_text(encoding="utf-8")})


@bp.get("/logs")
def logs():
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        return error("'limit' must be an integer")
    return jsonify({"entries": current_app.config["ACTIVITY"].entries(limit)})
