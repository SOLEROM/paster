"""One response shape for every route (plan §12)."""
import re

from conftest import CSRF, REPO_ROOT


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/nothing/here")
    assert r.status_code == 404 and r.get_json() == {"error": "no such route"} or r.get_json()["error"]
    assert r.headers["Content-Type"].startswith("application/json")


def test_method_not_allowed_is_json(client):
    r = client.post("/api/health", headers=CSRF)
    assert r.status_code == 405 and "error" in r.get_json()


def test_bad_json_body_is_400(client):
    r = client.put("/api/config", data="{not json", content_type="application/json", headers=CSRF)
    assert r.status_code == 400 and "JSON object" in r.get_json()["error"]


def test_unexpected_errors_are_json_500_without_a_traceback(app):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("secret detail")
    r = app.test_client().get("/api/boom")
    assert r.status_code == 500 and r.get_json() == {"error": "internal error — see the server log"}


def test_non_api_404_is_plain_text(client):
    r = client.get("/nothing")
    assert r.status_code == 404 and not r.headers["Content-Type"].startswith("application/json")


def test_every_api_route_is_documented(app):
    doc = (REPO_ROOT / "man" / "00-api.md").read_text(encoding="utf-8")
    rules = {str(r.rule) for r in app.url_map.iter_rules() if str(r.rule).startswith("/api/")}
    missing = [rule for rule in rules if re.sub(r"<[^>]*>", lambda m: "<" + m.group(0).strip("<>").split(":")[-1] + ">", rule) not in doc]
    assert not missing, f"undocumented routes: {missing}"
