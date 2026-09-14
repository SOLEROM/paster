"""The Doctor's checks and the gated desktop actions (plan §6, §13)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from . import doctor
from .routes_entries import _emit, _log, _paths
from .webutil import csrf_required

bp = Blueprint("doctor", __name__, url_prefix="/api")


def _runner():
    return current_app.config["ACTION_RUNNER"]


def _probe():
    return current_app.config.get("PROBE") or doctor.default_probe()


@bp.get("/doctor")
def report():
    last = _runner().last("run_tests")
    data = doctor.run_checks(_paths(), _probe(), port=current_app.config.get("PORT"),
                             last_test_run=last.as_dict() if last else None)
    data["actions"] = _runner().available()
    return jsonify(data)


@bp.get("/actions")
def actions():
    return jsonify({"actions": _runner().available()})


@bp.post("/actions/<name>")
@csrf_required
def run_action(name: str):
    result = _runner().run(name)
    _log("info" if result.rc == 0 else "warn",
         f"action {name}: rc={result.rc}" + (" (timed out)" if result.timed_out else ""))
    _emit("doctor_changed", {"action": name})
    return jsonify(result.as_dict())
