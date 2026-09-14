"""HTTP plumbing shared by every route: the error envelope, the CSRF guard,
the CSP (with the family's framing rules) and cache-busting.

``frame_ancestors``/``frame_src`` are solSeed's reference implementation
(app/webutil.py, 2026-08-31), copied with their docstrings — see
solBench/mainBench/framingLessons.md for why every rule is the way it is.
"""
from __future__ import annotations

import re
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import jsonify, request

APP_NAME = "paster"
CSRF_HEADER = "X-Requested-With"
BENCH_SHELL_ORIGINS_VAR = "BENCH_SHELL_ORIGINS"

# A bare hostname / IPv4, or a bracketed IPv6 literal. Anything else in the
# Host header (spaces, quotes, semicolons, control bytes) is dropped rather
# than spliced into a response header.
_CSP_HOST_RE = re.compile(r"^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._-]+)$")
# One http(s) origin: scheme://host[:port] — no path, query, userinfo, or
# anything else that has no business inside a response header.
_ORIGIN_RE = re.compile(r"^https?://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._-]+)(:[0-9]{1,5})?$")


class BadInput(ValueError):
    """A request failed validation — rendered as a 400 envelope."""


def error(message: str, status: int = 400):
    return jsonify({"error": str(message)}), status


def json_object() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadInput("request body must be a JSON object")
    return body


def csrf_required(view):
    """Every mutating route. A browser cannot attach a custom header to a
    cross-origin form post, so a random page cannot drive this API. A
    guard, not authentication."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.headers.get(CSRF_HEADER) != APP_NAME:
            return error(f"missing {CSRF_HEADER} header", 403)
        return view(*args, **kwargs)
    return wrapped


def redact_paths(message: str, *roots: Path) -> str:
    """A tooling message with the repo root and the home dir spelled as
    placeholders — an error body is client-visible on a no-auth tailnet."""
    out = message
    for root in roots:
        if root:
            out = out.replace(str(root), "<repo>")
    home = str(Path.home())
    return out.replace(home, "~") if home else out


def asset_rev(static_dir: Path) -> int:
    return max((int(p.stat().st_mtime) for p in static_dir.rglob("*") if p.is_file()), default=0)


def hostname_only(host_header: str) -> str:
    """The host the browser used, without its port ("[::1]:6012" → "[::1]")."""
    host = (host_header or "").strip()
    if host.startswith("["):                       # IPv6 literal
        end = host.find("]")
        return host[:end + 1] if end != -1 else ""
    return host.split(":", 1)[0]


def frame_ancestors(origins_env: str = "", host_header: str = "") -> str:
    """The `frame-ancestors` directive — who may *frame* this app.

    Always sent: 'self' alone is the real default-deny (an absent header
    allows framing in every browser), and it keeps same-origin embeds
    working. The request's own host joins on any port: the mainBench shell
    builds every frame URL from `location.hostname`, so shell and app always
    share a hostname, and echoing it means a service restart docks the app
    on any host with zero per-host config. A Host header that isn't a plain
    host is dropped, never trusted.

    The env value adds the origins of a shell on a *different* machine.
    That is operator config bound for a response header: a malformed entry
    silently dropped would strand the shell with no clue, spliced in it
    would rewrite the CSP — so refuse to start instead.
    """
    sources = ["'self'"]
    name = hostname_only(host_header)
    if name and _CSP_HOST_RE.match(name):
        sources += [f"http://{name}:*", f"https://{name}:*"]
    for token in (origins_env or "").split():
        if token.count("/") == 3 and token.endswith("/"):
            token = token[:-1]          # an address bar hands out a slash
        if not _ORIGIN_RE.match(token):
            raise ValueError(
                f"{BENCH_SHELL_ORIGINS_VAR}: {token!r} is not an http(s) "
                "origin (expected scheme://host[:port], space-separated)")
        if token not in sources:
            sources.append(token)
    return "frame-ancestors " + " ".join(sources)


def frame_src(host_header: str, pin: str = "") -> str:
    """The `frame-src` directive for the cldBar embed — the ONE outbound
    hole in the CSP: this same hostname on any port, both schemes, plus the
    pinned remdev origin when there is one."""
    sources = []
    name = hostname_only(host_header)
    if name and _CSP_HOST_RE.match(name):
        sources += [f"http://{name}:*", f"https://{name}:*"]
    parts = urlsplit(pin or "")
    if parts.scheme in ("http", "https") and parts.netloc and _CSP_HOST_RE.match(hostname_only(parts.netloc)):
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in sources:
            sources.append(origin)
    return "frame-src " + (" ".join(sources) if sources else "'none'")


def validate_remdev_url(value: str) -> str:
    """'' (derive browser-side) or an http(s) origin; anything else is refused
    at startup — it lands in an iframe src."""
    pin = (value or "").strip().rstrip("/")
    if pin and not _ORIGIN_RE.match(pin):
        raise ValueError(f"PASTER_REMDEV_URL: {pin!r} is not an http(s) origin")
    return pin


def content_security_policy(host_header: str, origins_env: str, remdev_pin: str) -> str:
    return "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",      # xterm/webterm set inline styles
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self' ws: wss:",
        frame_src(host_header, remdev_pin),
        "object-src 'none'",
        "base-uri 'self'",
        frame_ancestors(origins_env, host_header),
    ])
