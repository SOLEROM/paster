# paster front — overview

The front is a web GUI over the two things the rofi popup reads: the tab
folders under `entries/` and `config.yaml`. It runs as a small Flask
service (`./run.sh`, port 6012 on the bench) in the family's VS Code shape,
docks in mainBench like the other apps, and works from a phone on the
tailnet.

What it never does: change the entry format. A tab is a folder, an entry
is one non-empty line of that folder's `content.md`, the `NN_` prefix is
the order. What the GUI writes is exactly what `bin/toggle.sh` rescans on
the next hotkey press — no reload, no daemon.

## Views

| view | what |
|------|------|
| **Entries** | the tab list on the left (create, rename, drag to reorder, delete to trash); the selected tab's lines on the right — add, edit in place, duplicate, move to another tab, reorder, delete, bulk paste, sort, copy to the clipboard |
| **Doctor** | is the hotkey wired, which key, which checkout; rofi/xdotool/xclip/xprop present; compositor; stale state files; config warnings; entry health; the bash test suite; the desktop actions |
| **Sessions** | a shell in the repo (solBench/webterm) — **Shell in the repo** opens one in the checkout — for `./install.sh`, `git` and the like from anywhere |
| **Config** | a form over config.yaml with the same validation as `lib-config.sh`, or the raw file; a banner when the hotkey in the file is not the one i3 binds |
| **Help** | these pages |

**Open popup**, in the title bar, runs `bin/toggle.sh` on the laptop's
screen from whichever view is open — from a phone it is a remote trigger.
There is no picture of the popup: the popup is the preview.

Ctrl+P lists every entry across every tab (rofi's ALL mode) together with
the views and commands; picking an entry opens its tab and highlights it.

## Safety

- Every write is atomic and refused when the file changed since it was
  loaded (a `409`; the panel reloads and keeps your edit in the editor).
- Every version that ever existed on disk is in `~/.paster/history/`
  (50 per file). Deleting a tab moves the folder to `~/.paster/trash/`.
- Config edits replace values in place: your comments and order survive.
- No authentication. The service binds the tailnet (`--public`) like the
  rest of the family and the Sessions view is a real shell — trusted
  networks only (see Deployment).
