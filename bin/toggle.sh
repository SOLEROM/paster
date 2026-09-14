#!/usr/bin/env bash
# paster v3 — hotkey entry point.
# Captures the focused window (so paste-back.sh can restore focus and paste
# there), assembles one rofi script-mode per entries/ tab plus a combi "ALL"
# tab, renders the theme from config.yaml, and launches rofi.
#
#   toggle.sh              the hotkey target: show (or hide) the popup
#   toggle.sh --list-tabs  dry run for the control plane: print one
#                          "label<TAB>dir" line per tab exactly as rofi
#                          would label it, then exit — no X11, no rofi.
# PASTER_ENTRIES_DIR overrides the entries folder (tests, the front).
#
# Toggle-hide: while the popup is open rofi holds the keyboard grab, so the
# i3 binding can't fire — the same hotkey is therefore also wired as
# kb-cancel *inside* rofi. The pkill below only covers rare grab-less races.
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRIES_DIR="${PASTER_ENTRIES_DIR:-$PASTER_DIR/entries}"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}"
PREV_WIN_FILE="$STATE_DIR/paster-prev-win"
LAST_TAB_FILE="$STATE_DIR/paster-last-tab"
RASI_FILE="$STATE_DIR/paster.rasi"

source "$PASTER_DIR/bin/lib-config.sh"

# ---- tabs: subfolders of entries/ containing a content.md, sorted by name.
# Rescanned every toggle so new folders/edits show up without a reload.
# Label = folder basename minus an optional NN_ ordering prefix; characters
# that clash with rofi's -modi syntax are dropped, and labels colliding
# after that get a numeric suffix so no tab silently disappears.
scan_tabs() {  # fills labels[] and dirs[] (defined above, before the X work)
  labels=() dirs=()
  local -A seen=()
  local d b
  while IFS= read -r d; do
    [[ -f "$d/content.md" ]] || continue
    b="$(basename "$d")"
    [[ "$b" =~ ^[0-9]+_ ]] && b="${b#*_}"
    b="${b//[,:\'\"]/}"
    [[ -z "$b" ]] && continue
    if [[ -n "${seen[$b]:-}" ]]; then
      seen[$b]=$(( seen[$b] + 1 ))
      b="$b ${seen[$b]}"
    fi
    seen[$b]=1
    labels+=("$b") dirs+=("$d")
  done < <(find "$ENTRIES_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
}
# Dry run for the control plane (D4 of plans/pasterFrontPlan.md): the same
# scan the popup does, printed instead of shown. Handled before the pkill,
# the focus capture and rofi, so it needs no display at all. An empty
# entries folder prints nothing and exits 0 — an empty list is an answer.
labels=() dirs=()
if [[ "${1:-}" == "--list-tabs" ]]; then
  scan_tabs
  for i in "${!labels[@]}"; do printf '%s\t%s\n' "${labels[i]}" "${dirs[i]}"; done
  exit 0
fi

if pkill -f 'rofi .*/paster\.rasi' 2>/dev/null; then
  exit 0  # popup was open (grab-less edge case) — hotkey means hide
fi

# About to show the menu: remember where the user was.
active_win="$(xdotool getactivewindow 2>/dev/null || true)"
[[ -n "$active_win" ]] && printf '%s\n' "$active_win" > "$PREV_WIN_FILE"

# Single quotes in paths/labels are escaped for rofi's shell-style parsing
# of -modi command specs ('…' -> '…'\''…').
sq_escape() { printf '%s' "${1//\'/\'\\\'\'}"; }

# ---- tabs (scanned by scan_tabs, defined above)
scan_tabs

if (( ${#labels[@]} == 0 )); then
  rofi -e "paster: no tabs found — create entries/<TabName>/content.md under $ENTRIES_DIR" \
    2>/dev/null || echo "paster: no tabs found under $ENTRIES_DIR" >&2
  exit 1
fi

# ---- rofi mode list: "ALL" (combi over every tab) first, then one script
# mode per tab. Mode command args are single-quoted; rofi parses them
# shell-style before appending the selected entry as the last argument.
modi='combi' combi_modi=''
for i in "${!labels[@]}"; do
  modi+=",${labels[i]}:'$(sq_escape "$PASTER_DIR/bin/tab-mode.sh")' '$(sq_escape "${dirs[i]}")' '${labels[i]}'"
  combi_modi+="${combi_modi:+,}${labels[i]}"
done

# Reopen on the tab of the last pick (falls back to the first tab).
show_mode="${labels[0]}"
if [[ -r "$LAST_TAB_FILE" ]]; then
  last="$(head -n1 "$LAST_TAB_FILE")"
  for l in "${labels[@]}"; do [[ "$l" == "$last" ]] && show_mode="$last" && break; done
fi

# ---- theme: rendered from config.yaml on every toggle, so look/size edits
# apply on the next popup without re-running install.sh.
r=$((16#${PASTER_CFG_BACKGROUND:1:2}))
g=$((16#${PASTER_CFG_BACKGROUND:3:2}))
b=$((16#${PASTER_CFG_BACKGROUND:5:2}))
sed -e "s/__WIDTH__/$PASTER_CFG_WIDTH_PCT/g" \
    -e "s/__HEIGHT__/$PASTER_CFG_HEIGHT_PCT/g" \
    -e "s/__BORDER__/$PASTER_CFG_BORDER_PX/g" \
    -e "s/__FONT_SIZE__/$PASTER_CFG_FONT_SIZE/g" \
    -e "s/__FG__/$PASTER_CFG_FOREGROUND/g" \
    -e "s/__BG_RGBA__/rgba ( $r, $g, $b, $PASTER_CFG_OPACITY_PCT % )/g" \
    "$PASTER_DIR/config/paster.rasi.tmpl" > "$RASI_FILE"

# ---- keybindings.
# Plain arrows switch tabs (v1 muscle memory, per plan4 Q1); the query
# cursor stays reachable on Control+b/f. Control+h/l are freed from their
# rofi defaults (remove-char-back / mode-complete) to also switch tabs.
declare -A kb=(
  [kb-move-char-back]='Control+b'
  [kb-move-char-forward]='Control+f'
  [kb-remove-char-back]='BackSpace,Shift+BackSpace'
  [kb-mode-complete]=''
  [kb-mode-next]='Right,Control+l,Shift+Right,Control+Tab'
  [kb-mode-previous]='Left,Control+h,Shift+Left,Control+ISO_Left_Tab'
  [kb-cancel]='Escape,Control+g,Control+bracketleft'
)

strip_combo() {  # LIST COMBO -> comma list minus that combo
  local IFS=',' t out=()
  for t in $1; do [[ "$t" == "$2" ]] || out+=("$t"); done
  (IFS=','; printf '%s' "${out[*]-}")
}

# Hotkey-as-cancel: translate the i3 bindsym combo to rofi's syntax so
# pressing the hotkey again closes the popup (i3 can't see it during the
# grab). rofi refuses to start when two actions share a binding, so the
# combo is first stripped from every action that holds it — both our own
# overrides and rofi's defaults (queried via -dump-config, e.g. Ctrl+space
# is kb-row-select by default). Untranslatable syntax is skipped — Escape
# always works.
hk="$PASTER_CFG_HOTKEY"
if [[ -z "$hk" ]]; then  # same defaulting as install.sh
  [[ -d "$HOME/.config/regolith3/i3/config.d" ]] && hk='$mod+p' || hk='Mod1+p'
fi
hk="${hk//\$mod/Super}"; hk="${hk//Mod4/Super}"; hk="${hk//Mod1/Alt}"; hk="${hk//Ctrl/Control}"
if [[ "$hk" =~ ^[A-Za-z0-9_+]+$ ]]; then
  for action in "${!kb[@]}"; do
    kb[$action]="$(strip_combo "${kb[$action]}" "$hk")"
  done
  while IFS= read -r line; do
    action="${line%%:*}"
    bindings="${line#*: \"}"; bindings="${bindings%\"}"
    [[ -v "kb[$action]" ]] && continue  # ours already handled above
    stripped="$(strip_combo "$bindings" "$hk")"
    [[ "$stripped" != "$bindings" ]] && kb[$action]="$stripped"
  done < <(rofi -no-config -dump-config 2>/dev/null \
             | grep -oE 'kb-[a-z0-9-]+: "[^"]*"' || true)
  kb[kb-cancel]+=",$hk"
fi

kb_args=()
for action in "${!kb[@]}"; do kb_args+=("-$action" "${kb[$action]}"); done

exec rofi \
  -no-config \
  -show "$show_mode" \
  -modi "$modi" \
  -combi-modi "$combi_modi" \
  -display-combi 'ALL' \
  -combi-display-format '[{mode}]  {text}' \
  -matching fuzzy -sort -sorting-method fzf \
  -sidebar-mode \
  -monitor -4 \
  -theme "$RASI_FILE" \
  "${kb_args[@]}"
