from conftest import CSRF


def test_read_config_carries_schema_and_effective_values(client):
    data = client.get("/api/config").get_json()
    assert data["values"]["hotkey"] == "Ctrl+space" and data["effective"]["font_size"] == "12"
    assert data["warnings"] == [] and data["missing"] == []
    assert {s["id"] for s in data["schema"]["sections"]} == {"hotkey", "size", "look", "paste"}
    assert client.get("/api/config/schema").get_json()["fields"][0]["key"] == "hotkey"


def test_write_values_and_warnings(client):
    doc = client.get("/api/config").get_json()
    r = client.put("/api/config", json={"values": {"width_pct": 999, "font_size": 14}, "base_rev": doc["rev"]}, headers=CSRF)
    assert r.status_code == 200
    body = r.get_json()
    assert body["values"]["width_pct"] == "999" and body["effective"]["width_pct"] == "100"
    assert any("width_pct" in w for w in body["warnings"])
    assert client.put("/api/config", json={"values": {"font_size": 15}, "base_rev": doc["rev"]}, headers=CSRF).status_code == 409
    assert client.put("/api/config", json={"values": {}}, headers=CSRF).status_code == 400
    assert client.put("/api/config", json={"values": {"nope": 1}}, headers=CSRF).status_code == 400


def test_write_raw(client):
    doc = client.get("/api/config").get_json()
    r = client.put("/api/config/raw", json={"text": "hotkey: \"Mod4+p\"\n", "base_rev": doc["rev"]}, headers=CSRF)
    assert r.status_code == 200 and r.get_json()["values"] == {"hotkey": "Mod4+p"}
    assert len(r.get_json()["missing"]) == 13
    assert client.put("/api/config/raw", json={"text": 5}, headers=CSRF).status_code == 400


def test_preflight(client):
    r = client.post("/api/config/preflight", json={"values": {"opacity_pct": "3"}}, headers=CSRF)
    assert r.get_json()["fields"]["opacity_pct"]["ok"] is False
    assert client.post("/api/config/preflight", json={"values": 1}, headers=CSRF).status_code == 400
