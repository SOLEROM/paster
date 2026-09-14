"""webterm's one host requirement: the viewport must shrink for the soft
keyboard, or fullscreen hides the last terminal rows on a phone."""
import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "control-plane" / "templates" / "index.html"


def test_the_viewport_shrinks_for_the_soft_keyboard():
    html = TEMPLATE.read_text(encoding="utf-8")
    meta = re.search(r"<meta[^>]*name=[\"']viewport[\"'][^>]*>", html, re.S)
    assert meta, "no viewport meta tag"
    assert "interactive-widget=resizes-content" in meta.group(0)
    assert "viewport-fit=cover" in meta.group(0)


def test_the_terminal_mount_has_no_inline_style():
    html = TEMPLATE.read_text(encoding="utf-8")
    mount = re.search(r"<div id=\"webterm-root\"[^>]*>", html)
    assert mount and "style=" not in mount.group(0)
