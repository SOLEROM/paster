# Troubleshooting

- **The hotkey does nothing** — Doctor › *Hotkey binding*. Red means the
  drop-in or block is missing: Apply (or `./install.sh`). Yellow with "a
  different checkout" means the binding still points at the path the repo
  had before it moved.
- **The popup looks wrong after a config change** — the theme renders on
  the next toggle; if a value is invalid the popup used the default, and
  Config shows lib-config.sh's warning under the field.
- **"changed on disk" when saving** — something else wrote the file (vim,
  another browser, a restore). The panel reloaded; your text is back in
  the editor. Look, then save again.
- **Open the popup / Apply are disabled** — the server has no `DISPLAY`
  (Doctor › *Session*). The systemd user unit inherits it from an X11
  login; a server started over SSH does not have it.
- **A blank white strip in the footer** — remdev (port 6005) is not
  reachable from *this* browser; the Claude meters live there. Start
  remdev; the bar recovers on its own.
- **The Sessions view says no terminal** — webterm is not installed in
  the venv: `./run.sh` repairs it from `../solBench` on the next start.
- **Everything else** — the popup's own troubleshooting in the README
  (paste lands nowhere, wrong monitor, stale state); *Clear stale state*
  in the Doctor is the same as deleting `$XDG_RUNTIME_DIR/paster-*`.
- Logs: `journalctl --user -u paster -f`; the in-app **Log** button holds
  the activity ring.
