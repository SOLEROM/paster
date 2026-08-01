#!/usr/bin/env bash
# paster v2 — table-driven checks for bin/lib-hotkey.sh.
# Run: ./tests/test-hotkey.sh   (exit 0 = all green)
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$TESTS_DIR/../bin/lib-hotkey.sh"

pass=0 fail=0

expect() {  # FUNC INPUT EXPECTED
  local got
  got="$("$1" "$2" 2>/dev/null)"
  if [[ "$got" == "$3" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %s %-18q -> %q (want %q)\n' "$1" "$2" "$got" "$3"
  fi
}

expect_fail() {  # FUNC INPUT — conversion must return non-zero
  if "$1" "$2" >/dev/null 2>&1; then
    fail=$((fail + 1))
    printf 'FAIL: %s %-18q unexpectedly succeeded\n' "$1" "$2"
  else
    pass=$((pass + 1))
  fi
}

expect hotkey_to_gtk 'Ctrl+space'      '<Control>space'
expect hotkey_to_gtk 'ctrl+space'      '<Control>space'
expect hotkey_to_gtk 'Mod4+p'          '<Super>p'
expect hotkey_to_gtk 'Super+p'         '<Super>p'
expect hotkey_to_gtk 'Mod1+space'      '<Alt>space'
expect hotkey_to_gtk 'Ctrl+Shift+F5'   '<Control><Shift>F5'
expect hotkey_to_gtk 'Ctrl+Alt+t'      '<Control><Alt>t'
expect hotkey_to_gtk 'F9'              'F9'
expect_fail hotkey_to_gtk '$mod+p'
expect_fail hotkey_to_gtk 'Hyper+p'
expect_fail hotkey_to_gtk ''
expect_fail hotkey_to_gtk 'Ctrl+'

expect hotkey_to_sxhkd 'Ctrl+space'    'ctrl + space'
expect hotkey_to_sxhkd 'Mod4+P'        'super + p'
expect hotkey_to_sxhkd 'Ctrl+Shift+F5' 'ctrl + shift + F5'
expect hotkey_to_sxhkd 'Mod1+space'    'alt + space'
expect hotkey_to_sxhkd 'F9'            'F9'
expect_fail hotkey_to_sxhkd '$mod+p'
expect_fail hotkey_to_sxhkd 'Meta+x'

printf '%d passed, %d failed\n' "$pass" "$fail"
exit "$(( fail > 0 ? 1 : 0 ))"
