"""config.yaml: the form, the raw file, the schema and pre-flight checks (plan §5)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from . import config_schema, config_store
from .routes_entries import _base_rev, _emit, _log, _paths
from .webutil import BadInput, csrf_required, json_object

bp = Blueprint("config", __name__, url_prefix="/api")


def _doc_json(doc: config_store.ConfigDoc) -> dict:
    return {"raw": doc.raw, "rev": doc.rev, "values": doc.values, "effective": doc.effective,
            "warnings": list(doc.warnings), "missing": list(doc.missing),
            "schema": config_schema.schema_json()}


@bp.get("/config")
def read_config():
    return jsonify(_doc_json(config_store.read_config(_paths())))


@bp.get("/config/schema")
def schema():
    return jsonify(config_schema.schema_json())


@bp.put("/config")
@csrf_required
def write_values():
    body = json_object()
    values = body.get("values")
    if not isinstance(values, dict) or not values:
        raise BadInput("'values' must be a non-empty object")
    doc = config_store.write_values(_paths(), values, _base_rev(body))
    _log("warn" if doc.warnings else "info",
         f"config saved: {', '.join(sorted(values))}" + (f" — {len(doc.warnings)} warning(s)" if doc.warnings else ""))
    _emit("config_changed")
    return jsonify(_doc_json(doc))


@bp.put("/config/raw")
@csrf_required
def write_raw():
    body = json_object()
    doc = config_store.write_raw(_paths(), body.get("text"), _base_rev(body))
    _log("warn" if doc.warnings else "info", "config saved (raw)")
    _emit("config_changed")
    return jsonify(_doc_json(doc))


@bp.post("/config/preflight")
@csrf_required
def preflight():
    body = json_object()
    return jsonify({"fields": config_store.preflight(body.get("values"))})
