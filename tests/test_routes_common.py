from dataclasses import replace

from server import create_app


def test_health_and_logs(client):
    h = client.get("/api/health").get_json()
    assert h["ok"] and h["app"] == "paster" and h["webterm"] is False and h["port"] == 8790
    logs = client.get("/api/logs?limit=5").get_json()["entries"]
    assert logs and logs[-1]["message"].startswith("paster ready")
    assert client.get("/api/logs?limit=x").status_code == 400


def test_help_tree_and_pages(paths, tmp_path):
    man = tmp_path / "man"
    (man / "guide").mkdir(parents=True)
    (man / "01-overview.md").write_text("# Overview\n")
    (man / "guide" / "deep.md").write_text("# Deep\n")
    (man / "notes.txt").write_text("ignored")
    app, _ = create_app(replace(paths, man_dir=man), use_webterm=False)
    client = app.test_client()
    tree = client.get("/api/help/tree").get_json()
    assert tree["missing"] is False
    assert [n["name"] for n in tree["tree"]] == ["guide", "01-overview.md"]
    assert client.get("/api/help/page?file=01-overview.md").get_json()["content"] == "# Overview\n"
    assert client.get("/api/help/page?file=guide/deep.md").status_code == 200
    assert client.get("/api/help/page?file=../config.yaml").status_code == 404
    assert client.get("/api/help/page?file=notes.txt").status_code == 404


def test_index_renders_the_workbench(client):
    body = client.get("/").get_data(as_text=True)
    assert 'data-app="paster"' in body and 'id="panel-entries"' in body
    assert "webterm-root" not in body       # webterm off in tests
