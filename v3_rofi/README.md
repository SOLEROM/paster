# paster v3 — rofi-backed tabbed prompt paster for i3/X11

A drop-down, semi-transparent, fuzzy-searchable menu of reusable prompt
lines, organized in **tabs** — same feature set as v1_i3tabs, rebuilt on
**rofi**. Press the hotkey anywhere, pick a tab (or search across all of
them), type a few characters, hit Enter — the popup closes, focus returns
to the window you came from, and the chosen line is pasted there.

Where v1 needed five cooperating pieces (alacritty host window, fzf, the
i3 scratchpad, a geometry-retry dance, picom for opacity), rofi draws,
places, and styles its own popup: v3 is one rofi launch plus three short
scripts. No persistent process between toggles, no `for_window` rule, and
transparency degrades gracefully without a compositor (rofi falls back to
pseudo-transparency instead of going solid).

## Entries = folders (unchanged from v1)

**Each subfolder of `entries/` is a tab** (its name is the tab title), and
the `content.md` inside it holds the lines shown for that tab — one entry
per non-empty line:

```
entries/
├── 10_Coding/content.md     # tab "Coding"
├── 20_Writing/content.md    # tab "Writing"
└── 30_General/content.md    # tab "General"
```

- Tabs are ordered by folder name; a leading `NN_` number prefix is used
  only for ordering and is stripped from the displayed title.
- Folders without a `content.md` are ignored.
- Everything is rescanned on every toggle — add a folder or edit a
  `content.md` and it shows up on the next popup, no reload needed.
- An extra **ALL** tab (always first) searches every tab at once; entries
  there are shown as `[Tab]  line`.

## Requirements

- X11 session with **i3** (Wayland is not supported)
- `rofi` (≥ 1.6; Ubuntu 24.04 ships 1.7.5), `xdotool`, `xclip`, `xprop` —
  **the installer apt-installs whatever is missing**
- A compositor (picom) for true transparency; without one rofi uses
  pseudo-transparency

## Install

```sh
./install.sh              # hotkey from config.yaml, else $mod+p (Regolith) / Mod1+p (plain i3)
./install.sh 'Mod4+p'     # or pass any key bindsym accepts to pick your own
```

The installer:

1. Verifies X11/i3, checks the dependencies, and apt-installs missing ones.
2. Reads `config.yaml` (hotkey).
3. Wires the snippet into whichever config your session actually uses:
   - **Regolith i3** (detected via `~/.config/regolith3/i3/config.d/`) —
     writes a drop-in file `config.d/90_paster`.
   - **Plain i3** — seeds `~/.config/i3/config` from `/etc/i3/config` if
     missing, backs it up to `config.paster-backup`, and appends the block.
4. Removes previous paster blocks — **including v1/v0i3 blocks** — and
   closes their leftover popup window, so installing v3 cleanly supersedes
   older versions. Re-running is idempotent.

## Usage

- **Hotkey** — open the popup on the screen you're working on; press it
  again (or **Esc**) to close without pasting.
- **← / →** (or **Ctrl-h / Ctrl-l**, **Shift+←/→**, **Ctrl+Tab**) —
  previous / next tab. The text you typed is kept when switching tabs.
- **ALL** — the first tab searches every tab at once (`[Tab]  line`).
- Type to fuzzy-filter (fzf-style ranking), **Enter** — copy the line to
  the clipboard, close, refocus your previous window, and auto-paste there
  (`Ctrl+Shift+V` if that window is a known terminal, `Ctrl+V` otherwise).

The popup reopens on the tab you last picked from.

### Differences from v1 worth knowing

- Because plain **←/→ switch tabs**, the cursor inside the filter text
  moves with **Ctrl-b / Ctrl-f** (emacs-style) instead of the arrows.
- ALL mode is a regular tab (always leftmost) instead of a Ctrl-a toggle.
- "Remembers the tab" means the tab of your **last pick** — closing with
  Esc keeps the previous memory (v1 remembered the tab you were looking at).
- rofi holds a keyboard grab while open, so the close-on-hotkey behavior is
  implemented *inside* rofi (the hotkey is added to its cancel keys, and
  automatically freed from any rofi default that used the same combo —
  e.g. `Ctrl+space` is rofi's row-select by default). If you set an exotic
  `hotkey` the translation may skip it — Esc always works.

## config.yaml — global settings

| key          | default   | meaning                                              |
|--------------|-----------|------------------------------------------------------|
| `hotkey`     | *(auto)*  | toggle key; empty = `$mod+p` Regolith / `Mod1+p` i3  |
| `width_pct`  | `100`     | popup width in % of the screen; `<100` is centered   |
| `height_pct` | `40`      | popup height in % of the screen, from the top        |
| `opacity_pct`| `85`      | `100` = solid, lower = more transparent              |
| `background` | `#10141a` | popup background color (`"#rrggbb"`)                 |
| `foreground` | `#d8dee9` | popup text color                                     |
| `font_size`  | `12`      | popup font size                                      |
| `border_px`  | `1`       | border around the popup (drawn by rofi), in pixels   |

**Look and size keys apply on the next toggle** — the theme is re-rendered
from `config.yaml` at every launch, no reinstall needed (an improvement
over v1). Only `hotkey` needs `./install.sh` again, since it lives in the
i3 config.

## Layout

```
v3_rofi/
├── config.yaml                  # global settings (size, colors, hotkey, …)
├── entries/                     # one subfolder per tab
│   └── <NN_TabName>/content.md  #   one entry per line
├── bin/
│   ├── toggle.sh                # hotkey target: focus capture, theme render, rofi launch
│   ├── tab-mode.sh              # rofi script-mode backend (one instance per tab)
│   ├── paste-back.sh            # clipboard + focus-restore + paste keystroke
│   └── lib-config.sh            # config.yaml reader (sourced by toggle.sh)
├── config/
│   ├── i3.conf.snippet          # keybinding (template; no window rule needed)
│   └── paster.rasi.tmpl         # rofi theme template, rendered per toggle
├── install.sh
└── README.md
```

## Customization

- **Tabs / entries** — folders under `entries/`; picked up on the next
  toggle. Tab names should avoid `,` `:` `'` `"` (dropped from the label —
  they clash with rofi's mode syntax).
- **Everything visual** — `config.yaml`; applies on the next toggle.
- **Hotkey** — `config.yaml` + `./install.sh`, or `./install.sh '<key>'`.
- **Terminal detection** — apps that should receive `Ctrl+Shift+V` are
  listed in `TERMINAL_CLASSES` in `bin/paste-back.sh` (matched
  case-insensitively against WM_CLASS; find a window's class with
  `xprop WM_CLASS`).
- **Tab-bar colors / theme details** beyond config.yaml —
  `config/paster.rasi.tmpl`.

## Troubleshooting

- **Paste lands nowhere** — the selection is always on the clipboard, so
  `Ctrl+V` manually; happens if the previous window closed meanwhile.
- **Paste keystroke arrives too early / gets swallowed** — tab-mode.sh
  waits for the rofi process to exit before pasting; if you see this,
  raise the `sleep 0.15` in `bin/paste-back.sh`.
- **Wrong paste keystroke in some app** — add its WM_CLASS to
  `TERMINAL_CLASSES` (or remove it) in `bin/paste-back.sh`.
- **Hotkey does nothing** — check which config your i3 actually loads:
  `pgrep -a i3` shows the `-c <path>` it was started with (Regolith uses
  `/etc/regolith/i3/config` + `config.d` drop-ins, not `~/.config/i3/config`).
  Then confirm the paster block/drop-in is in the matching location and the
  chosen key isn't bound elsewhere.
- **Popup on the wrong monitor** — v3 asks rofi for "the monitor with the
  focused window" (`-monitor -4`); if your setup disagrees, try `-1`
  (focused monitor) or `-5` (monitor with the mouse) in `bin/toggle.sh`.
- **Old v0/v1 menu still opens** — its window survived in the scratchpad;
  re-run `./install.sh` (it closes leftover Paster windows).
- **Stale state** — `$XDG_RUNTIME_DIR/paster-prev-win`, `paster-last-tab`,
  and the rendered `paster.rasi` (fallback `/tmp`); all safe to delete.
