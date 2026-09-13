#!/usr/bin/env bash
# paster v3 — table-driven checks for bin/lib-config.sh (paste-behavior keys
# and the validators behind them). Run: ./tests/test-config.sh (exit 0 = green)
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$TESTS_DIR/../bin/lib-config.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

pass=0 fail=0

cfg_var() {  # YAML-CONTENT VARNAME -> value of PASTER_CFG_<VARNAME> after sourcing
  local yaml="$TMP/cfg-$RANDOM.yaml"
  printf '%s\n' "$1" > "$yaml"
  # shellcheck disable=SC1090,SC1091
  ( PASTER_CONFIG_FILE="$yaml"; source "$LIB" 2>/dev/null; eval "printf '%s' \"\$PASTER_CFG_$2\"" )
}

expect() {  # LABEL GOT WANT
  if [[ "$2" == "$3" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %-42s -> %q (want %q)\n' "$1" "$2" "$3"
  fi
}

# ---- validators, called directly
# shellcheck disable=SC1090,SC1091
source "$LIB" 2>/dev/null   # uses the real config.yaml; only the functions matter here
expect '_paster_bool true'        "$(_paster_bool true  false k 2>/dev/null)" true
expect '_paster_bool False'       "$(_paster_bool False true  k 2>/dev/null)" false
expect '_paster_bool yes'         "$(_paster_bool yes   false k 2>/dev/null)" true
expect '_paster_bool no'          "$(_paster_bool no    true  k 2>/dev/null)" false
expect '_paster_bool on'          "$(_paster_bool on    false k 2>/dev/null)" true
expect '_paster_bool OFF'         "$(_paster_bool OFF   true  k 2>/dev/null)" false
expect '_paster_bool 1'           "$(_paster_bool 1     false k 2>/dev/null)" true
expect '_paster_bool 0'           "$(_paster_bool 0     true  k 2>/dev/null)" false
expect '_paster_bool maybe->def'  "$(_paster_bool maybe true  k 2>/dev/null)" true
expect '_paster_bool empty->def'  "$(_paster_bool ''    false k 2>/dev/null)" false
expect '_paster_bool warns'       "$(_paster_bool maybe true k 2>&1 >/dev/null | grep -c 'config k=')" 1

expect '_paster_keystroke ctrl+v'       "$(_paster_keystroke ctrl+v x k 2>/dev/null)" ctrl+v
expect '_paster_keystroke shift+Insert' "$(_paster_keystroke shift+Insert x k 2>/dev/null)" shift+Insert
expect '_paster_keystroke space->def'   "$(_paster_keystroke 'ctrl v' x k 2>/dev/null)" x
expect '_paster_keystroke shell->def'   "$(_paster_keystroke 'ctrl+v; rm' x k 2>/dev/null)" x
expect '_paster_keystroke empty->def'   "$(_paster_keystroke '' x k 2>/dev/null)" x

expect '_paster_classes one'        "$(_paster_classes foo d k 2>/dev/null)" foo
expect '_paster_classes list'       "$(_paster_classes 'foo|bar-baz|org.wez.term' d k 2>/dev/null)" 'foo|bar-baz|org.wez.term'
expect '_paster_classes empty tok'  "$(_paster_classes 'foo||bar' d k 2>/dev/null)" d
expect '_paster_classes trailing|'  "$(_paster_classes 'foo|' d k 2>/dev/null)" d
expect '_paster_classes regex meta' "$(_paster_classes 'foo|(bar' d k 2>/dev/null)" d
expect '_paster_classes space'      "$(_paster_classes 'foo bar' d k 2>/dev/null)" d

# ---- defaults when the keys are absent
expect 'default auto_paste'          "$(cfg_var '' AUTO_PASTE)" true
expect 'default paste_delay_ms'      "$(cfg_var '' PASTE_DELAY_MS)" 150
expect 'default paste_key'           "$(cfg_var '' PASTE_KEY)" ctrl+v
expect 'default terminal_paste_key'  "$(cfg_var '' TERMINAL_PASTE_KEY)" ctrl+shift+v
expect 'default press_enter'         "$(cfg_var '' PRESS_ENTER)" false
expect 'default terminal_classes has alacritty' \
  "$(cfg_var '' TERMINAL_CLASSES | tr '|' '\n' | grep -cx alacritty)" 1
expect 'default terminal_classes has wezterm' \
  "$(cfg_var '' TERMINAL_CLASSES | tr '|' '\n' | grep -cx org.wezfurlong.wezterm)" 1

# ---- keys read from the file
expect 'auto_paste: false'           "$(cfg_var 'auto_paste: false' AUTO_PASTE)" false
expect 'auto_paste: "false" quoted'  "$(cfg_var 'auto_paste: "false"' AUTO_PASTE)" false
expect 'auto_paste: no  # comment'   "$(cfg_var 'auto_paste: no  # comment' AUTO_PASTE)" false
expect 'auto_paste: TRUE'            "$(cfg_var 'auto_paste: TRUE' AUTO_PASTE)" true
expect 'auto_paste: nope -> default' "$(cfg_var 'auto_paste: nope' AUTO_PASTE)" true
expect 'auto_paste: (empty) -> def'  "$(cfg_var 'auto_paste:' AUTO_PASTE)" true
expect 'paste_delay_ms: 0'           "$(cfg_var 'paste_delay_ms: 0' PASTE_DELAY_MS)" 0
expect 'paste_delay_ms: 5000'        "$(cfg_var 'paste_delay_ms: 5000' PASTE_DELAY_MS)" 5000
expect 'paste_delay_ms: 5001 -> def' "$(cfg_var 'paste_delay_ms: 5001' PASTE_DELAY_MS)" 150
expect 'paste_delay_ms: -1 -> def'   "$(cfg_var 'paste_delay_ms: -1' PASTE_DELAY_MS)" 150
expect 'paste_delay_ms: fast -> def' "$(cfg_var 'paste_delay_ms: fast' PASTE_DELAY_MS)" 150
expect 'paste_key custom'            "$(cfg_var 'paste_key: ctrl+shift+Insert' PASTE_KEY)" ctrl+shift+Insert
expect 'paste_key quoted'            "$(cfg_var "paste_key: 'shift+Insert'" PASTE_KEY)" shift+Insert
expect 'paste_key bad -> default'    "$(cfg_var 'paste_key: ctrl v' PASTE_KEY)" ctrl+v
expect 'terminal_paste_key custom'   "$(cfg_var 'terminal_paste_key: shift+Insert' TERMINAL_PASTE_KEY)" shift+Insert
expect 'terminal_classes custom'     "$(cfg_var 'terminal_classes: "foo|bar"' TERMINAL_CLASSES)" 'foo|bar'
expect 'terminal_classes unquoted'   "$(cfg_var 'terminal_classes: foo|bar # c' TERMINAL_CLASSES)" 'foo|bar'
expect 'terminal_classes bad -> def has alacritty' \
  "$(cfg_var 'terminal_classes: "foo|(bar"' TERMINAL_CLASSES | tr '|' '\n' | grep -cx alacritty)" 1
expect 'press_enter: true'           "$(cfg_var 'press_enter: true' PRESS_ENTER)" true
expect 'press_enter: 1'              "$(cfg_var 'press_enter: 1' PRESS_ENTER)" true

# ---- existing keys unaffected (regression guard)
expect 'width_pct: 50 still parsed'  "$(cfg_var 'width_pct: 50' WIDTH_PCT)" 50
expect 'opacity_pct: 200 -> default' "$(cfg_var 'opacity_pct: 200' OPACITY_PCT)" 85
expect 'background quoted'           "$(cfg_var 'background: "#000000"' BACKGROUND)" '#000000'

printf '%d passed, %d failed\n' "$pass" "$fail"
exit "$(( fail > 0 ? 1 : 0 ))"
