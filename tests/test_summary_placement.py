"""The status bar row stays free of anything that grows with app state —
a long count once covered the Claude meters. Counts go on #summary-strip."""
import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "control-plane" / "templates" / "index.html"
JS = Path(__file__).resolve().parents[1] / "control-plane" / "static" / "js"


def test_the_footer_carries_no_count_and_the_titlebar_has_the_strip():
    html = TEMPLATE.read_text(encoding="utf-8")
    footer = html.split('<footer class="statusbar"', 1)[1].split("</footer>", 1)[0]
    assert "count" not in footer and "summary" not in footer
    header = html.split("<header", 1)[1].split("</header>", 1)[0]
    assert 'id="summary-strip"' in header


def test_the_js_never_writes_counts_into_the_footer():
    for path in JS.glob("*.js"):
        if path.name.startswith(("wb-", "theme-", "cldbar.")):
            continue
        src = path.read_text()
        assert not re.search(r'\$\("#status-(left|right|bar)"\)\.(innerHTML|textContent)', src), path.name
