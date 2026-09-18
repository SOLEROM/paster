"""The footer's app-name item asks the mainBench shell for its app bar.

The vsCodeFront kit's `setupShell()` hands `#app-item` to the mainBench embed
kit's `bench-signal.js` (solBench/mainBench/embed — a copy-in, never edited
here). Docked in the shell the item posts the frame signal
(`{bench: 1, type: "toggle-strip"}`); opened on its own there is no shell
to ask, so the markup ships it as a plain label. The sidebar toggle lives
on the title bar's brand, keyboard-reachable now that it is the one toggle.

Source-level contracts; both kits' behavior is tested where they live.
"""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "control-plane/templates/index.html"
KIT_COPY = ROOT / "control-plane/static/js" / "bench-signal.js"
SHELL_JS = ROOT / "control-plane/static" / "js" / "wb-shell.js"


def _html() -> str:
    return re.sub(r"<!--.*?-->", "", TEMPLATE.read_text(encoding="utf-8"), flags=re.S)


def _embed_kit() -> Path:
    """solBench/mainBench/embed: $SOLBENCH_HOME › the sibling ../solBench."""
    env = os.environ.get("SOLBENCH_HOME")
    kit = (Path(env) if env else ROOT.parent / "solBench") / "mainBench" / "embed"
    if not (kit / "bench-signal.js").is_file():
        if env:
            pytest.fail(f"SOLBENCH_HOME={env} has no mainBench/embed kit")
        pytest.skip("solBench checkout not found beside this repo — set SOLBENCH_HOME")
    return kit


def test_kit_copy_is_not_forked():
    assert KIT_COPY.read_bytes() == (_embed_kit() / "bench-signal.js").read_bytes(), \
        "re-run solBench/mainBench/embed/install.sh — never edit the copy"


def test_the_app_name_item_ships_as_a_plain_label():
    tag = re.search(r'<span[^>]*id="app-item"[^>]*>', _html()).group(0)
    assert "statusbar-item remote" in tag, "it keeps today's look"
    for attr in ("role=", "tabindex=", "title="):
        assert attr not in tag, \
            f"{attr} promises an action the standalone app does not have"


def test_the_brand_is_the_keyboard_reachable_sidebar_toggle():
    tag = re.search(r'<span[^>]*class="brand[ "][^>]*>', _html()).group(0)
    assert 'role="button"' in tag and 'tabindex="0"' in tag


def test_the_workbench_kit_hands_the_item_to_the_embed_kit():
    js = SHELL_JS.read_text(encoding="utf-8")
    assert "window.benchSignal.setupItem(" in js, \
        "an older wb-shell.js — re-run solBench/vsCodeFront/install.sh"
    assert 'wireButton($(".statusbar-item.remote")' not in js


def test_the_embed_kit_loads_before_the_boot_script():
    srcs = re.findall(r'<script[^>]*src="([^"?]+)', _html())
    names = [s.rsplit("/", 1)[-1] for s in srcs]
    assert names.count("bench-signal.js") == 1
    assert names.index("bench-signal.js") < names.index("main.js")
