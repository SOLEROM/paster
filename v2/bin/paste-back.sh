#!/usr/bin/env bash
# paster v2 — delivers the selected entry (read from stdin).
# clipboard -> hide the Paster window -> restore focus to the previous window
# -> simulated paste keystroke (Ctrl+Shift+V for terminals, Ctrl+V otherwise).
# On the wayland-degraded backend the last two steps are impossible for
# native windows, so delivery stops at the clipboard plus a notification.
set -uo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
PREV_WIN_FILE="$STATE_DIR/paster-prev-win"

source "$PASTER_DIR/bin/lib-wm.sh"

# WM_CLASS values that expect Ctrl+Shift+V instead of Ctrl+V.
TERMINAL_CLASSES='alacritty|kitty|urxvt|rxvt|xterm|st|st-256color|gnome-terminal|gnome-terminal-server|xfce4-terminal|konsole|terminator|tilix|termite|guake|lxterminal|sakura|qterminal|eterm|wezterm|org.wezfurlong.wezterm'

selection="$(cat)"
[[ -z "$selection" ]] && exit 0

# The popup runs on X (or XWayland), so xclip always works here; on GNOME
# Wayland, Mutter mirrors the X clipboard to the Wayland one.
printf '%s' "$selection" | xclip -selection clipboard

wm_hide

if [[ "$PASTER_WM" == "wayland-degraded" ]]; then
  command -v notify-send >/dev/null 2>&1 \
    && notify-send 'paster' 'Copied — press Ctrl+V to paste' 2>/dev/null
  exit 0
fi

prev_win=""
[[ -r "$PREV_WIN_FILE" ]] && prev_win="$(cat "$PREV_WIN_FILE")"
# No stashed window, or it no longer exists: the text is still on the
# clipboard, so the user can paste manually.
[[ -z "$prev_win" ]] && exit 0
xdotool windowactivate --sync "$prev_win" 2>/dev/null || exit 0

# WM_CLASS "general" part via xprop (getwindowclassname is missing on older xdotool)
target_class="$(xprop -id "$prev_win" WM_CLASS 2>/dev/null | awk -F'"' '{print $4}')"
shopt -s nocasematch
if [[ "$target_class" =~ ^($TERMINAL_CLASSES)$ ]]; then
  keystroke='ctrl+shift+v'
else
  keystroke='ctrl+v'
fi
shopt -u nocasematch

sleep 0.15  # let the focus switch settle before injecting the keystroke
xdotool key --clearmodifiers "$keystroke"
