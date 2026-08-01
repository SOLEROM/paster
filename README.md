# paster

A Guake-style drop-down **prompt paster**. Press a hotkey anywhere and a
semi-transparent panel drops over the top of the screen with a
fuzzy-searchable menu of your reusable text lines (prompts, commands,
boilerplate). Pick one with a few keystrokes and Enter — the popup hides,
focus returns to the window you came from, and the line is pasted right
there.

No custom GUI app and no daemon: a thin shell layer over standard tools.
v0/v1 compose `fzf` + `alacritty` on i3's native scratchpad; v2 puts a
small window-manager backend underneath so the same scripts run on **any
Ubuntu desktop** — i3/Regolith, GNOME, XFCE, KDE, MATE, Cinnamon on X11,
plus a degraded no-auto-paste mode on GNOME Wayland (the stock Ubuntu
login); v3 swaps the whole popup/menu layer for **rofi**, collapsing the
window machinery into a single launcher call.

## Versions

| Folder | What it is |
|--------|------------|
| [`v3_rofi/`](v3_rofi/README.md) | **Newest** — v1's tabbed feature set rebuilt on rofi (i3/X11). No scratchpad, no terminal window, no persistent process; look/size changes apply without reinstall. Install with `./v3_rofi/install.sh` (apt-installs missing deps). |
| [`v2/`](v2/README.md) | Desktop-agnostic fzf variant. WM backends (i3 scratchpad / generic X11 EWMH / XWayland), per-desktop hotkey wiring in the installer (i3 config, gsettings, dconf, xfconf, sxhkd fallback), `--dry-run`/`--uninstall`. Install with `./v2/install.sh`. |
| [`v1_i3tabs/`](v1_i3tabs/README.md) | i3/X11 only. Tabbed entries: each folder under `entries/` is a tab, global settings in `config.yaml`. Supersedes a v0i3 install. |
| [`v0i3/`](v0i3/README.md) | First working version — i3/X11, a single flat `entries.txt` list. |

Installing a newer version supersedes the older one on i3 (the installer
replaces earlier paster config blocks).

## Planning history

The design evolved through `plan0.md` (raw idea dump) → `plan1.md` →
`plan2.md` (decisions locked, i3 implementation) → `plan3.md`
(generalizing v2 beyond i3 to any Ubuntu desktop) → `plan4.md`
(v3: replacing the fzf/alacritty/scratchpad stack with rofi).
