# paster v0i3 — Guake-style prompt paster for i3/X11

A drop-down, semi-transparent, fuzzy-searchable menu of reusable prompt
lines. Press the hotkey anywhere, type a few characters, hit Enter — the
popup hides, focus returns to the window you came from, and the chosen line
is pasted there.

No custom GUI app, no daemon: a thin shell layer over `fzf`, `xdotool`,
`xclip`, `alacritty`, and i3's native **scratchpad**, which provides
single-instance, show/hide, always-on-top, and sticky behavior for free.
Transparency comes from the running compositor (picom).

## Requirements

- X11 session with **i3** (Wayland is not supported)
- A compositor for transparency (picom, or opacity is simply ignored)
- `fzf`, `xdotool`, `xclip` (checked by the installer)
- `alacritty` (installed by the installer via apt if missing)

## Install

```sh
./install.sh              # default hotkey: $mod+p (Super+p) on Regolith, Mod1+p (Alt+p) on plain i3
./install.sh 'Mod4+p'     # or pass any key bindsym accepts to pick your own
```

The installer:

1. Verifies X11/i3 and the dependencies; apt-installs `alacritty` if missing.
2. Makes the scripts in `bin/` executable.
3. Wires the snippet into whichever config your session actually uses:
   - **Regolith i3** (detected via `~/.config/regolith3/i3/config.d/`) —
     writes a drop-in file `config.d/90_paster`. Regolith launches i3 with
     `-c /etc/regolith/i3/config` and never reads `~/.config/i3/config`,
     so the drop-in directory is the only place user config takes effect.
   - **Plain i3** — seeds `~/.config/i3/config` from `/etc/i3/config` if
     missing, backs it up to `config.paster-backup`, and appends the block.
4. Reloads i3. Re-running is idempotent and replaces the previous block —
   which is also how you **rebind the hotkey**: just run
   `./install.sh '<new-key>'` again.

Manual install: substitute `__PASTER_DIR__` and `__PASTER_KEY__` in
`config/i3.conf.snippet`, put it where your i3 reads config (see above),
and `i3-msg reload`.

## Usage

- **Hotkey** (default: Super+p on Regolith, Alt+p on plain i3) — toggle the
  menu. Full-width panel over the top 40% of the screen.
- Type to fuzzy-filter, **Enter** — copy the line to the clipboard, hide,
  refocus your previous window, and auto-paste there (`Ctrl+Shift+V` if
  that window is a known terminal, `Ctrl+V` otherwise).
- **Esc** (or Alt+p again) — hide without pasting.

The first hotkey press spawns the window; after that it lives hidden in the
i3 scratchpad and pops instantly.

## Layout

```
v0i3/
├── entries.txt                  # one prompt per line (edit freely; git-tracked)
├── bin/
│   ├── toggle.sh                # hotkey target: capture focus, show/hide/spawn
│   ├── menu-loop.sh             # runs inside the window: fzf loop over entries.txt
│   └── paste-back.sh            # clipboard + hide + focus-restore + paste keystroke
├── config/
│   ├── i3.conf.snippet          # window rule + keybinding (template)
│   └── alacritty-paster.toml    # Paster-only profile: opacity, no decorations
├── install.sh
└── README.md
```

## Customization

- **Entries** — edit `entries.txt`; picked up on the next popup, no reload
  needed (fzf re-reads it every cycle).
- **Hotkey / modifier** — re-run `./install.sh '<key>'` with anything
  `bindsym` accepts, e.g. `'Mod4+p'` (Super+p), `'Mod1+space'` (Alt+Space),
  `'ctrl+Mod1+v'`. It replaces the old binding and reloads i3 in one step.
- **Size/position** — geometry is computed per-toggle in `bin/toggle.sh`
  from the focused workspace's rect, so on multi-monitor setups the popup
  always opens full-width on the screen you're currently working on.
  Change `POPUP_HEIGHT_PCT` (default 40) there to adjust the height.
- **Look** — opacity, font, and colors in `config/alacritty-paster.toml`.
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
  chosen key isn't bound elsewhere (`grep -rn 'bindsym' <config locations>`).
- **Stale state** — the previously-focused window id is stashed at
  `$XDG_RUNTIME_DIR/paster-prev-win` (fallback `/tmp`); safe to delete.
