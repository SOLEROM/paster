#!/usr/bin/env bash
# paster v0i3 — hotkey entry point.
# Shows/hides the Paster window and captures the previously focused window
# so paste-back.sh can restore focus and paste there.
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
PREV_WIN_FILE="$STATE_DIR/paster-prev-win"

# Guake-ish top drop-down: full width, top POPUP_HEIGHT_PCT% of the screen
# the user is currently working on. Geometry is computed per-toggle from the
# focused workspace's rect (per-output, excludes the bar) so on multi-monitor
# setups the popup always lands on the active screen.
POPUP_HEIGHT_PCT=40

popup_geometry() {
  local x y w h
  if read -r x y w h < <(i3-msg -t get_workspaces 2>/dev/null \
        | jq -r '.[] | select(.focused) | "\(.rect.x) \(.rect.y) \(.rect.width) \(.rect.height)"' 2>/dev/null) \
      && [[ -n "${h:-}" ]]; then
    printf 'resize set %d px %d px, move absolute position %d px %d px' \
      "$w" $(( h * POPUP_HEIGHT_PCT / 100 )) "$x" "$y"
  else
    # Fallback if the workspace query fails: single-screen static geometry.
    printf 'resize set 100 ppt %d ppt, move absolute position 0 px 0 px' \
      "$POPUP_HEIGHT_PCT"
  fi
}

# WM_CLASS "general" part, e.g. `WM_CLASS(STRING) = "Navigator", "firefox"`
# -> firefox. (xdotool getwindowclassname is missing on older xdotool.)
win_class() { xprop -id "$1" WM_CLASS 2>/dev/null | awk -F'"' '{print $4}'; }

active_win="$(xdotool getactivewindow 2>/dev/null || true)"
active_class=""
if [[ -n "$active_win" ]]; then
  active_class="$(win_class "$active_win")"
fi

if [[ "$active_class" == "Paster" ]]; then
  # Paster is visible and focused — the hotkey acts as "hide".
  i3-msg -q '[class="Paster"] move scratchpad'
  exit 0
fi

# About to show the menu: remember where the user was.
if [[ -n "$active_win" ]]; then
  printf '%s\n' "$active_win" > "$PREV_WIN_FILE"
fi

if xdotool search --class '^Paster$' >/dev/null 2>&1; then
  i3-msg -q "[class=\"Paster\"] scratchpad show, $(popup_geometry)"
else
  alacritty --class Paster,Paster \
    --config-file "$PASTER_DIR/config/alacritty-paster.toml" \
    -e "$PASTER_DIR/bin/menu-loop.sh" &
  # Wait for the window to map (spawns on the focused workspace, i.e. the
  # current screen), then place it.
  for _ in $(seq 1 50); do
    xdotool search --class '^Paster$' >/dev/null 2>&1 && break
    sleep 0.1
  done
  i3-msg -q "[class=\"Paster\"] $(popup_geometry)" || true
fi
