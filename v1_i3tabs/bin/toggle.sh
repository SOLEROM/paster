#!/usr/bin/env bash
# paster v1 — hotkey entry point.
# Shows/hides the Paster window and captures the previously focused window
# so paste-back.sh can restore focus and paste there.
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
PREV_WIN_FILE="$STATE_DIR/paster-prev-win"

# Global settings (size %, opacity, colors, font) from <root>/config.yaml.
source "$PASTER_DIR/bin/lib-config.sh"

# Guake-ish top drop-down on the screen the user is currently working on.
# Geometry is computed per-toggle from the focused workspace's rect
# (per-output, excludes the bar) so on multi-monitor setups the popup always
# lands on the active screen. width_pct < 100 centers the popup, shrinking
# it equally from both sides.
# Sets GEO_CMD (i3 command string) and GEO_W (expected width px; 0 = unknown,
# when the fallback path couldn't read the workspace rect).
compute_geometry() {
  local x y w h pw ph px
  if read -r x y w h < <(i3-msg -t get_workspaces 2>/dev/null \
        | jq -r '.[] | select(.focused) | "\(.rect.x) \(.rect.y) \(.rect.width) \(.rect.height)"' 2>/dev/null) \
      && [[ -n "${h:-}" ]]; then
    pw=$(( w * PASTER_CFG_WIDTH_PCT / 100 ))
    ph=$(( h * PASTER_CFG_HEIGHT_PCT / 100 ))
    px=$(( x + (w - pw) / 2 ))
    GEO_CMD="resize set ${pw} px ${ph} px, move absolute position ${px} px ${y} px"
    GEO_W=$pw
  else
    # Fallback if the workspace query fails: static geometry, primary screen.
    GEO_CMD="resize set ${PASTER_CFG_WIDTH_PCT} ppt ${PASTER_CFG_HEIGHT_PCT} ppt, move absolute position 0 px 0 px"
    GEO_W=0
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

compute_geometry

if xdotool search --class '^Paster$' >/dev/null 2>&1; then
  i3-msg -q "[class=\"Paster\"] scratchpad show, $GEO_CMD"
else
  # Look settings are injected at spawn via -o, so config.yaml wins over the
  # base profile. They stick for the window's lifetime; ./install.sh closes
  # the old window, which is how look changes get applied.
  opacity="$(awk -v p="$PASTER_CFG_OPACITY_PCT" 'BEGIN{printf "%.2f", p/100}')"
  alacritty --class Paster,Paster \
    --config-file "$PASTER_DIR/config/alacritty-paster.toml" \
    -o "window.opacity=$opacity" \
    -o "font.size=$PASTER_CFG_FONT_SIZE" \
    -o "colors.primary.background=\"$PASTER_CFG_BACKGROUND\"" \
    -o "colors.primary.foreground=\"$PASTER_CFG_FOREGROUND\"" \
    -e "$PASTER_DIR/bin/menu-loop.sh" &
  # Wait for the window to map (spawns on the focused workspace, i.e. the
  # current screen), then place it.
  for _ in $(seq 1 50); do
    xdotool search --class '^Paster$' >/dev/null 2>&1 && break
    sleep 0.1
  done
  # The for_window rule floats the fresh window with i3's default float
  # geometry a moment after it maps, which can override an early resize —
  # re-apply until the requested width sticks.
  for _ in $(seq 1 10); do
    i3-msg -q "[class=\"Paster\"] $GEO_CMD" || true
    sleep 0.15
    cur_w="$(i3-msg -t get_tree 2>/dev/null \
      | jq -r 'first(.. | objects | select(.window_properties?.class? == "Paster")) | .rect.width' 2>/dev/null || true)"
    [[ "$GEO_W" -eq 0 || "$cur_w" == "$GEO_W" ]] && break
  done
fi
