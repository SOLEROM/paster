#!/usr/bin/env bash
# paster v2 — window-manager backend layer. Source this file (after
# lib-config.sh when geometry is needed); every window-management action the
# runtime scripts need goes through the wm_* functions below, so nothing
# outside this file talks to a WM directly.
#
# Backends (detected per invocation — cheap, and it survives the user
# switching session types without reinstalling; override with
# PASTER_WM_BACKEND for testing):
#   i3               — i3/Regolith: scratchpad + i3-msg geometry
#   ewmh             — any other X11 WM/DE: xdotool map/unmap keeps the
#                      menu-loop process alive (instant re-show), wmctrl
#                      applies the on-top/sticky/skip-taskbar EWMH hints
#                      that i3 gets from its for_window rule
#   wayland-degraded — GNOME on Wayland: the popup is forced onto XWayland
#                      so the X tools still drive it; auto-paste into native
#                      windows is not possible and paste-back.sh skips it
#
# Geometry contract: wm_compute_geometry sets GEO_X/GEO_Y/GEO_W/GEO_H
# (pixels) and GEO_KNOWN (0 = no monitor rect resolved; the i3 backend then
# falls back to percent-of-screen, the others leave placement to the WM).

wm_backend() {
  if [[ -n "${PASTER_WM_BACKEND:-}" ]]; then
    printf '%s' "$PASTER_WM_BACKEND"
  elif i3-msg -t get_version >/dev/null 2>&1; then
    printf 'i3'
  elif [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    printf 'wayland-degraded'
  else
    printf 'ewmh'
  fi
}
PASTER_WM="$(wm_backend)"

# First window id with class Paster; empty if none. Deliberately not
# --onlyvisible: the hidden (scratchpad / unmapped) window must be found.
wm_paster_id() {
  { xdotool search --class '^Paster$' 2>/dev/null || true; } | head -n1
}

wm_hide() {
  local id
  case "$PASTER_WM" in
    i3)
      i3-msg -q '[class="Paster"] move scratchpad' >/dev/null 2>&1 || true
      ;;
    *)
      id="$(wm_paster_id)"
      [[ -n "$id" ]] && xdotool windowunmap "$id" 2>/dev/null
      ;;
  esac
  return 0
}

_wm_geo_from_rect() {  # X Y W H of a monitor/workspace -> GEO_* via config %
  local x="$1" y="$2" w="$3" h="$4"
  GEO_W=$(( w * PASTER_CFG_WIDTH_PCT / 100 ))
  GEO_H=$(( h * PASTER_CFG_HEIGHT_PCT / 100 ))
  GEO_X=$(( x + (w - GEO_W) / 2 ))
  GEO_Y=$y
  GEO_KNOWN=1
}

# Prints "X Y W H" of the xrandr monitor under the mouse pointer (the
# non-i3 stand-in for "the screen you are working on"); falls back to the
# first active monitor. Non-zero when xrandr gave nothing usable.
_wm_monitor_under_mouse() {
  local mx="" my="" line geo W H X Y first=""
  read -r mx my < <(xdotool getmouselocation --shell 2>/dev/null \
    | awk -F= '/^X=/{x=$2} /^Y=/{y=$2} END{if (x != "" && y != "") print x, y}') || true
  while IFS= read -r line; do
    geo="$(awk '{print $3}' <<<"$line")"   # e.g. 1920/344x1080/194+0+0
    [[ "$geo" =~ ^([0-9]+)(/[0-9]+)?x([0-9]+)(/[0-9]+)?\+([0-9]+)\+([0-9]+)$ ]] || continue
    W="${BASH_REMATCH[1]}"; H="${BASH_REMATCH[3]}"
    X="${BASH_REMATCH[5]}"; Y="${BASH_REMATCH[6]}"
    [[ -z "$first" ]] && first="$X $Y $W $H"
    if [[ -n "$mx" && -n "$my" ]] \
        && (( mx >= X && mx < X + W && my >= Y && my < Y + H )); then
      printf '%s %s %s %s\n' "$X" "$Y" "$W" "$H"
      return 0
    fi
  done < <(xrandr --listactivemonitors 2>/dev/null | tail -n +2)
  [[ -n "$first" ]] && { printf '%s\n' "$first"; return 0; }
  return 1
}

wm_compute_geometry() {
  GEO_X=0; GEO_Y=0; GEO_W=0; GEO_H=0; GEO_KNOWN=0
  local x y w h
  if [[ "$PASTER_WM" == "i3" ]]; then
    # Focused workspace rect: per-output and excludes the bar.
    if read -r x y w h < <(i3-msg -t get_workspaces 2>/dev/null \
          | jq -r '.[] | select(.focused) | "\(.rect.x) \(.rect.y) \(.rect.width) \(.rect.height)"' 2>/dev/null) \
        && [[ -n "${h:-}" ]]; then
      _wm_geo_from_rect "$x" "$y" "$w" "$h"
    fi
  elif read -r x y w h < <(_wm_monitor_under_mouse) && [[ -n "${h:-}" ]]; then
    _wm_geo_from_rect "$x" "$y" "$w" "$h"
  elif read -r w h < <(xdotool getdisplaygeometry 2>/dev/null) && [[ -n "${h:-}" ]]; then
    _wm_geo_from_rect 0 0 "$w" "$h"
  fi
  return 0
}

_wm_i3_geo_cmd() {  # i3 command string for the current GEO_*
  if (( GEO_KNOWN )); then
    printf 'resize set %s px %s px, move absolute position %s px %s px' \
      "$GEO_W" "$GEO_H" "$GEO_X" "$GEO_Y"
  else
    # Workspace query failed: static geometry, primary screen.
    printf 'resize set %s ppt %s ppt, move absolute position 0 px 0 px' \
      "$PASTER_CFG_WIDTH_PCT" "$PASTER_CFG_HEIGHT_PCT"
  fi
}

wm_place() {  # $1 = window id (no-op for i3 — geometry rides the i3 commands)
  (( GEO_KNOWN )) || return 0
  xdotool windowsize "$1" "$GEO_W" "$GEO_H" 2>/dev/null || true
  xdotool windowmove "$1" "$GEO_X" "$GEO_Y" 2>/dev/null || true
  return 0
}

# Non-i3 stand-in for the i3 for_window rule: always-on-top, on every
# workspace, out of the taskbar/pager. Floating needs no request outside
# tiling WMs, and the window is already undecorated via alacritty config.
wm_apply_window_props() {  # $1 = window id
  command -v wmctrl >/dev/null 2>&1 || return 0
  wmctrl -i -r "$1" -b add,above,sticky 2>/dev/null || true
  wmctrl -i -r "$1" -b add,skip_taskbar,skip_pager 2>/dev/null || true
  return 0
}

wm_show() {  # $1 = paster window id (must exist)
  case "$PASTER_WM" in
    i3)
      i3-msg -q "[class=\"Paster\"] scratchpad show, $(_wm_i3_geo_cmd)" >/dev/null 2>&1 || true
      ;;
    *)
      xdotool windowmap "$1" 2>/dev/null || true
      wm_place "$1"
      wm_apply_window_props "$1"
      xdotool windowactivate "$1" 2>/dev/null || true
      ;;
  esac
  return 0
}

wm_spawn() {  # run the popup command ("$@") detached
  if [[ "$PASTER_WM" == "wayland-degraded" ]]; then
    # Without WAYLAND_DISPLAY alacritty (winit) falls back to X11, i.e.
    # XWayland — which is what keeps xdotool/xclip working on Wayland.
    env -u WAYLAND_DISPLAY "$@" &
  else
    "$@" &
  fi
  return 0
}

# The WM floats/positions a freshly mapped window a moment after it maps,
# which can override an early resize — re-apply until the width sticks.
wm_settle_new_window() {  # $1 = window id
  local cur_w=""
  case "$PASTER_WM" in
    i3)
      for _ in $(seq 1 10); do
        i3-msg -q "[class=\"Paster\"] $(_wm_i3_geo_cmd)" >/dev/null 2>&1 || true
        sleep 0.15
        cur_w="$(i3-msg -t get_tree 2>/dev/null \
          | jq -r 'first(.. | objects | select(.window_properties?.class? == "Paster")) | .rect.width' 2>/dev/null || true)"
        [[ "$GEO_KNOWN" -eq 0 || "$cur_w" == "$GEO_W" ]] && break
      done
      ;;
    *)
      for _ in $(seq 1 10); do
        wm_apply_window_props "$1"
        wm_place "$1"
        sleep 0.15
        cur_w="$(xdotool getwindowgeometry --shell "$1" 2>/dev/null \
          | sed -n 's/^WIDTH=//p' || true)"
        [[ "$GEO_KNOWN" -eq 0 || "$cur_w" == "$GEO_W" ]] && break
      done
      xdotool windowactivate "$1" 2>/dev/null || true
      ;;
  esac
  return 0
}

wm_kill_paster() {  # close any Paster window (used by the installer)
  local id
  case "$PASTER_WM" in
    i3)
      i3-msg -q '[class="Paster"] kill' >/dev/null 2>&1 || true
      ;;
    *)
      while IFS= read -r id; do
        [[ -n "$id" ]] && xdotool windowkill "$id" 2>/dev/null
      done < <(xdotool search --class '^Paster$' 2>/dev/null || true)
      ;;
  esac
  return 0
}
