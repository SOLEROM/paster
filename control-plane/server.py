"""paster front — the control plane over entries/ and config.yaml.

One template rendered once; everything after is the SPA (REST for state,
Socket.IO for "something moved"). Contracts kept the way the family keeps
them: ``X-Requested-With: paster`` on every mutating route, a strict CSP
with the framing rules from solSeed, ``asset_rev`` cache-busting, the
``{"error": "…"}`` envelope on every 4xx/5xx under /api, an optional
webterm, and the port precedence ``--port`` › ``.port`` › code default.

Run: ``../run.sh`` (venv, kits, webterm), or ``python server.py [--port N]
[--host H | --public]`` from an activated venv.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO
from werkzeug.exceptions import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules import actions, bash_bridge, config_store, entries_store, fileio  # noqa: E402
from modules import routes_common, routes_config, routes_doctor, routes_entries  # noqa: E402
from modules import watcher as watcher_mod  # noqa: E402
from modules import webterm_integration, webutil  # noqa: E402
from modules.activity_log import ActivityLog  # noqa: E402
from modules.paths import Paths, default_paths  # noqa: E402
from modules.webutil import APP_NAME  # noqa: E402

DEFAULT_PORT = 8790
DEFAULT_HOST = "127.0.0.1"
PUBLIC_HOST = "0.0.0.0"
WEBTERM_ENV = "PASTER_WEBTERM"
REMDEV_ENV = "PASTER_REMDEV_URL"

log = logging.getLogger(APP_NAME)


def read_port_file(paths: Paths) -> int | None:
    try:
        return int(paths.port_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def resolve_port(cli_port: int | None, paths: Paths) -> int:
    """``--port`` › ``.port`` › code default (myApps.md, family precedence)."""
    if cli_port:
        return cli_port
    return read_port_file(paths) or DEFAULT_PORT


def create_app(paths: Paths | None = None, *, use_webterm: bool | None = None,
               origins_env: str | None = None, remdev_url: str | None = None,
               port: int | None = None):
    paths = paths or default_paths()
    origins = os.environ.get(webutil.BENCH_SHELL_ORIGINS_VAR, "") if origins_env is None else origins_env
    webutil.frame_ancestors(origins, "")            # refuse to start on a malformed origin
    remdev = webutil.validate_remdev_url(os.environ.get(REMDEV_ENV, "") if remdev_url is None else remdev_url)

    app = Flask(APP_NAME, static_folder=str(paths.static_dir), template_folder=str(paths.templates_dir))
    socketio = SocketIO(app, cors_allowed_origins=[], async_mode="threading")
    activity = ActivityLog(emit=lambda name, payload: socketio.emit(name, payload))

    app.config.update(
        PATHS=paths, SOCKETIO=socketio, ACTIVITY=activity, WATCHER=None, PROBE=None,
        ACTION_RUNNER=actions.ActionRunner(paths),
        ORIGINS=origins, REMDEV_URL=remdev, PORT=port or resolve_port(None, paths),
        DISPLAY_AVAILABLE=bool(os.environ.get("DISPLAY")),
    )

    @app.get("/")
    def index():
        return render_template("index.html", app_name=APP_NAME, asset_rev=webutil.asset_rev(paths.static_dir),
                               use_webterm=app.config.get("WEBTERM_ENABLED", False), remdev_url=remdev,
                               repo_root=str(paths.repo_root))

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = webutil.content_security_policy(
            request.headers.get("Host", ""), origins, remdev)
        response.headers.pop("X-Frame-Options", None)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    _register_errors(app)
    for bp in (routes_common.bp, routes_entries.bp, routes_config.bp, routes_doctor.bp):
        app.register_blueprint(bp)

    if use_webterm is None:
        use_webterm = os.environ.get(WEBTERM_ENV, "1") != "0"
    app.config["WEBTERM_ENABLED"] = webterm_integration.mount(app, socketio, paths, use_webterm)
    activity.log("info", f"{APP_NAME} ready (webterm={'on' if app.config['WEBTERM_ENABLED'] else 'off'})")
    return app, socketio


def _register_errors(app: Flask) -> None:
    def envelope(message: str, status: int):
        if request.path.startswith("/api/"):
            return jsonify({"error": message}), status
        return message, status, {"Content-Type": "text/plain; charset=utf-8"}

    @app.errorhandler(HTTPException)
    def on_http(exc: HTTPException):
        return envelope(exc.description or exc.name, exc.code or 500)

    @app.errorhandler(entries_store.NotFound)
    @app.errorhandler(FileNotFoundError)
    def on_missing(exc):
        return envelope(str(exc) or "not found", 404)

    @app.errorhandler(entries_store.Conflict)
    def on_conflict(exc):
        return envelope(str(exc), 409)

    @app.errorhandler(fileio.StaleRevision)
    def on_stale(exc: fileio.StaleRevision):
        if request.path.startswith("/api/"):
            return jsonify({"error": str(exc), "current": exc.current}), 409
        return envelope(str(exc), 409)

    @app.errorhandler(actions.ActionError)
    def on_action(exc: actions.ActionError):
        return envelope(str(exc), exc.status)

    @app.errorhandler(ValueError)          # Invalid, BadInput, BadRelpath, bad JSON shapes
    def on_value(exc):
        return envelope(str(exc) or "invalid input", 400)

    @app.errorhandler(bash_bridge.BridgeError)
    def on_tooling(exc):
        log.error("%s", exc)
        paths = app.config["PATHS"]
        return envelope(webutil.redact_paths(str(exc), paths.repo_root, paths.entries_dir, paths.bin_dir, paths.data_dir), 500)

    @app.errorhandler(Exception)
    def on_unexpected(exc):
        log.exception("unhandled error")
        return envelope("internal error — see the server log", 500)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="paster-front")
    parser.add_argument("--port", type=int, default=None, help="listen port (default: .port, then 8790)")
    parser.add_argument("--host", default=None, help="bind address (default 127.0.0.1)")
    parser.add_argument("--public", action="store_true", help="bind 0.0.0.0 — a trusted network only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    paths = default_paths()
    port = resolve_port(args.port, paths)
    host = PUBLIC_HOST if args.public else (args.host or DEFAULT_HOST)
    app, socketio = create_app(paths, port=port)
    app.config["HOST"] = host
    watcher = watcher_mod.Watcher(paths, lambda name, payload: socketio.emit(name, payload))
    app.config["WATCHER"] = watcher
    watcher.start()
    print(f"{APP_NAME}: http://{host}:{port}  (webterm={app.config['WEBTERM_ENABLED']}, "
          f"display={'yes' if app.config['DISPLAY_AVAILABLE'] else 'no'})", flush=True)
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
