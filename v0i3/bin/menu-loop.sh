#!/usr/bin/env bash
# paster v0i3 — runs inside the Paster alacritty window.
# Loops fzf over entries.txt forever so the window is spawned once and then
# only shown/hidden via the i3 scratchpad (single instance, instant popup).
set -uo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRIES="$PASTER_DIR/entries.txt"

while true; do
  if [[ ! -r "$ENTRIES" ]]; then
    printf 'paster: entries file not found: %s\n' "$ENTRIES" >&2
    sleep 2
    continue
  fi

  if selection="$(fzf --reverse --no-multi --prompt='paster> ' < "$ENTRIES")" \
     && [[ -n "$selection" ]]; then
    printf '%s' "$selection" | "$PASTER_DIR/bin/paste-back.sh"
  else
    # Esc / Ctrl-C — hide without pasting; entries stay ready for next toggle.
    i3-msg -q '[class="Paster"] move scratchpad'
  fi
done
