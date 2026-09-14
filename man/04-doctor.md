# Doctor

One table of checks, re-run on every open (and after any action).

| row | green means | when it is not |
|-----|-------------|----------------|
| Session | X11 with a `DISPLAY` in the server's environment | Wayland: paster v3 is X11 only. No `DISPLAY`: the desktop actions are disabled here (the unit inherits the user session's `DISPLAY` on an X11 login) |
| i3 | i3 running; Regolith or plain layout detected | start an i3 session |
| Hotkey binding | the drop-in `config.d/90_paster` (Regolith) or the `paster v3` block (plain) exists and points at **this** checkout | missing: run `./install.sh` (Apply). Pointing elsewhere: a stale install from before a move — Apply |
| Old paster block | — | a `paster v1`/`v0i3` block is still in the plain i3 config; `install.sh` removes it |
| Hotkey | config.yaml and the binding agree | Apply rebinds |
| rofi, xdotool, xclip, xprop | found (rofi ≥ 1.6) | the fix names the apt package; `./install.sh` installs them too |
| Compositor | picom (or another) running: real transparency | rofi uses pseudo-transparency — cosmetic |
| paster-prev-win, paster-last-tab, paster.rasi | the runtime state under `$XDG_RUNTIME_DIR` (the remembered tab is shown) | absent is fine; **Clear stale state** removes them |
| config.yaml | every value valid | each `lib-config.sh` warning is one row; fix it in Config |
| Entries | tabs and entries counted | empty tabs, ignored folders, folders rofi skips (empty label), duplicate lines across tabs, lines over 300 characters |
| Bash test suite | the last run from here passed | run it with the button; the output shows below the table |
| Service | systemd unit or foreground, the port, and whether `.port` disagrees | — |

## Actions

Every action is an argv subprocess with a timeout, run with the server's
own `DISPLAY`/`XAUTHORITY` and a freshly resolved `I3SOCK` (the one in the
environment goes stale when i3 restarts). One at a time per action, with
a two-second cooldown, so a double tap never opens two popups.

- **Open the popup** — `bin/toggle.sh`, on the laptop's screen (the same
  button sits in the title bar, on every view); press the
  hotkey or Esc there to close it.
- **Apply hotkey (install.sh)** — `./install.sh` from this repo: rewrites
  the i3 binding from config.yaml and reloads i3. Asks first.
- **Run the bash tests** — `tests/run.sh`.
- **Clear stale state** — deletes the three runtime files.

The exact command of each button is in its tooltip and in
`GET /api/actions`.
