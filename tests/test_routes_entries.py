from conftest import CSRF


def get_tab(client, tab_id="10_Coding"):
    return client.get(f"/api/tabs/{tab_id}/entries").get_json()


def test_list_tabs(client):
    data = client.get("/api/tabs").get_json()
    assert [t["label"] for t in data["tabs"]] == ["Coding", "Writing", "General"]
    assert data["tabs"][0]["count"] == 5 and data["ignored"] == [] and data["unlabeled"] == []


def test_read_and_write_entries(client):
    tab = get_tab(client)
    lines = tab["lines"][::-1]
    r = client.put("/api/tabs/10_Coding/entries", json={"lines": lines, "base_rev": tab["rev"]}, headers=CSRF)
    assert r.status_code == 200 and r.get_json()["count"] == 5
    assert get_tab(client)["lines"] == lines
    stale = client.put("/api/tabs/10_Coding/entries", json={"lines": ["x"], "base_rev": tab["rev"]}, headers=CSRF)
    assert stale.status_code == 409 and "changed on disk" in stale.get_json()["error"]
    assert "current" in stale.get_json()


def test_write_validation_and_not_found(client):
    assert client.put("/api/tabs/10_Coding/entries", json={"lines": ["a\nb"]}, headers=CSRF).status_code == 400
    assert client.put("/api/tabs/10_Coding/entries", json={"lines": "x"}, headers=CSRF).status_code == 400
    assert client.put("/api/tabs/10_Coding/entries", json={"lines": ["a"], "base_rev": 5}, headers=CSRF).status_code == 400
    assert client.put("/api/tabs/10_Coding/entries", data="nope", headers=CSRF).status_code == 400
    assert client.get("/api/tabs/99_Nope/entries").status_code == 404
    assert client.get("/api/tabs/..%2Fconfig.yaml/entries").status_code == 404


def test_tab_lifecycle(client):
    r = client.post("/api/tabs", json={"name": "Prompts"}, headers=CSRF)
    assert r.status_code == 201 and r.get_json() == {"id": "40_Prompts", "renames": []}
    r = client.post("/api/tabs", json={"name": "Mid", "after": "10_Coding"}, headers=CSRF)
    assert r.status_code == 201 and r.get_json()["id"] == "20_Mid"
    assert client.post("/api/tabs", json={"name": "Coding"}, headers=CSRF).status_code == 409
    assert client.post("/api/tabs", json={"name": "../x"}, headers=CSRF).status_code == 400
    assert client.post("/api/tabs", json={}, headers=CSRF).status_code == 400
    assert client.post("/api/tabs", json={"name": "Ok", "after": 7}, headers=CSRF).status_code == 400
    assert client.post("/api/tabs", json={"name": "Ok", "after": "99_X"}, headers=CSRF).status_code == 404
    r = client.patch("/api/tabs/20_Mid", json={"name": "Middle"}, headers=CSRF)
    assert r.get_json() == {"id": "20_Middle"}
    assert client.patch("/api/tabs/20_Middle", json={}, headers=CSRF).status_code == 400
    ids = [t["id"] for t in client.get("/api/tabs").get_json()["tabs"]]
    r = client.put("/api/tabs/order", json={"ids": ids[::-1]}, headers=CSRF)
    assert r.status_code == 200 and len(r.get_json()["renames"]) == 4
    assert client.put("/api/tabs/order", json={"ids": ids[:1]}, headers=CSRF).status_code == 400
    ids = [t["id"] for t in client.get("/api/tabs").get_json()["tabs"]]
    r = client.delete(f"/api/tabs/{ids[0]}", headers=CSRF)
    assert r.status_code == 200 and r.get_json()["ok"] and "trash" in r.get_json()["trash"]
    assert client.delete(f"/api/tabs/{ids[0]}", headers=CSRF).status_code == 404


def test_move_entry(client):
    src, dst = get_tab(client, "10_Coding"), get_tab(client, "20_Writing")
    body = {"from": "10_Coding", "index": 0, "to": "20_Writing", "position": 0,
            "base_from": src["rev"], "base_to": dst["rev"]}
    r = client.post("/api/entries/move", json=body, headers=CSRF)
    assert r.status_code == 200 and set(r.get_json()) == {"rev_from", "rev_to"}
    assert get_tab(client, "20_Writing")["lines"][0] == src["lines"][0]
    assert client.post("/api/entries/move", json=body, headers=CSRF).status_code == 409
    for bad in [{**body, "index": "0"}, {**body, "from": 1}, {**body, "position": "x"}, {**body, "index": True}]:
        assert client.post("/api/entries/move", json=bad, headers=CSRF).status_code == 400


def test_search(client):
    hits = client.get("/api/search?q=FOLLOWING").get_json()["hits"]
    assert hits and all("following" in h["line"].lower() for h in hits)
    assert {"tab", "label", "index", "line"} <= set(hits[0])


def test_history_list_read_restore(client):
    tab = get_tab(client)
    client.put("/api/tabs/10_Coding/entries", json={"lines": ["one"], "base_rev": tab["rev"]}, headers=CSRF)
    hist = client.get("/api/history?file=entries/10_Coding/content.md").get_json()
    assert len(hist["snapshots"]) == 1
    ts = hist["snapshots"][0]["ts"]
    snap = client.get(f"/api/history/snapshot?file=entries/10_Coding/content.md&ts={ts}").get_json()
    assert snap["content"].startswith("Explain this code")
    cur = get_tab(client)["rev"]
    r = client.post("/api/history/restore", json={"file": "entries/10_Coding/content.md", "ts": ts, "base_rev": cur}, headers=CSRF)
    assert r.status_code == 200 and get_tab(client)["lines"] == tab["lines"]
    assert client.get("/api/history?file=README.md").status_code == 400
    assert client.get("/api/history/snapshot?file=config.yaml&ts=../x").status_code == 404
    assert client.post("/api/history/restore", json={"file": "config.yaml"}, headers=CSRF).status_code == 400
    assert client.post("/api/history/restore", json={"file": "config.yaml", "ts": "nope"}, headers=CSRF).status_code == 404
