import pytest

from conftest import REPO_ROOT
from modules import config_store as cs
from modules import fileio


def test_read_config_reports_values_effective_and_missing(paths):
    doc = cs.read_config(paths)
    assert doc.values["hotkey"] == "Ctrl+space"
    assert doc.effective["width_pct"] == "100"
    assert doc.warnings == () and doc.missing == ()
    assert doc.rev == fileio.rev_of(paths.config_file.read_bytes())


def test_write_values_keeps_comments_order_and_other_lines(paths):
    before = paths.config_file.read_text().splitlines()
    doc = cs.read_config(paths)
    new = cs.write_values(paths, {"opacity_pct": 70, "background": "#000000", "auto_paste": False}, doc.rev)
    after = paths.config_file.read_text().splitlines()
    assert len(before) == len(after)
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert changed == [
        ("opacity_pct: 85     # 100 = fully solid, lower = more transparent (real alpha with a compositor)",
         "opacity_pct: 70     # 100 = fully solid, lower = more transparent (real alpha with a compositor)"),
        ('background: "#10141a"', 'background: "#000000"'),
        ("auto_paste: true             # false = clipboard + refocus only, paste it yourself (Ctrl+V)",
         "auto_paste: false             # false = clipboard + refocus only, paste it yourself (Ctrl+V)"),
    ]
    assert new.effective["opacity_pct"] == "70" and new.effective["auto_paste"] == "false"
    assert new.warnings == ()


def test_write_values_appends_missing_keys_under_one_marker(paths):
    paths.config_file.write_text("# mine\nwidth_pct: 90\n")
    doc = cs.read_config(paths)
    assert "hotkey" in doc.missing
    new = cs.write_values(paths, {"hotkey": "Mod4+p", "font_size": 14}, doc.rev)
    text = paths.config_file.read_text()
    assert text == '# mine\nwidth_pct: 90\n\n# added by paster front\nhotkey: "Mod4+p"\nfont_size: 14\n'
    again = cs.write_values(paths, {"border_px": 2}, new.rev)
    assert again.raw.count(cs.ADDED_MARKER) == 1 and again.raw.endswith("border_px: 2\n")


def test_an_invalid_value_is_written_but_reported(paths):
    doc = cs.read_config(paths)
    new = cs.write_values(paths, {"width_pct": 999}, doc.rev)
    assert new.values["width_pct"] == "999"
    assert new.effective["width_pct"] == "100"
    assert any("width_pct" in w for w in new.warnings)


def test_write_values_refuses_unknown_keys_and_bad_shapes(paths):
    doc = cs.read_config(paths)
    for bad in [{"nope": 1}, {"hotkey": ["a"]}, {"hotkey": None}, {"paste_key": 'a"b'}, {"hotkey": "a\nb"}, "text"]:
        with pytest.raises(cs.Invalid):
            cs.write_values(paths, bad, doc.rev)
    assert paths.config_file.read_text() == (REPO_ROOT / "config.yaml").read_text()


def test_write_values_refuses_a_stale_rev(paths):
    doc = cs.read_config(paths)
    cs.write_values(paths, {"font_size": 13}, doc.rev)
    with pytest.raises(fileio.StaleRevision):
        cs.write_values(paths, {"font_size": 15}, doc.rev)
    assert cs.read_config(paths).values["font_size"] == "13"


def test_write_raw_round_trips_and_snapshots(paths):
    from modules import history
    doc = cs.read_config(paths)
    text = "# all mine\nhotkey: \"Mod4+p\"\n"
    new = cs.write_raw(paths, text, doc.rev)
    assert new.raw == text and paths.config_file.read_text() == text
    assert len(history.list_snapshots(paths, "config.yaml")) == 1
    with pytest.raises(cs.Invalid):
        cs.write_raw(paths, "bad\0bytes", new.rev)
    with pytest.raises(cs.Invalid):
        cs.write_raw(paths, 42, new.rev)


def test_preflight_mirrors_the_schema():
    out = cs.preflight({"width_pct": "5", "background": "#123456", "auto_paste": True, "unknown": 1})
    assert out["width_pct"]["ok"] is False and out["width_pct"]["effective"] == "100"
    assert out["background"]["ok"] is True
    assert out["auto_paste"] == {"ok": True, "effective": "true", "message": None}
    assert "unknown" not in out


def test_replace_value_handles_unquoted_and_absent(paths):
    assert cs.replace_value("a: 1\nwidth_pct: 5\n", "width_pct", "9") == "a: 1\nwidth_pct: 9\n"
    assert cs.replace_value("width_pct:\n", "width_pct", "9") == "width_pct: 9\n"
    assert cs.replace_value("a: 1\n", "width_pct", "9") is None
