#!/usr/bin/env bash
# paster v3 — rofi script-mode backend; one instance of this script per tab.
# rofi invokes it as:  tab-mode.sh <entries-subdir> <tab-label> [selection]
# with ROFI_RETV saying why:
#   0 = initial call: print the tab's entries (one per line)
#   1 = an entry was selected (also reached when picked via the ALL/combi tab,
#       which dispatches the selection back to the owning tab's script)
#   2 = custom text with no match — ignored, same as v1 (nothing is pasted)
set -uo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAB_DIR="${1:?usage: tab-mode.sh <entries-subdir> <tab-label> [selection]}"
TAB_LABEL="${2:?missing tab label}"
SELECTION="${3:-}"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
LAST_TAB_FILE="$STATE_DIR/paster-last-tab"

case "${ROFI_RETV:-0}" in
  0)
    # Non-empty lines of this tab's content.md. Missing/empty file -> no
    # rows for this tab; rofi shows it as an empty list.
    awk 'NF' "$TAB_DIR/content.md" 2>/dev/null
    ;;
  1)
    [[ -z "$SELECTION" ]] && exit 0
    printf '%s\n' "$TAB_LABEL" > "$LAST_TAB_FILE"
    # Printing nothing below makes rofi quit — but paste-back must not run
    # until rofi has actually exited and released its keyboard grab, or the
    # injected paste keystroke would be swallowed. Detach fully (setsid,
    # all fds closed — rofi reads our stdout to EOF) and wait for the rofi
    # process to disappear before delivering the selection.
    setsid -f bash -c '
      for _ in $(seq 1 40); do
        pgrep -f "rofi .*/paster\.rasi" >/dev/null 2>&1 || break
        sleep 0.05
      done
      printf "%s" "$1" | "$2"
    ' _ "$SELECTION" "$PASTER_DIR/bin/paste-back.sh" >/dev/null 2>&1 </dev/null
    ;;
esac
