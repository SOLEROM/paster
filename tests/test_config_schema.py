"""The schema mirrors lib-config.sh: bash decides, the schema must agree."""
import re

import pytest

from conftest import REPO_ROOT
from modules import bash_bridge, config_schema as cs

CASES = {
    "width_pct": ["20", "100", "19", "101", "abc", "", "5x"],
    "height_pct": ["10", "100", "5"],
    "opacity_pct": ["10", "100", "0", "85"],
    "font_size": ["6", "72", "99", "12"],
    "border_px": ["0", "20", "21"],
    "background": ["#10141a", "#GGGGGG", "10141a", "#abc", "#ABCDEF"],
    "foreground": ["#ffffff", "red", ""],
    "auto_paste": ["true", "yes", "on", "1", "false", "no", "off", "0", "maybe", "TRUE", "Off"],
    "press_enter": ["Yes", "x", ""],
    "paste_delay_ms": ["0", "5000", "5001", "-1", "150"],
    "paste_key": ["ctrl+v", "ctrl+shift+v", "ctrl v", "+v", "v+", "Return"],
    "terminal_paste_key": ["ctrl+shift+v", "bad key", "ctrl+shift+v+"],
    "terminal_classes": ["alacritty|kitty", "a b", "alacritty|", "org.wezfurlong.wezterm", "x|y|z"],
}


@pytest.mark.parametrize("key,raw", [(k, v) for k, vs in CASES.items() for v in vs])
def test_parity_with_lib_config(paths, key, raw):
    paths.config_file.write_text(f"{key}: {raw}\n")
    dump = bash_bridge.dump_config(paths)
    v = cs.validate(cs.FIELD_BY_KEY[key], raw)
    assert v.effective == dump.values[key], f"{key}={raw!r}: schema {v.effective!r} vs bash {dump.values[key]!r}"
    warned = any(f"config {key}=" in w for w in dump.warnings)
    assert (not v.ok) == warned, f"{key}={raw!r}: schema ok={v.ok} but bash warned={warned}"


def test_every_lib_config_key_is_in_the_schema():
    src = (REPO_ROOT / "bin" / "lib-config.sh").read_text()
    bash_keys = set(re.findall(r'\$\(paster_cfg (\w+) ', src))
    assert bash_keys == set(cs.KEYS)


def test_defaults_match_lib_config_on_an_empty_file(paths):
    paths.config_file.write_text("")
    dump = bash_bridge.dump_config(paths)
    for field in cs.FIELDS:
        assert dump.values[field.key] == field.default, field.key


@pytest.mark.parametrize("hotkey,ok", [("Ctrl+space", True), ("$mod+p", True), ("Mod1+space", True),
                                       ("", True), ("a b", False), ("ctrl;rm", False)])
def test_hotkey_follows_the_installers_rule(hotkey, ok):
    assert cs.validate(cs.FIELD_BY_KEY["hotkey"], hotkey).ok is ok


@pytest.mark.parametrize("line,value,rest", [
    ('hotkey: "Ctrl+space"', "Ctrl+space", ""),
    ("width_pct: 100", "100", ""),
    ("height_pct: 40      # measured from the top", "40", "      # measured from the top"),
    ("background: \"#10141a\"  # colour", "#10141a", "  # colour"),
    ("paste_key: 'ctrl+v'", "ctrl+v", ""),
    ("terminal_classes: \"a|b\"", "a|b", ""),
    ("x:   spaced value   ", "spaced value", "   "),
    ("x: #notacomment", "#notacomment", ""),
])
def test_split_line_reads_like_bash(line, value, rest):
    prefix, got, got_rest = cs.split_line(line)
    assert got == value and got_rest == rest
    assert line == prefix + ('"' + got + '"' if line[len(prefix):].startswith('"') else
                             "'" + got + "'" if line[len(prefix):].startswith("'") else got) + got_rest


def test_parse_flat_takes_the_first_match_only():
    text = "width_pct: 50\nwidth_pct: 60\n# height_pct: 1\nheight_pct: 30\nunknown: 1\n"
    assert cs.parse_flat(text) == {"width_pct": "50", "height_pct": "30"}


def test_to_file_value_spelling():
    f = cs.FIELD_BY_KEY
    assert cs.to_file_value(f["auto_paste"], True) == "true"
    assert cs.to_file_value(f["auto_paste"], "no") == "no"
    assert cs.to_file_value(f["width_pct"], 80) == "80"
    assert cs.to_file_value(f["background"], "#000000") == '"#000000"'
    assert cs.to_file_value(f["hotkey"], "$mod+p") == '"$mod+p"'


def test_schema_json_has_every_field_with_a_section():
    data = cs.schema_json()
    sections = {s["id"] for s in data["sections"]}
    assert all(f["section"] in sections for f in data["fields"])
    assert {f["key"] for f in data["fields"]} == set(cs.KEYS)
