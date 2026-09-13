---
project: 'paster'
type: planning
target_repo: '/ (v3 root)'
strategy_hint: 'extend, do not restructure: paste behavior becomes config.yaml keys read by paste-back.sh at paste time'
version: 1
date: '2026-09-11'
status: decisions locked, implemented at repo root
---

# paster v3.1 — configurable paste-back (`auto_paste` & friends), plan

> Goal: on Enter the selected line is put on the clipboard **and** pasted
> into the previous window, with the paste step (and everything around it)
> driven by `config.yaml` instead of constants inside `bin/paste-back.sh`.
> `auto_paste: true` is the headline key; the other keys expose the knobs
> the README already told users to edit by hand in the script.

## 1. Feature: current state (what already exists)

v3 already pastes on Enter: `tab-mode.sh` (ROFI_RETV=1) waits for rofi to
exit, then pipes the pick to `paste-back.sh`, which does

    xclip -selection clipboard  ->  xdotool windowactivate <prev>  ->
    sleep 0.15  ->  xdotool key ctrl+v | ctrl+shift+v (terminal WM_CLASS)

Everything after the clipboard step is hardcoded: the 150 ms delay, both
keystrokes, and the `TERMINAL_CLASSES` regex. `config.yaml` exists and is
parsed by `lib-config.sh` (flat `key: value`, validated, defaults on bad
input) but only carries look/size/hotkey keys, and `paste-back.sh` does not
source it. So the change is "make the last leg configurable", not "add
pasting".

## 2. Feature: config keys (decisions locked)

New section in `config.yaml`, same flat syntax. All keys optional; a
missing or invalid value falls back to the default with the usual
`paster: config KEY=... invalid` warning on stderr.

| key                  | default                 | validation                         | effect |
|----------------------|-------------------------|------------------------------------|--------|
| `auto_paste`         | `true`                  | bool: true/false/yes/no/on/off/1/0 | `false` = clipboard + refocus only, no keystroke |
| `paste_delay_ms`     | `150`                   | int 0–5000                         | wait after refocus before the keystroke (was `sleep 0.15`) |
| `paste_key`          | `ctrl+v`                | xdotool key syntax `[A-Za-z0-9_+]+` | keystroke for ordinary windows |
| `terminal_paste_key` | `ctrl+shift+v`          | same                               | keystroke when WM_CLASS matches `terminal_classes` |
| `terminal_classes`   | *(the v3 list)*         | `\|`-separated `[A-Za-z0-9_.-]+` tokens | WM_CLASS names (case-insensitive) that get `terminal_paste_key` |
| `press_enter`        | `false`                 | bool                               | send `Return` after the paste (submit in chat UIs / run in a terminal) |

Decisions:

- **One file.** No separate `settings.yaml`: `config.yaml` is already "the
  global settings file" in README and installer; a second file would split
  the story. The user's `auto_paste=true` spelling becomes `auto_paste: true`
  (the parser is `key: value` YAML).
- **Read at paste time.** `paste-back.sh` sources `lib-config.sh` itself
  instead of receiving values through the rofi → tab-mode → setsid
  environment chain. Robust when run standalone
  (`printf x | bin/paste-back.sh`) and consistent with "edit config.yaml,
  applies on next use" — the paste keys apply on the next Enter.
- **No `restore_focus` key.** `auto_paste: false` still refocuses the
  previous window (clipboard is loaded, user presses Ctrl+V). A
  copy-without-refocus mode has no use case; rofi closing already returns
  focus in i3.
- **Disabling terminal detection** = set `terminal_paste_key` to the same
  value as `paste_key`. An empty `terminal_classes` means "use the
  default" (parser rule for every key), not "none".
- **`press_enter` waits `paste_delay_ms` again** before `Return`, so the
  target app has processed the paste. Default off — in a terminal it runs
  the pasted line.

## 3. Feature: implementation tasks

| # | file | change |
|---|------|--------|
| T1 | `tests/test-config.sh` | table-driven checks for the new validators and keys (written first, RED) |
| T2 | `tests/test-paste-back.sh` | runs `paste-back.sh` against stub `xclip`/`xdotool`/`xprop`/`sleep` on `PATH`, asserts the call log per config (RED) |
| T3 | `bin/lib-config.sh` | `_paster_bool`, `_paster_keystroke`, `_paster_classes`; six `PASTER_CFG_*` vars; default list moved here from paste-back |
| T4 | `bin/paste-back.sh` | source lib-config; `auto_paste` gate after refocus; keys/delay/classes from config; `press_enter` |
| T5 | `config.yaml` | "Paste behavior" section with the six keys and comments |
| T6 | `README.md`, `devRef/README.md` | config table, usage bullet, customization + troubleshooting now point at config.yaml; layout gains `tests/`; plan5 in history |
| T7 | `tests/run.sh` | runs T1+T2; documented in README |

Unchanged: `toggle.sh` (still sources lib-config, so bad paste keys warn at
toggle time too), `tab-mode.sh`, `install.sh`, the rasi template.

## 4. Feature: test approach

No bats on the box; same plain-bash `expect` style as
`devRef/v2/tests/test-hotkey.sh`. `lib-config.sh` honours
`PASTER_CONFIG_FILE`, so config tests write temp YAML files. `paste-back.sh`
honours `XDG_RUNTIME_DIR` for the prev-window file, and finds its tools via
`PATH`, so the paste tests prepend a stub dir and read back a log. Run
`./tests/run.sh` (exit 0 = green). Manual desktop check after install:
Enter in a terminal and in a browser text field with `auto_paste` true and
false, then `press_enter: true` in a chat field.

## 5. Open / deferred

- Wayland (`wl-copy`/`wtype`) stays out of scope, as in plan4.
- A `paste_method: type` mode (`xdotool type` instead of a keystroke, for
  targets with no clipboard paste) is easy to add on this structure but
  has no requester yet.
