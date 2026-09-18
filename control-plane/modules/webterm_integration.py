"""Mount solBench/webterm when the library is importable (plan §8).

Policy lives here: the client sends ids, never paths or commands. One
session kind — a shell in the repo root — is all this app needs.
"""
from __future__ import annotations

import logging
import os
import sys

from .paths import Paths
from .webutil import APP_NAME

log = logging.getLogger(APP_NAME)


def trusted_networks(default: str) -> tuple:
    """CIDRs besides loopback that get a shell: the tailnet unless overridden."""
    raw = os.environ.get("PASTER_WEBTERM_TRUSTED_NETS", default)
    return tuple(net.strip() for net in raw.split(",") if net.strip())


def mount(app, socketio, paths: Paths, enabled: bool) -> bool:
    if not enabled:
        return False
    try:
        import webterm
        from webterm import SpawnSpec, TerminalConfig

        def spawn_resolver(payload: dict) -> SpawnSpec:
            return SpawnSpec(tmux_name="shell", cwd=str(paths.repo_root), label="shell",
                             metadata={"kind": "workspace"})

        nets = trusted_networks(webterm.TAILSCALE_CGNAT)
        config = TerminalConfig(tmux_socket=f"{APP_NAME}-term", tmux_prefix=f"{APP_NAME}-",
                                trusted_networks=nets)
        try:
            if str(paths.static_dir) not in sys.path:
                sys.path.insert(0, str(paths.static_dir))
            from theme4col import terminal_themes          # 4ColThems copy-in
            config.themes = terminal_themes(paths.static_dir / "terminal-themes.json")
        except (ImportError, OSError, ValueError):
            log.warning("4ColThems terminal palettes not loaded — webterm defaults")
        webterm.init_app(app, socketio, config, spawn_resolver=spawn_resolver)
        log.info("webterm auth: loopback%s", "".join(f"+{n}" for n in nets))
        return True
    except Exception:  # noqa: BLE001 — a broken terminal must not take the app down
        log.exception("webterm unavailable — starting without a terminal")
        return False
