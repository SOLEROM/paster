"""cldBar embed — remdev's Claude status bar in the footer (kit contract).

The mechanism belongs to the kit (solBench/cldBar): ``cldbar.js`` is a
copy-in that owns the iframe. This app owns policy: the mount slot, the
optional ``PASTER_REMDEV_URL`` pin, and the theme map. The pitfalls pinned
here are the kit readme's: no server-rendered 127.0.0.1 ever reaches the
page, every theme maps to a slug, the copy is not a fork.
"""
import json
import re

import pytest

from conftest import REPO_ROOT, solbench_home
from server import create_app

STATIC = REPO_ROOT / "control-plane" / "static"


def page(client):
    return client.get("/").get_data(as_text=True)


def test_the_footer_carries_the_slot(client):
    body = page(client)
    footer = body.split('<footer class="statusbar"', 1)[1].split("</footer>", 1)[0]
    assert 'id="cldbar-slot"' in footer


def test_kit_then_glue(client):
    body = page(client)
    assert body.index("/static/js/cldbar.js") < body.index("/static/js/cldbar-glue.js")


def test_the_page_never_hardcodes_the_station_address(client):
    body = re.sub(r"<!--.*?-->", "", page(client), flags=re.S)
    assert "127.0.0.1" not in body and "6005" not in body
    assert 'data-remdev-url=""' in body


def test_the_glue_derives_the_origin_from_the_viewer_address():
    src = re.sub(r"//.*", "", (STATIC / "js" / "cldbar-glue.js").read_text())
    assert "127.0.0.1" not in src and "6005" not in src and "remdevUrl" in src


def test_a_pinned_remdev_url_reaches_the_slot_and_the_csp(paths):
    app, _ = create_app(paths, use_webterm=False, remdev_url="https://station.ts.net/")
    resp = app.test_client().get("/")
    assert 'data-remdev-url="https://station.ts.net"' in resp.get_data(as_text=True)
    frame_src = [d for d in resp.headers["Content-Security-Policy"].split(";") if d.strip().startswith("frame-src")][0]
    assert "https://station.ts.net" in frame_src and "http://localhost:*" in frame_src


@pytest.mark.parametrize("bad", ["station:6005", "//station:6005", "javascript:alert(1)", "http://a/b"])
def test_a_bad_pin_refuses_to_start(paths, bad):
    with pytest.raises(ValueError):
        create_app(paths, use_webterm=False, remdev_url=bad)


def test_the_glue_maps_every_theme_onto_a_remdev_slug():
    manifest = json.loads((STATIC / "themes.json").read_text())["themes"]
    ids = set(manifest) if isinstance(manifest, dict) else {t["id"] for t in manifest}
    glue = (STATIC / "js" / "cldbar-glue.js").read_text()
    block = re.search(r"CLDBAR_THEME = \{(.*?)\}", glue, re.S).group(1)
    mapped = dict(re.findall(r'(\w+):\s*"([a-z0-9-]+)"', block))
    assert set(mapped) == ids and mapped["light"].endswith("light")


def test_the_glue_re_points_the_embed_on_themechange():
    glue = (STATIC / "js" / "cldbar-glue.js").read_text()
    assert "themechange" in glue and "syncCldBar" in glue


def test_the_kit_copy_is_not_a_local_fork():
    kit = solbench_home() / "cldBar"
    assert (STATIC / "js" / "cldbar.js").read_bytes() == (kit / "cldbar.js").read_bytes()
