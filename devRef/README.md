# devRef — development-stage reference versions

The paster design evolved through three earlier working versions before
settling on the rofi-based **v3** that now lives at the repository root.
This folder keeps those versions and the planning documents for reference.
They are complete and installable, but superseded — install the root
version unless you specifically need one of these.

## Versions

| Folder | What it is |
|--------|------------|
| [`../` (root)](../README.md) | **v3, the final version** — v1's tabbed feature set rebuilt on rofi (i3/X11). No scratchpad, no terminal window, no persistent process; look/size changes apply without reinstall. |
| [`v2/`](v2/README.md) | Desktop-agnostic fzf variant. WM backends (i3 scratchpad / generic X11 EWMH / XWayland), per-desktop hotkey wiring in the installer (i3 config, gsettings, dconf, xfconf, sxhkd fallback), `--dry-run`/`--uninstall`. Install with `./v2/install.sh`. |
| [`v1_i3tabs/`](v1_i3tabs/README.md) | i3/X11 only, fzf + alacritty on i3's scratchpad. Tabbed entries: each folder under `entries/` is a tab, global settings in `config.yaml`. Supersedes a v0i3 install. |
| [`v0i3/`](v0i3/README.md) | First working version — i3/X11, a single flat `entries.txt` list. |

Installing a newer version supersedes the older one on i3 (each installer
replaces earlier paster config blocks — the root v3 installer removes
v1/v0i3 blocks too).

## Planning history

The design evolved through `plan0.md` (raw idea dump) → `plan1.md` →
`plan2.md` (decisions locked, i3 implementation) → `plan3.md`
(generalizing v2 beyond i3 to any Ubuntu desktop) → `plan4.md`
(v3: replacing the fzf/alacritty/scratchpad stack with rofi).
