"""The keys of ``config.yaml`` as the form sees them (plan §5).

Validation here mirrors ``bin/lib-config.sh`` for pre-flight feedback;
the bash dump (bash_bridge.dump_config) stays the truth and
tests/test_config_schema.py keeps the two in step. ``hotkey`` is the one
key lib-config.sh passes through untouched — its shape is the installer's
``check_key`` rule, so the form can warn before ``install.sh`` refuses it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

DEFAULT_TERMINAL_CLASSES = (
    "alacritty|kitty|urxvt|rxvt|xterm|st|st-256color|gnome-terminal|gnome-terminal-server|"
    "xfce4-terminal|konsole|terminator|tilix|termite|guake|lxterminal|sakura|qterminal|eterm|"
    "wezterm|org.wezfurlong.wezterm")

INT_RE = re.compile(r"^[0-9]+$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
KEYSTROKE_RE = re.compile(r"^[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*$")
CLASSES_RE = re.compile(r"^[A-Za-z0-9_.-]+(\|[A-Za-z0-9_.-]+)*$")
HOTKEY_RE = re.compile(r"^[A-Za-z0-9_+\$]+$")          # install.sh check_key
TRUE_WORDS, FALSE_WORDS = {"true", "yes", "on", "1"}, {"false", "no", "off", "0"}


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    desc: str


@dataclass(frozen=True)
class Field:
    key: str
    section: str
    type: str           # text | int | color | bool | keystroke | classes | hotkey
    default: str
    label: str
    desc: str
    applies: str        # next toggle | next Enter | install.sh
    min: int | None = None
    max: int | None = None


@dataclass(frozen=True)
class Validation:
    ok: bool
    effective: str
    message: str | None = None


SECTIONS = (
    Section("hotkey", "Hotkey", "The key that opens the popup. It lives in the i3 config, so a change "
            "needs ./install.sh — the Doctor's Apply button runs it."),
    Section("size", "Size", "Popup geometry, in % of the screen you are working on. Applies on the next toggle."),
    Section("look", "Look", "Colours, transparency, font and border. Applies on the next toggle."),
    Section("paste", "Paste behavior", "What Enter does after the line is on the clipboard. Applies on the next Enter."),
)

FIELDS = (
    Field("hotkey", "hotkey", "hotkey", "", "Hotkey",
          "Anything i3 bindsym accepts (Mod4+p, Ctrl+space, $mod+p). Empty = $mod+p on Regolith, Mod1+p on plain i3.",
          "install.sh"),
    Field("width_pct", "size", "int", "100", "Width %", "Popup width; below 100 it is centered.", "next toggle", 20, 100),
    Field("height_pct", "size", "int", "40", "Height %", "Popup height, measured from the top of the screen.", "next toggle", 10, 100),
    Field("opacity_pct", "look", "int", "85", "Opacity %", "100 = solid; lower is more transparent (real alpha needs a compositor).", "next toggle", 10, 100),
    Field("background", "look", "color", "#10141a", "Background", "Popup background colour.", "next toggle"),
    Field("foreground", "look", "color", "#d8dee9", "Foreground", "Popup text colour.", "next toggle"),
    Field("font_size", "look", "int", "12", "Font size", "Popup font size (monospace).", "next toggle", 6, 72),
    Field("border_px", "look", "int", "1", "Border px", "Border around the popup, drawn by rofi.", "next toggle", 0, 20),
    Field("auto_paste", "paste", "bool", "true", "Auto paste",
          "Send the paste keystroke after refocusing; off = clipboard + refocus only.", "next Enter"),
    Field("paste_delay_ms", "paste", "int", "150", "Paste delay ms",
          "Wait after the refocus before the keystroke.", "next Enter", 0, 5000),
    Field("paste_key", "paste", "keystroke", "ctrl+v", "Paste key", "Keystroke for ordinary windows (xdotool key syntax).", "next Enter"),
    Field("terminal_paste_key", "paste", "keystroke", "ctrl+shift+v", "Terminal paste key",
          "Keystroke for windows whose WM_CLASS is in the terminal list.", "next Enter"),
    Field("terminal_classes", "paste", "classes", DEFAULT_TERMINAL_CLASSES, "Terminal classes",
          "WM_CLASS names (case-insensitive) that get the terminal keystroke. Empty = the default list.", "next Enter"),
    Field("press_enter", "paste", "bool", "false", "Press Enter",
          "Also send Return after the paste — submits in chat UIs, RUNS the line in a terminal.", "next Enter"),
)
FIELD_BY_KEY = {f.key: f for f in FIELDS}
KEYS = tuple(f.key for f in FIELDS)


def parse_flat(text: str) -> dict:
    """{key: raw value} for every schema key present, read the way
    ``paster_cfg`` reads it: first matching line, quotes optional, a
    trailing ``# comment`` dropped."""
    found: dict = {}
    for line in text.splitlines():
        for key in KEYS:
            if key in found or not line.startswith(f"{key}:"):
                continue
            found[key] = split_line(line)[1]
    return found


def split_line(line: str) -> tuple[str, str, str]:
    """``key: value  # comment`` → (``key: ``, value-as-bash-reads-it, rest).

    ``rest`` is everything after the value (the comment with its leading
    spaces, or the closing quote and what follows) so a rewrite can keep it.
    """
    key, _, raw = line.partition(":")
    body = raw.lstrip(" \t")
    prefix = f"{key}:{raw[:len(raw) - len(body)]}"
    if body[:1] in ('"', "'"):
        quote = body[0]
        end = body.find(quote, 1)
        if end != -1:
            return prefix, body[1:end], body[end + 1:]
    m = re.search(r"[ \t]#", body)
    value = body[:m.start()] if m else body
    stripped = value.rstrip()
    return prefix, stripped, body[len(stripped):]


def validate(field: Field, raw: str) -> Validation:
    """What lib-config.sh would make of ``raw`` for this key."""
    value = (raw or "")
    if value == "":
        return Validation(True, field.default)
    if field.type == "int":
        if INT_RE.match(value) and field.min <= int(value) <= field.max:
            return Validation(True, value)
        return Validation(False, field.default, f"want an integer {field.min}-{field.max}")
    if field.type == "color":
        return Validation(True, value) if COLOR_RE.match(value) else Validation(False, field.default, 'want "#rrggbb"')
    if field.type == "bool":
        low = value.lower()
        if low in TRUE_WORDS:
            return Validation(True, "true")
        if low in FALSE_WORDS:
            return Validation(True, "false")
        return Validation(False, field.default, "want true/false")
    if field.type == "keystroke":
        return (Validation(True, value) if KEYSTROKE_RE.match(value)
                else Validation(False, field.default, "want xdotool key syntax, e.g. ctrl+shift+v"))
    if field.type == "classes":
        return (Validation(True, value) if CLASSES_RE.match(value)
                else Validation(False, field.default, 'want WM_CLASS names separated by "|"'))
    if field.type == "hotkey":
        return (Validation(True, value) if HOTKEY_RE.match(value)
                else Validation(False, value, "install.sh will refuse it: use letters, digits, + and $ only"))
    return Validation(True, value)


def to_file_value(field: Field, value: object) -> str:
    """How the form's value is spelled on its config.yaml line."""
    if field.type == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value).strip().lower()
    if field.type == "int":
        return str(value).strip()
    text = str(value).strip()
    return f'"{text}"'


def schema_json() -> dict:
    return {"sections": [asdict(s) for s in SECTIONS], "fields": [asdict(f) for f in FIELDS]}
