#!/usr/bin/env bash
# paster v3 — behavior checks for bin/paste-back.sh against stubbed X tools.
# Stub xclip/xdotool/xprop/sleep are put first on PATH and append every call
# to a log; each case runs paste-back.sh with its own config.yaml and
# prev-window file, then compares the log. Run: ./tests/test-paste-back.sh
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTE_BACK="$TESTS_DIR/../bin/paste-back.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STUBS="$TMP/stubs"; RUN="$TMP/run"; LOG="$TMP/calls.log"
mkdir -p "$STUBS" "$RUN"

# ---- stubs: log args; xclip also captures stdin; xprop answers with the
# class from $STUB_WM_CLASS; windowactivate fails when $STUB_ACTIVATE_FAIL set.
cat > "$STUBS/xclip" <<'S'
#!/usr/bin/env bash
printf 'xclip %s\n' "$*" >> "$STUB_LOG"; cat > "$STUB_CLIP"
S
cat > "$STUBS/xdotool" <<'S'
#!/usr/bin/env bash
printf 'xdotool %s\n' "$*" >> "$STUB_LOG"
[[ "$1" == windowactivate && -n "${STUB_ACTIVATE_FAIL:-}" ]] && exit 1
exit 0
S
cat > "$STUBS/xprop" <<'S'
#!/usr/bin/env bash
printf 'xprop %s\n' "$*" >> "$STUB_LOG"
printf 'WM_CLASS(STRING) = "instance", "%s"\n' "${STUB_WM_CLASS:-firefox}"
S
cat > "$STUBS/sleep" <<'S'
#!/usr/bin/env bash
printf 'sleep %s\n' "$*" >> "$STUB_LOG"
S
chmod +x "$STUBS"/*

pass=0 fail=0

run_case() {  # WM_CLASS CONFIG-YAML [PREV_WIN|"-"] [ACTIVATE_FAIL] -> runs paste-back on "hello world"
  local wm_class="$1" yaml="$2" prev="${3:-123}" afail="${4:-}"
  : > "$LOG"; : > "$TMP/clip.txt"
  printf '%s\n' "$yaml" > "$TMP/config.yaml"
  if [[ "$prev" == "-" ]]; then rm -f "$RUN/paster-prev-win"; else printf '%s\n' "$prev" > "$RUN/paster-prev-win"; fi
  printf '%s' "${INPUT-hello world}" | env PATH="$STUBS:$PATH" \
      XDG_RUNTIME_DIR="$RUN" PASTER_CONFIG_FILE="$TMP/config.yaml" \
      STUB_LOG="$LOG" STUB_CLIP="$TMP/clip.txt" STUB_WM_CLASS="$wm_class" \
      STUB_ACTIVATE_FAIL="$afail" \
      bash "$PASTE_BACK" 2>/dev/null
  RC=$?
}

expect_log() {  # LABEL EXPECTED-LOG (multi-line)
  local got; got="$(cat "$LOG")"
  if [[ "$got" == "$2" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %s\n--- got ---\n%s\n--- want ---\n%s\n-----------\n' "$1" "$got" "$2"
  fi
}
expect_eq() {  # LABEL GOT WANT
  if [[ "$2" == "$3" ]]; then pass=$((pass + 1)); else
    fail=$((fail + 1)); printf 'FAIL: %s -> %q (want %q)\n' "$1" "$2" "$3"; fi
}

# 1. defaults, ordinary window: clipboard, refocus, delay, ctrl+v
run_case firefox ''
expect_log 'defaults / ordinary window' \
'xclip -selection clipboard
xdotool windowactivate --sync 123
xprop -id 123 WM_CLASS
sleep 0.150
xdotool key --clearmodifiers ctrl+v'
expect_eq 'clipboard got the text' "$(cat "$TMP/clip.txt")" 'hello world'
expect_eq 'exit code' "$RC" 0

# 2. terminal window (case-insensitive class match) -> ctrl+shift+v
run_case Alacritty ''
expect_eq 'Alacritty -> ctrl+shift+v' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+shift+v'
run_case org.wezfurlong.wezterm ''
expect_eq 'wezterm (dotted class) -> ctrl+shift+v' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+shift+v'
run_case xtermish ''
expect_eq 'partial class name does not match' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+v'

# 3. auto_paste: false -> clipboard + refocus only
run_case firefox 'auto_paste: false'
expect_log 'auto_paste: false' \
'xclip -selection clipboard
xdotool windowactivate --sync 123'
expect_eq 'auto_paste: false still copies' "$(cat "$TMP/clip.txt")" 'hello world'

# 4. delay from config (0 = no sleep at all)
run_case firefox 'paste_delay_ms: 1250'
expect_eq 'paste_delay_ms: 1250 -> sleep 1.250' "$(grep -c '^sleep 1.250$' "$LOG")" 1
run_case firefox 'paste_delay_ms: 0'
expect_eq 'paste_delay_ms: 0 -> no sleep' "$(grep -c '^sleep' "$LOG")" 0
expect_eq 'paste_delay_ms: 0 still pastes' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+v'

# 5. custom keystrokes
run_case firefox $'paste_key: ctrl+shift+Insert\nterminal_paste_key: shift+Insert'
expect_eq 'custom paste_key' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+shift+Insert'
run_case xterm $'paste_key: ctrl+shift+Insert\nterminal_paste_key: shift+Insert'
expect_eq 'custom terminal_paste_key' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers shift+Insert'

# 6. custom terminal_classes replaces the default list
run_case firefox 'terminal_classes: "firefox|foo"'
expect_eq 'custom classes: firefox is now a terminal' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+shift+v'
run_case alacritty 'terminal_classes: "firefox|foo"'
expect_eq 'custom classes: alacritty no longer is' "$(tail -n1 "$LOG")" 'xdotool key --clearmodifiers ctrl+v'

# 7. press_enter
run_case firefox 'press_enter: true'
expect_log 'press_enter: true' \
'xclip -selection clipboard
xdotool windowactivate --sync 123
xprop -id 123 WM_CLASS
sleep 0.150
xdotool key --clearmodifiers ctrl+v
sleep 0.150
xdotool key --clearmodifiers Return'
run_case firefox $'press_enter: true\nauto_paste: false'
expect_eq 'press_enter needs auto_paste' "$(grep -c 'Return' "$LOG")" 0

# 8. no previous window / refocus failure / empty input -> clipboard only, exit 0
run_case firefox '' -
expect_log 'no prev window -> clipboard only' 'xclip -selection clipboard'
expect_eq 'no prev window exit 0' "$RC" 0
run_case firefox '' 123 1
expect_log 'windowactivate fails -> no keystroke' \
'xclip -selection clipboard
xdotool windowactivate --sync 123'
expect_eq 'windowactivate fails exit 0' "$RC" 0
INPUT='' run_case firefox ''
expect_log 'empty input -> nothing' ''
expect_eq 'empty input exit 0' "$RC" 0

printf '%d passed, %d failed\n' "$pass" "$fail"
exit "$(( fail > 0 ? 1 : 0 ))"
