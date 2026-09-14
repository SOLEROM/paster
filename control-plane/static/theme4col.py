"""4ColThems — the server side of the four-theme kit.

A zero-dependency, standard-library-only module. Copy it into your app the
way you copy the CSS and JS (``./install.sh --py <modules-dir>``); import it
and you have the theme ids, their metadata, and the terminal palettes:

    from theme4col import THEMES, normalize, terminal_themes

    theme = normalize(request.cookies.get("theme"))   # never raises
    config.themes = terminal_themes()                 # webterm / ttyd palettes

Why a Python half at all — the browser owns the switching. Three jobs need
the ids on the backend:

1. **Validating a stored preference.** Anything that arrives from a client is
   user data; ``normalize`` turns an unknown value into the default instead of
   a 500 or an unstyled page.
2. **Themed terminals.** CSS custom properties cannot reach inside an xterm.js
   canvas, so ttyd and webterm are handed a palette object *at session
   creation*. Every app in the family had hand-rolled the same loader for
   that; this is it, once.
3. **Server-rendered chrome.** A ``<meta name="theme-color">`` or an inline
   fallback needs the same colour the CSS uses.

The theme identity below mirrors ``themes.json``. It is inlined rather than
read from the JSON so the module keeps working when it is the only file
copied into an app — ``tests/test_python_api.py`` fails the moment the two
drift apart.

Not this module's job: deciding *which* theme a user gets. That is the
browser's (localStorage + the pre-paint guard). Reading a theme out of a
request here and echoing it back is fine; storing it server-side is a policy
choice your app owns.
"""

import json
import logging
import os
from types import MappingProxyType

log = logging.getLogger(__name__)

__all__ = [
    "THEMES", "DEFAULT_THEME", "STORAGE_KEY_DEFAULT", "TERMINAL_THEMES_FILENAME",
    "LABELS", "CODICONS", "GLYPHS", "REMDEV_SLUGS", "META_COLORS", "COLOR_SCHEMES",
    "ACCENTS", "is_valid", "normalize", "label", "remdev_slug", "meta_color",
    "color_scheme", "accent", "theme_meta", "storage_key", "terminal_themes",
    "terminal_theme",
]

# Cycle order — the toggle button walks this list, wrapping at the end.
THEMES = ("dark", "light", "hc", "green")

# The first theme doubles as the fallback everywhere: it is what the bare
# `:root` block in themes.css defines, so an unset/unknown attribute still
# renders correctly.
DEFAULT_THEME = THEMES[0]

# The localStorage key the kit ships with. Apps override it per app on
# `<html data-theme-key="…">` — see storage_key().
STORAGE_KEY_DEFAULT = "app-theme"

# The palette file that ships beside this module.
TERMINAL_THEMES_FILENAME = "terminal-themes.json"

# Read-only on purpose: two apps in one process (or a test suite) must not be
# able to re-skin each other by poking at a shared dict.
LABELS = MappingProxyType({
    "dark": "Dark Modern",
    "light": "Light Modern",
    "hc": "Dark High Contrast",
    "green": "Garage Green",
})

# VS Code codicon glyph per theme — for apps that load the codicon font and
# set `<html data-theme-icons="codicon">`.
CODICONS = MappingProxyType({
    "dark": "circle-filled",
    "light": "circle-outline",
    "hc": "color-mode",
    "green": "terminal",
})

# Single-character glyph per theme, for apps whose chrome is drawn with text
# glyphs (`<html data-theme-icons="glyph">`).
GLYPHS = MappingProxyType({
    "dark": "\u263e",
    "light": "\u2600",
    "hc": "\u25d0",
    "green": "\u276f",
})

# remdev theme slug per theme, for the cldBar status-bar embed
# (solBench/cldBar): `/statusbar?theme=<slug>`.
REMDEV_SLUGS = MappingProxyType({
    "dark": "vscode-dark",
    "light": "vscode-light",
    "hc": "vscode-hc",
    "green": "vscode-green",
})

# `<meta name="theme-color">` per theme == that theme's --bg-base.
META_COLORS = MappingProxyType({
    "dark": "#1f1f1f",
    "light": "#ffffff",
    "hc": "#000000",
    "green": "#0c120e",
})

# CSS `color-scheme` per theme. Also what an embedding iframe must be set to:
# when the host's and the embedded page's schemes disagree the browser drops
# transparency and paints an opaque canvas (see cldBar's readme).
COLOR_SCHEMES = MappingProxyType({
    "dark": "dark",
    "light": "light",
    "hc": "dark",
    "green": "dark",
})

ACCENTS = MappingProxyType({
    "dark": "#0078d4",
    "light": "#005fb8",
    "hc": "#f38518",
    "green": "#36c97a",
})


def is_valid(name):
    """True if ``name`` is one of the four theme ids, exactly as written."""
    return isinstance(name, str) and name in THEMES


def normalize(name, default=DEFAULT_THEME):
    """``name`` if the kit ships it, else ``default``.

    Use this on anything that came from outside the process — a cookie, a
    query string, a config file, a database column.
    """
    return name if is_valid(name) else default


def label(name):
    """Human name for the theme ("Dark High Contrast")."""
    return LABELS[normalize(name)]


def remdev_slug(name):
    """cldBar/remdev slug for the theme ("vscode-hc").

    An unknown id falls back to the dark slug — the same fallback the browser
    glue uses, so a missing mapping looks the same on both sides.
    """
    return REMDEV_SLUGS[normalize(name)]


def meta_color(name):
    """`<meta name="theme-color">` value — the theme's canvas colour."""
    return META_COLORS[normalize(name)]


def color_scheme(name):
    """CSS ``color-scheme`` for the theme: "dark" or "light"."""
    return COLOR_SCHEMES[normalize(name)]


def accent(name):
    """The theme's accent colour."""
    return ACCENTS[normalize(name)]


def theme_meta(name):
    """Everything the kit knows about one theme, as a plain dict.

    Handy as template context::

        return render_template("index.html", theme=theme_meta(theme))
    """
    theme = normalize(name)
    return {
        "theme": theme,
        "label": LABELS[theme],
        "codicon": CODICONS[theme],
        "glyph": GLYPHS[theme],
        "remdev_slug": REMDEV_SLUGS[theme],
        "meta_color": META_COLORS[theme],
        "color_scheme": COLOR_SCHEMES[theme],
        "accent": ACCENTS[theme],
    }


def storage_key(app=""):
    """The localStorage key for ``app`` ("soldo" → "soldo-theme").

    Put the result on ``<html data-theme-key="…">``; both browser files read
    it from there. Distinct keys keep two apps on one origin from overwriting
    each other's choice.
    """
    app = (app or "").strip()
    return f"{app}-theme" if app else STORAGE_KEY_DEFAULT


def _themes_path(path=None):
    if path is not None:
        return os.fspath(path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        TERMINAL_THEMES_FILENAME)


def terminal_themes(path=None):
    """``{theme id: xterm ITheme dict}`` from ``terminal-themes.json``.

    Shaped for ``webterm.TerminalConfig.themes`` and for ttyd's
    ``--client-option theme=<json>``. Doc keys (``_comment``) are stripped.

    A missing or malformed file is logged and degrades to ``{}`` — terminals
    then fall back to the library's own palette, which is ugly but running.
    That is deliberate: a broken palette file must never take the app's
    terminals down with it.

    Each call returns a fresh, mutable structure; webterm takes ownership of
    what it is handed.
    """
    resolved = _themes_path(path)
    try:
        with open(resolved, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        log.warning("4ColThems: %s unusable (%s) — terminal palettes fall "
                    "back to library defaults", resolved, exc)
        return {}
    return {name: dict(palette) for name, palette in raw.items()
            if isinstance(palette, dict) and not name.startswith("_")}


def terminal_theme(name, path=None):
    """One xterm palette, for a single session spawn.

    Returns ``{}`` if the palettes are unavailable — pass it straight through
    to the terminal, which then keeps its own colours.
    """
    return terminal_themes(path).get(normalize(name), {})
