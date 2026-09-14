"""What is and is not protected (plan §11)."""
import re

from conftest import CSRF, REPO_ROOT


def test_security_headers_on_every_response(client):
    for path in ("/", "/api/health", "/api/nope"):
        h = client.get(path).headers
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["Referrer-Policy"] == "no-referrer"
        assert "script-src 'self'" in h["Content-Security-Policy"]
        assert "X-Frame-Options" not in h


def test_every_mutating_route_needs_the_csrf_header(app):
    client = app.test_client()
    for rule in app.url_map.iter_rules():
        path = str(rule.rule)
        if not path.startswith("/api/"):
            continue
        for method in rule.methods & {"POST", "PUT", "PATCH", "DELETE"}:
            concrete = re.sub(r"<[^>]*>", "x", path)
            r = client.open(concrete, method=method, json={})
            assert r.status_code == 403, f"{method} {concrete} answered {r.status_code} without the header"
            assert r.get_json()["error"].startswith("missing X-Requested-With")


def test_a_wrong_csrf_value_is_refused(client):
    assert client.post("/api/tabs", json={"name": "x"}, headers={"X-Requested-With": "other"}).status_code == 403


def test_no_inline_scripts_in_the_page(client):
    body = client.get("/").get_data(as_text=True)
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", body)


def test_only_known_actions_run(client):
    assert client.post("/api/actions/rm_-rf", headers=CSRF).status_code == 404
    assert client.post("/api/actions/..%2Fx", headers=CSRF).status_code == 404


def test_error_messages_never_carry_absolute_repo_paths(client, paths):
    r = client.get("/api/tabs/99_Nope/entries")
    assert str(paths.repo_root) not in r.get_json()["error"]


def test_the_page_never_uses_raw_hex_in_app_css():
    css = (REPO_ROOT / "control-plane" / "static" / "css" / "app.css").read_text()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "raw hex in app.css — use 4ColThems tokens"


def test_tooling_errors_never_carry_absolute_paths(paths, tmp_path, monkeypatch):
    """A broken checkout (no bin/) surfaces as a 500 whose body names no host path."""
    from dataclasses import replace
    from server import create_app
    broken = replace(paths, bin_dir=tmp_path / "nobin")
    app, _ = create_app(broken, use_webterm=False)
    r = app.test_client().get("/api/tabs")
    assert r.status_code == 500
    body = r.get_json()["error"]
    assert str(tmp_path) not in body and "/home/" not in body
    assert "toggle.sh" in body
