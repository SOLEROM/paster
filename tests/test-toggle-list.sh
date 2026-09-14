#!/usr/bin/env bash
# paster v3 — checks for `bin/toggle.sh --list-tabs`, the dry-run the control
# plane asks for the tab labels rofi would show (plan: pasterFrontPlan.md D4).
# Prints "label<TAB>dir" per tab and exits before any X11 work.
# Run: ./tests/test-toggle-list.sh (exit 0 = green)
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOGGLE="$TESTS_DIR/../bin/toggle.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

pass=0 fail=0
expect() {  # LABEL GOT WANT
  if [[ "$2" == "$3" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %-44s -> %q (want %q)\n' "$1" "$2" "$3"
  fi
}

mk() {  # ENTRIES-DIR FOLDER [with-content]  -> creates the tab folder
  mkdir -p "$1/$2"
  [[ "${3:-yes}" == "yes" ]] && printf 'one\n' > "$1/$2/content.md"
}

list() {  # ENTRIES-DIR -> stdout of --list-tabs (labels only, joined by |)
  PASTER_ENTRIES_DIR="$1" bash "$TOGGLE" --list-tabs 2>/dev/null | cut -f1 | paste -sd'|'
}

# ---- prefix stripping, ordering, ignored folders
E="$TMP/e1"; mk "$E" 20_Writing; mk "$E" 10_Coding; mk "$E" 30_General; mk "$E" 40_Empty no; mk "$E" Misc
expect 'order by folder name, NN_ stripped' "$(list "$E")" 'Coding|Writing|General|Misc'

# ---- rofi-unsafe characters are dropped from the label
E="$TMP/e2"; mk "$E" "10_A,B:C'D\"E"
expect 'drops , : quote chars' "$(list "$E")" 'ABCDE'

# ---- collisions get a numeric suffix, no tab disappears
E="$TMP/e3"; mk "$E" 10_Coding; mk "$E" 20_Coding; mk "$E" 30_Coding
expect 'collisions suffixed' "$(list "$E")" 'Coding|Coding 2|Coding 3'

# ---- a label that empties out is skipped (toggle.sh has nothing to show for it)
E="$TMP/e4"; mk "$E" '10_,,'; mk "$E" 20_Ok
expect 'empty label skipped' "$(list "$E")" 'Ok'

# ---- the dir column is the absolute folder path
E="$TMP/e5"; mk "$E" 10_Coding
got="$(PASTER_ENTRIES_DIR="$E" bash "$TOGGLE" --list-tabs 2>/dev/null | cut -f2)"
expect 'dir column' "$got" "$E/10_Coding"

# ---- no tabs: empty output, exit 0 (an empty list is an answer, not an error)
E="$TMP/e6"; mkdir -p "$E"
out="$(PASTER_ENTRIES_DIR="$E" bash "$TOGGLE" --list-tabs 2>/dev/null)"; rc=$?
expect 'no tabs -> empty' "$out" ''
expect 'no tabs -> exit 0' "$rc" 0

# ---- a missing entries dir behaves the same
out="$(PASTER_ENTRIES_DIR="$TMP/nope" bash "$TOGGLE" --list-tabs 2>/dev/null)"; rc=$?
expect 'missing dir -> empty, exit 0' "$out/$rc" '/0'

# ---- --list-tabs never touches X: stub rofi/xdotool/pkill that record any
# call, run with no DISPLAY, and expect the labels with no stub ever hit.
E="$TMP/e7"; mk "$E" 10_Coding
mkdir -p "$TMP/stub"
for b in rofi xdotool pkill; do
  printf '#!/usr/bin/env bash\ntouch "%s/x-touched"; exit 1\n' "$TMP" > "$TMP/stub/$b"
  chmod +x "$TMP/stub/$b"
done
out="$(env -u DISPLAY PATH="$TMP/stub:$PATH" PASTER_ENTRIES_DIR="$E" bash "$TOGGLE" --list-tabs 2>/dev/null | cut -f1)"
expect 'works without DISPLAY' "$out" 'Coding'
expect 'no X binary was called' "$([[ -e "$TMP/x-touched" ]] && echo touched || echo clean)" 'clean'

printf '%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
