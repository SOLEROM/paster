"""The views the front has, and the ones it deliberately does not (removed
2026-09-14 on request: the Changes/git view and the Preview mock). Open popup
lives in the title bar; the Sessions shell button exists only with webterm."""
import re
from pathlib import Path

from server import create_app

TEMPLATE = Path(__file__).resolve().parents[1] / "control-plane" / "templates" / "index.html"


def _views(html):
    return re.findall(r'data-view="([a-z]+)"', html)


def test_the_activity_bar_has_exactly_these_views(client):
    html = client.get("/").get_data(as_text=True)
    assert _views(html) == ["entries", "doctor", "sessions", "config", "help"]
    for gone in ("panel-preview", "panel-changes", "preview.js", "changes.js"):
        assert gone not in html


def test_open_popup_sits_in_the_titlebar_on_every_view(client):
    html = client.get("/").get_data(as_text=True)
    header = html.split("</header>")[0]
    assert 'id="btn-popup-open"' in header
    assert html.count('id="btn-popup-open"') == 1


def test_the_git_api_is_gone(client):
    r = client.get("/api/git/status")
    assert r.status_code == 404 and "error" in r.get_json()


def test_the_sessions_shell_button_needs_webterm(paths):
    src = TEMPLATE.read_text(encoding="utf-8")
    on = src.index("{% if use_webterm %}", src.index('id="panel-sessions"'))
    off = src.index("{% else %}", on)
    assert 'id="btn-shell-repo"' in src[on:off] and 'id="btn-shell-repo"' not in src[off:]
    app, _ = create_app(paths, use_webterm=False)
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'id="btn-shell-repo"' not in html
