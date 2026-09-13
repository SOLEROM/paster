#!/usr/bin/env bash
# paster v3 — delivers the selected entry (read from stdin).
# clipboard -> restore focus to the previous window -> simulated paste
# keystroke (terminal_paste_key for windows whose WM_CLASS is listed in
# terminal_classes, paste_key otherwise) -> optional Return.
# Every step after the clipboard is driven by the "Paste behavior" keys of
# config.yaml, re-read here on each paste (auto_paste: false = clipboard +
# refocus only). Unlike v1 there is no popup window to hide: rofi has
# already exited by the time tab-mode.sh hands over the selection.
set -uo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
PREV_WIN_FILE="$STATE_DIR/paster-prev-win"

source "$PASTER_DIR/bin/lib-config.sh"

selection="$(cat)"
[[ -z "$selection" ]] && exit 0

printf '%s' "$selection" | xclip -selection clipboard

prev_win=""
[[ -r "$PREV_WIN_FILE" ]] && prev_win="$(cat "$PREV_WIN_FILE")"
# No stashed window, or it no longer exists: the text is still on the
# clipboard, so the user can paste manually.
[[ -z "$prev_win" ]] && exit 0
xdotool windowactivate --sync "$prev_win" 2>/dev/null || exit 0

[[ "$PASTER_CFG_AUTO_PASTE" == true ]] || exit 0

# WM_CLASS "general" part via xprop (getwindowclassname is missing on older xdotool)
target_class="$(xprop -id "$prev_win" WM_CLASS 2>/dev/null | awk -F'"' '{print $4}')"
shopt -s nocasematch
if [[ "$target_class" =~ ^(${PASTER_CFG_TERMINAL_CLASSES//./\\.})$ ]]; then
  keystroke="$PASTER_CFG_TERMINAL_PASTE_KEY"
else
  keystroke="$PASTER_CFG_PASTE_KEY"
fi
shopt -u nocasematch

paste_delay() {  # let the focus switch / the paste settle before the next keystroke
  (( PASTER_CFG_PASTE_DELAY_MS > 0 )) || return 0
  sleep "$(printf '%d.%03d' $(( PASTER_CFG_PASTE_DELAY_MS / 1000 )) $(( PASTER_CFG_PASTE_DELAY_MS % 1000 )))"
}

paste_delay
xdotool key --clearmodifiers "$keystroke"

if [[ "$PASTER_CFG_PRESS_ENTER" == true ]]; then
  paste_delay
  xdotool key --clearmodifiers Return
fi
