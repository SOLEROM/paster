#!/usr/bin/env bash
# paster v1 — runs inside the Paster alacritty window.
# Tabbed fzf loop over entries/<Tab>/content.md, modeled on the taskStack
# demo1.sh navigator: a top nav bar lists every tab with the current one
# highlighted; left/right (or ctrl-h/ctrl-l) switch tabs; ctrl-a toggles a
# global search where typing filters the lines of ALL tabs at once.
# The loop never exits, so re-showing the scratchpad window is instant.
set -uo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRIES_DIR="$PASTER_DIR/entries"

FZF_COLOR='dark,fg:251,bg:235,hl:39,fg+:255,bg+:237,hl+:81,info:144,prompt:33,spinner:143'
NAV_KEYS='ctrl-a,left,right,ctrl-h,ctrl-l'

hide() { i3-msg -q '[class="Paster"] move scratchpad' >/dev/null 2>&1; }

# Tab label = folder basename, minus an optional NN_ ordering prefix
# (entries/10_Coding -> "Coding").
tab_label() {
  local b
  b="$(basename "$1")"
  [[ "$b" =~ ^[0-9]+_ ]] && b="${b#*_}"
  printf '%s' "$b"
}

tab_idx=0   # current tab
global=0    # 0 = current tab only, 1 = search across all tabs
query=""    # filter text, preserved across tab switches

while true; do
  # Tabs = subfolders of entries/ containing a content.md, sorted by name.
  # Rescanned every cycle so new folders/edits show up without a restart.
  tabs=()
  while IFS= read -r d; do
    [[ -f "$d/content.md" ]] && tabs+=("$d")
  done < <(find "$ENTRIES_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

  n=${#tabs[@]}
  if (( n == 0 )); then
    printf 'paster: no tabs found.\nCreate entries/<TabName>/content.md under:\n  %s\n' "$ENTRIES_DIR" >&2
    sleep 2
    continue
  fi
  (( tab_idx >= n )) && tab_idx=0

  labels=()
  for d in "${tabs[@]}"; do labels+=("$(tab_label "$d")"); done

  # Nav bar:  ← tab1 [CURRENT] tab3 →   (blue tabs, bold-red current)
  E=$'\033'
  hdr="  ${E}[34m←${E}[0m"
  for (( j=0; j<n; j++ )); do
    if (( j == tab_idx )); then
      hdr+=" ${E}[1;31m[${labels[j]}]${E}[0m"
    else
      hdr+=" ${E}[34m${labels[j]}${E}[0m"
    fi
  done
  hdr+="  ${E}[34m→${E}[0m  ${E}[90m(ctrl-a: all tabs)${E}[0m"

  if (( global == 1 )); then
    # Global search: every line of every tab, prefixed with its tab label.
    out="$(
      for (( j=0; j<n; j++ )); do
        awk -v tab="${labels[j]}" 'NF { print "[" tab "]  " $0 }' "${tabs[j]}/content.md"
      done | fzf --ansi --layout=reverse --no-multi --cycle --no-info \
          --query="$query" --print-query \
          --prompt=' ALL ❯ ' --header="$hdr" --color="$FZF_COLOR" \
          --expect="$NAV_KEYS"
    )"
  else
    out="$(
      awk 'NF' "${tabs[tab_idx]}/content.md" | \
      fzf --ansi --layout=reverse --no-multi --cycle --no-info \
          --query="$query" --print-query \
          --prompt=" ${labels[tab_idx]} ❯ " --header="$hdr" --color="$FZF_COLOR" \
          --expect="$NAV_KEYS"
    )"
  fi
  st=$?

  # --print-query + --expect output: line1=query line2=key line3=selection
  query="$(printf '%s' "$out" | sed -n '1p')"
  key="$(printf '%s' "$out" | sed -n '2p')"
  sel="$(printf '%s' "$out" | sed -n '3p')"

  case "$key" in
    ctrl-a)       global=$(( 1 - global )); continue ;;
    left|ctrl-h)  global=0; tab_idx=$(( (tab_idx - 1 + n) % n )); continue ;;
    right|ctrl-l) global=0; tab_idx=$(( (tab_idx + 1) % n )); continue ;;
  esac

  if (( st != 0 )) || [[ -z "$sel" ]]; then
    # Esc / Ctrl-C — hide without pasting; fresh filter on next toggle.
    query=""
    hide
    continue
  fi

  # Global items carry a "[Tab]  " prefix — strip it before pasting.
  if (( global == 1 )); then
    sel="$(printf '%s' "$sel" | sed 's/^\[[^]]*\]  *//')"
  fi

  query=""
  printf '%s' "$sel" | "$PASTER_DIR/bin/paste-back.sh"
done
