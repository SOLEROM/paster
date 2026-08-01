#!/usr/bin/env bash
# paster v2 — hotkey entry point.
# Shows/hides the Paster window and captures the previously focused window
# so paste-back.sh can restore focus and paste there. All window-manager
# work goes through bin/lib-wm.sh (i3 scratchpad, generic X11 EWMH, or the
# degraded Wayland backend — picked per invocation).
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
PREV_WIN_FILE="$STATE_DIR/paster-prev-win"

# Global settings (size %, opacity, colors, font) from <root>/config.yaml,
# then the WM backend layer (which reads the size settings for geometry).
source "$PASTER_DIR/bin/lib-config.sh"
source "$PASTER_DIR/bin/lib-wm.sh"

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
  wm_hide
  exit 0
fi

# About to show the menu: remember where the user was. Pointless on Wayland,
# where focus can't be handed back to native windows from here.
if [[ -n "$active_win" && "$PASTER_WM" != "wayland-degraded" ]]; then
  printf '%s\n' "$active_win" > "$PREV_WIN_FILE"
fi

# Guake-ish top drop-down on the screen the user is currently working on:
# i3 uses the focused workspace rect (excludes the bar), the other backends
# the monitor under the mouse. width_pct < 100 centers the popup.
wm_compute_geometry

paster_id="$(wm_paster_id)"
if [[ -n "$paster_id" ]]; then
  wm_show "$paster_id"
else
  # Look settings are injected at spawn via -o, so config.yaml wins over the
  # base profile. They stick for the window's lifetime; ./install.sh closes
  # the old window, which is how look changes get applied.
  opacity="$(awk -v p="$PASTER_CFG_OPACITY_PCT" 'BEGIN{printf "%.2f", p/100}')"
  wm_spawn alacritty --class Paster,Paster \
    --config-file "$PASTER_DIR/config/alacritty-paster.toml" \
    -o "window.opacity=$opacity" \
    -o "font.size=$PASTER_CFG_FONT_SIZE" \
    -o "colors.primary.background=\"$PASTER_CFG_BACKGROUND\"" \
    -o "colors.primary.foreground=\"$PASTER_CFG_FOREGROUND\"" \
    -e "$PASTER_DIR/bin/menu-loop.sh"
  # Wait for the window to map (it spawns on the focused workspace/monitor),
  # then place it and pin its properties until they stick.
  for _ in $(seq 1 50); do
    paster_id="$(wm_paster_id)"
    [[ -n "$paster_id" ]] && break
    sleep 0.1
  done
  if [[ -n "$paster_id" ]]; then
    wm_settle_new_window "$paster_id"
  fi
fi
