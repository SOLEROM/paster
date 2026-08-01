# paster v1 — tabbed Guake-style prompt paster for i3/X11

A drop-down, semi-transparent, fuzzy-searchable menu of reusable prompt
lines, now organized in **tabs**. Press the hotkey anywhere, pick a tab (or
search across all of them), type a few characters, hit Enter — the popup
hides, focus returns to the window you came from, and the chosen line is
pasted there.

The tab bar follows the `taskStack/demo1.sh` navigator pattern: a top line
listing every tab with the current one highlighted, arrow keys to move
between them, and a one-key toggle to search everything at once.

No custom GUI app, no daemon: a thin shell layer over `fzf`, `xdotool`,
`xclip`, `alacritty`, and i3's native **scratchpad**. Transparency comes
from the running compositor (picom).

## Entries = folders

`entries.txt` from v0 is now an `entries/` directory. **Each subfolder is a
tab** (its name is the tab title), and the `content.md` inside it holds the
lines shown for that tab — one entry per non-empty line:

```
entries/
├── 10_Coding/content.md     # tab "Coding"
├── 20_Writing/content.md    # tab "Writing"
└── 30_General/content.md    # tab "General"
```

- Tabs are ordered by folder name; a leading `NN_` number prefix is used
  only for ordering and is stripped from the displayed title.
- Folders without a `content.md` are ignored.
- Everything is rescanned on every menu cycle — add a folder or edit a
  `content.md` and it shows up on the next popup, no reload needed.

## Requirements

- X11 session with **i3** (Wayland is not supported)
- A compositor for transparency (picom, or opacity is simply ignored)
- `fzf`, `xdotool`, `xclip`, `xprop`, `jq` (checked by the installer)
- `alacritty` (installed by the installer via apt if missing)

## Install

```sh
./install.sh              # hotkey from config.yaml, else $mod+p (Regolith) / Mod1+p (plain i3)
./install.sh 'Mod4+p'     # or pass any key bindsym accepts to pick your own
```

The installer:

1. Verifies X11/i3 and the dependencies; apt-installs `alacritty` if missing.
2. Reads `config.yaml` (hotkey, border width).
3. Wires the snippet into whichever config your session actually uses:
   - **Regolith i3** (detected via `~/.config/regolith3/i3/config.d/`) —
     writes a drop-in file `config.d/90_paster`.
   - **Plain i3** — seeds `~/.config/i3/config` from `/etc/i3/config` if
     missing, backs it up to `config.paster-backup`, and appends the block.
4. Closes any Paster window left over from a previous install and reloads
   i3. Re-running is idempotent — it replaces the previous block, **including
   a v0i3 block**, so installing v1 cleanly supersedes v0.

## Usage

- **Hotkey** — toggle the popup on the screen you're currently working on.
- **← / →** (or **Ctrl-h / Ctrl-l**) — previous / next tab.
- **Ctrl-a** — toggle **ALL mode**: every line from every tab in one list
  (prefixed `[Tab]`), so typing filters across all tabs at once. The text
  you already typed is kept when switching tabs or modes.
- Type to fuzzy-filter, **Enter** — copy the line to the clipboard, hide,
  refocus your previous window, and auto-paste there (`Ctrl+Shift+V` if
  that window is a known terminal, `Ctrl+V` otherwise).
- **Esc** (or the hotkey again) — hide without pasting.

The first hotkey press spawns the window; after that it lives hidden in the
i3 scratchpad and pops instantly — and remembers which tab you were on.

## config.yaml — global settings

All knobs live in `config.yaml` at the root of this folder. Apply changes
by re-running `./install.sh` (it re-wires i3 and restarts the popup window):

| key          | default   | meaning                                              |
|--------------|-----------|------------------------------------------------------|
| `hotkey`     | *(auto)*  | toggle key; empty = `$mod+p` Regolith / `Mod1+p` i3  |
| `width_pct`  | `100`     | popup width in % of the screen; `<100` is centered, shrunk equally from both sides |
| `height_pct` | `40`      | popup height in % of the screen, from the top        |
| `opacity_pct`| `85`      | `100` = solid, lower = more transparent              |
| `background` | `#10141a` | popup background color (`"#rrggbb"`)                 |
| `foreground` | `#d8dee9` | popup text color                                     |
| `font_size`  | `12`      | popup font size                                      |
| `border_px`  | `1`       | i3 border around the popup, in pixels                |

Size keys (`width_pct`, `height_pct`) are read live on every toggle; look
keys are applied when the popup window spawns and the hotkey/border when i3
reloads — re-running `./install.sh` covers all cases in one step. Invalid
values fall back to the defaults with a warning.

## Layout

```
v1/
├── config.yaml                  # global settings (size, colors, hotkey, …)
├── entries/                     # one subfolder per tab
│   └── <NN_TabName>/content.md  #   one entry per line
├── bin/
│   ├── toggle.sh                # hotkey target: capture focus, show/hide/spawn
│   ├── menu-loop.sh             # inside the window: tabbed fzf loop (demo1-style)
│   ├── paste-back.sh            # clipboard + hide + focus-restore + paste keystroke
│   └── lib-config.sh            # config.yaml reader (sourced by the two above)
├── config/
│   ├── i3.conf.snippet          # window rule + keybinding (template)
│   └── alacritty-paster.toml    # base profile; config.yaml overrides at spawn
├── install.sh
└── README.md
```

## Customization

- **Tabs / entries** — folders under `entries/`; picked up on the next
  popup cycle, no reload needed.
- **Everything visual + hotkey** — `config.yaml`, then `./install.sh`.
- **Terminal detection** — apps that should receive `Ctrl+Shift+V` are
  listed in `TERMINAL_CLASSES` in `bin/paste-back.sh` (matched
  case-insensitively against WM_CLASS; find a window's class with
  `xprop WM_CLASS`).

## Troubleshooting

- **No transparency** — no compositor running; start picom.
- **Paste lands nowhere** — the selection is always on the clipboard, so
  `Ctrl+V` manually; happens if the previous window closed meanwhile.
- **Wrong paste keystroke in some app** — add its WM_CLASS to
  `TERMINAL_CLASSES` (or remove it) in `bin/paste-back.sh`.
- **Hotkey does nothing** — check which config your i3 actually loads:
  `pgrep -a i3` shows the `-c <path>` it was started with (Regolith uses
  `/etc/regolith/i3/config` + `config.d` drop-ins, not `~/.config/i3/config`).
  Then confirm the paster block/drop-in is in the matching location and the
  chosen key isn't bound elsewhere.
- **Old single-list menu still opens** — a v0 window was still alive;
  re-run `./install.sh` (it closes leftover Paster windows).
- **Stale state** — the previously-focused window id is stashed at
  `$XDG_RUNTIME_DIR/paster-prev-win` (fallback `/tmp`); safe to delete.
