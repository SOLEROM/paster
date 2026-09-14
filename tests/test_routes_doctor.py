import pytest

from conftest import CSRF
from modules import actions
from fakes import FakeRunner, make_probe, write_dropin


@pytest.fixture
def wired(app, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    rt.mkdir()
    write_dropin(home, "Ctrl+space", str(app.config["PATHS"].toggle_script))
    app.config["PROBE"] = make_probe(home, rt)
    fake = FakeRunner(out="[paster] done")
    app.config["ACTION_RUNNER"] = actions.ActionRunner(
        app.config["PATHS"], env_provider=lambda: {"DISPLAY": ":1"}, runner=fake, runtime_dir=str(rt))
    return app.test_client(), fake


def test_doctor_report(wired):
    client, _ = wired
    data = client.get("/api/doctor").get_json()
    assert data["summary"]["fail"] == 0 and data["hotkey_drift"] is False
    assert {a["name"] for a in data["actions"]} == {"open_popup", "apply_install", "run_tests", "clear_state"}
    assert next(c for c in data["checks"] if c["id"] == "tests")["status"] == "na"


def test_actions_run_and_report(wired):
    client, fake = wired
    r = client.post("/api/actions/run_tests", headers=CSRF)
    assert r.status_code == 200 and r.get_json()["ok"] and r.get_json()["output"] == "[paster] done"
    assert fake.calls[-1][0][-1].endswith("tests/run.sh")
    assert next(c for c in client.get("/api/doctor").get_json()["checks"] if c["id"] == "tests")["status"] == "ok"
    assert client.post("/api/actions/run_tests", headers=CSRF).status_code == 409     # cooldown
    assert client.post("/api/actions/nope", headers=CSRF).status_code == 404
    assert client.post("/api/actions/run_tests").status_code == 403
    assert client.get("/api/actions").get_json()["actions"][0]["name"] == "open_popup"


def test_actions_without_a_display(app, tmp_path):
    app.config["ACTION_RUNNER"] = actions.ActionRunner(app.config["PATHS"], env_provider=lambda: {}, runner=FakeRunner())
    client = app.test_client()
    r = client.post("/api/actions/open_popup", headers=CSRF)
    assert r.status_code == 503 and "DISPLAY" in r.get_json()["error"]
