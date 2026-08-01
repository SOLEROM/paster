# paster v2 — tabbed Guake-style prompt paster for any Ubuntu desktop

A drop-down, semi-transparent, fuzzy-searchable menu of reusable prompt
lines, organized in **tabs**. Press the hotkey anywhere, pick a tab (or
search across all of them), type a few characters, hit Enter — the popup
hides, focus returns to the window you came from, and the chosen line is
pasted there.

v2 removes the hard i3 dependency of v0/v1: the same thin shell layer
(`fzf`, `xdotool`, `xclip`, `alacritty` — no custom GUI app, no daemon) now
runs on **any Ubuntu desktop** through a small window-manager backend
(`bin/lib-wm.sh`), picked automatically on every toggle:

| backend | where | how |
|---|---|---|
| `i3` | i3 / Regolith | native scratchpad + `for_window` rule (v1 behavior, unchanged) |
| `ewmh` | any other X11 desktop (GNOME on Xorg, XFCE, KDE, MATE, Cinnamon, LXQt, …) | `xdotool` map/unmap keeps the menu process alive (instant re-show); `wmctrl` sets always-on-top / sticky / skip-taskbar |
| `wayland-degraded` | GNOME on Wayland (stock Ubuntu login) | popup forced onto XWayland; **copy works, auto-paste doesn't** — see Tiers |

## Tiers — what works where

- **Tier 1 (any X11 session):** everything — popup, tabs, search, hide,
  focus-restore, auto-paste into the window you came from.
- **Tier 2 (GNOME on Wayland):** popup, tabs, search, copy-to-clipboard, and
  a notification; the auto-paste keystroke is impossible for native Wayland
  windows (no `xdotool` there), so you press Ctrl+V yourself. For the full
  experience pick **"Ubuntu on Xorg"** at the login screen.
- Wayland with non-GNOME desktops is not supported — log in with Xorg.

## Entries = folders

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
- Everything is rescanned on every menu cycle — add a folder or edit a
  `content.md` and it shows up on the next popup, no reload needed.

## Install

```sh
./install.sh                # hotkey from config.yaml (default Ctrl+space)
./install.sh 'Mod4+p'       # pass an i3-style key to pick your own
./install.sh --sxhkd        # force the sxhkd hotkey fallback (any X11 WM)
./install.sh --dry-run      # show what would be detected/changed, change nothing
./install.sh --uninstall    # reverse whatever a previous run wired
```

The installer detects your session and wires the hotkey through whatever
your desktop actually provides:

| desktop | hotkey wiring |
|---|---|
| Regolith i3 | drop-in file `~/.config/regolith3/i3/config.d/90_paster` |
| plain i3 | markered block appended to `~/.config/i3/config` (+ backup, + `i3-msg reload`) |
| GNOME / Ubuntu (Xorg **and** Wayland) | `gsettings` custom shortcut named `paster` |
| Cinnamon | `gsettings` custom shortcut |
| MATE | `dconf` custom shortcut |
| XFCE | `xfconf` custom command |
| KDE / LXQt / other | prints exact manual instructions; or `--sxhkd` installs sxhkd with a markered rc block + autostart entry |

It also checks the dependencies (`fzf xdotool xclip xprop`, plus `jq` on
i3 or `wmctrl`/`xrandr` elsewhere) and apt-installs anything missing,
including `alacritty`. Re-running is idempotent — it replaces the previous
wiring, **including v0i3/v1 blocks** on i3, so installing v2 cleanly
supersedes them. The hotkey in `config.yaml` is written in i3-style
(`Ctrl+space`, `Mod4+p`) and translated per desktop; `$mod` only exists on
i3/Regolith.

## Usage

- **Hotkey** — toggle the popup on the screen you're currently working on
  (focused workspace on i3, monitor under the mouse elsewhere).
- **← / →** (or **Ctrl-h / Ctrl-l**) — previous / next tab.
- **Ctrl-a** — toggle **ALL mode**: every line from every tab in one list
  (prefixed `[Tab]`), so typing filters across all tabs at once. The text
  you already typed is kept when switching tabs or modes.
- Type to fuzzy-filter, **Enter** — copy the line to the clipboard, hide,
  refocus your previous window, and auto-paste there (`Ctrl+Shift+V` if
  that window is a known terminal, `Ctrl+V` otherwise). On Tier 2 the
  paste step is replaced by a "press Ctrl+V" notification.
- **Esc** (or the hotkey again) — hide without pasting.

The first hotkey press spawns the window; after that it stays alive hidden
(i3 scratchpad, or unmapped elsewhere) and pops instantly — and remembers
which tab you were on.

## config.yaml — global settings

All knobs live in `config.yaml` at the root of this folder. Apply changes
by re-running `./install.sh` (it re-wires the hotkey and restarts the
popup window):

| key          | default      | meaning                                              |
|--------------|--------------|------------------------------------------------------|
| `hotkey`     | `Ctrl+space` | toggle key, i3-style notation, translated per desktop |
| `width_pct`  | `100`        | popup width in % of the screen; `<100` is centered, shrunk equally from both sides |
| `height_pct` | `40`         | popup height in % of the screen, from the top        |
| `opacity_pct`| `85`         | `100` = solid, lower = more transparent              |
| `background` | `#10141a`    | popup background color (`"#rrggbb"`)                 |
| `foreground` | `#d8dee9`    | popup text color                                     |
| `font_size`  | `12`         | popup font size                                      |
| `border_px`  | `1`          | window border in pixels — **i3 only**, ignored elsewhere |

Size keys (`width_pct`, `height_pct`) are read live on every toggle; look
keys are applied when the popup window spawns and the hotkey when the
installer runs — re-running `./install.sh` covers all cases in one step.
Invalid values fall back to the defaults with a warning.

## Layout

```
v2/
├── config.yaml                  # global settings (size, colors, hotkey, …)
├── entries/                     # one subfolder per tab
│   └── <NN_TabName>/content.md  #   one entry per line
├── bin/
│   ├── toggle.sh                # hotkey target: capture focus, show/hide/spawn
│   ├── menu-loop.sh             # inside the window: tabbed fzf loop
│   ├── paste-back.sh            # clipboard + hide + focus-restore + paste keystroke
│   ├── lib-wm.sh                # WM backends: i3 / ewmh / wayland-degraded
│   ├── lib-hotkey.sh            # i3-style hotkey -> gsettings/xfconf/sxhkd formats
│   └── lib-config.sh            # config.yaml reader
├── config/
│   ├── i3.conf.snippet          # i3 window rule + keybinding (template)
│   └── alacritty-paster.toml    # base profile; config.yaml overrides at spawn
├── tests/
│   └── test-hotkey.sh           # table-driven checks for lib-hotkey.sh
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

- **Hotkey does nothing** — run `./install.sh --dry-run` to see which
  wiring was detected. GNOME: check Settings → Keyboard → Custom Shortcuts
  for the `paster` entry and key conflicts. XFCE: Keyboard → Application
  Shortcuts. i3: `pgrep -a i3` shows which config file the session loads;
  confirm the paster block/drop-in is in the matching location.
- **No transparency** — on bare i3 there is no compositor by default;
  start picom. GNOME/KDE/XFCE composite out of the box.
- **Paste lands nowhere** — the selection is always on the clipboard, so
  `Ctrl+V` manually; happens if the previous window closed meanwhile —
  and always on Tier 2 (Wayland), where auto-paste is not possible.
- **Wrong paste keystroke in some app** — add its WM_CLASS to
  `TERMINAL_CLASSES` (or remove it) in `bin/paste-back.sh`.
- **Popup not on top / on the wrong monitor (non-i3)** — needs `wmctrl`
  and `xrandr` (installed by `./install.sh`); the popup targets the
  monitor under the mouse pointer.
- **Old single-list menu still opens** — a v0/v1 window was still alive;
  re-run `./install.sh` (it closes leftover Paster windows).
- **Stale state** — the previously-focused window id is stashed at
  `$XDG_RUNTIME_DIR/paster-prev-win` (fallback `/tmp`); safe to delete.
  The installer's record of what it wired lives in `.install-state`.
