#!/usr/bin/env bash
# paster v3 — config.yaml reader. Source this file: it loads validated
# PASTER_CFG_* variables from <paster root>/config.yaml (flat "key: value"
# YAML only; quotes optional, trailing "# comments" allowed). Invalid or
# missing values fall back to the built-in defaults with a warning.
# Sourced by toggle.sh and install.sh (look/size/hotkey keys) and by
# paste-back.sh (paste-behavior keys, re-read on every paste).

_PASTER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTER_CONFIG_FILE="${PASTER_CONFIG_FILE:-$_PASTER_LIB_DIR/../config.yaml}"

paster_cfg() {  # paster_cfg KEY DEFAULT -> raw value (or DEFAULT if absent/empty)
  local key="$1" def="$2" raw val
  raw="$(sed -n "s/^${key}:[[:space:]]*//p" "$PASTER_CONFIG_FILE" 2>/dev/null | head -n1)"
  if [[ "$raw" =~ ^\"([^\"]*)\" ]]; then
    val="${BASH_REMATCH[1]}"
  elif [[ "$raw" =~ ^\'([^\']*)\' ]]; then
    val="${BASH_REMATCH[1]}"
  else
    val="${raw%%[[:space:]]#*}"                 # strip trailing " # comment"
    val="${val%"${val##*[![:space:]]}"}"        # rtrim
  fi
  if [[ -n "$val" ]]; then printf '%s' "$val"; else printf '%s' "$def"; fi
}

_paster_int() {  # VALUE MIN MAX DEFAULT KEY -> VALUE if an int in range, else DEFAULT
  local v="$1" min="$2" max="$3" def="$4" key="$5"
  if [[ "$v" =~ ^[0-9]+$ ]] && (( v >= min && v <= max )); then
    printf '%s' "$v"
  else
    printf 'paster: config %s=%q invalid (want integer %s-%s) — using %s\n' \
      "$key" "$v" "$min" "$max" "$def" >&2
    printf '%s' "$def"
  fi
}

_paster_color() {  # VALUE DEFAULT KEY -> VALUE if "#rrggbb", else DEFAULT
  local v="$1" def="$2" key="$3"
  if [[ "$v" =~ ^#[0-9a-fA-F]{6}$ ]]; then
    printf '%s' "$v"
  else
    printf 'paster: config %s=%q invalid (want "#rrggbb") — using %s\n' \
      "$key" "$v" "$def" >&2
    printf '%s' "$def"
  fi
}

_paster_bool() {  # VALUE DEFAULT KEY -> "true"/"false" (accepts yes/no, on/off, 1/0, any case), else DEFAULT
  local v="${1,,}" def="$2" key="$3"
  case "$v" in
    true|yes|on|1)  printf 'true' ;;
    false|no|off|0) printf 'false' ;;
    *)
      printf 'paster: config %s=%q invalid (want true/false) — using %s\n' \
        "$key" "$1" "$def" >&2
      printf '%s' "$def" ;;
  esac
}

_paster_keystroke() {  # VALUE DEFAULT KEY -> VALUE if xdotool key syntax ("ctrl+shift+v"), else DEFAULT
  local v="$1" def="$2" key="$3"
  if [[ "$v" =~ ^[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*$ ]]; then
    printf '%s' "$v"
  else
    printf 'paster: config %s=%q invalid (want xdotool key syntax, e.g. ctrl+shift+v) — using %s\n' \
      "$key" "$v" "$def" >&2
    printf '%s' "$def"
  fi
}

_paster_classes() {  # VALUE DEFAULT KEY -> VALUE if "name|name|…" (WM_CLASS names), else DEFAULT
  local v="$1" def="$2" key="$3"
  if [[ "$v" =~ ^[A-Za-z0-9_.-]+(\|[A-Za-z0-9_.-]+)*$ ]]; then
    printf '%s' "$v"
  else
    printf 'paster: config %s=%q invalid (want WM_CLASS names separated by "|") — using default list\n' \
      "$key" "$v" >&2
    printf '%s' "$def"
  fi
}

# ---- look / size / hotkey (toggle.sh, install.sh)
PASTER_CFG_HOTKEY="$(paster_cfg hotkey '')"
PASTER_CFG_WIDTH_PCT="$(_paster_int "$(paster_cfg width_pct 100)" 20 100 100 width_pct)"
PASTER_CFG_HEIGHT_PCT="$(_paster_int "$(paster_cfg height_pct 40)" 10 100 40 height_pct)"
PASTER_CFG_OPACITY_PCT="$(_paster_int "$(paster_cfg opacity_pct 85)" 10 100 85 opacity_pct)"
PASTER_CFG_FONT_SIZE="$(_paster_int "$(paster_cfg font_size 12)" 6 72 12 font_size)"
PASTER_CFG_BORDER_PX="$(_paster_int "$(paster_cfg border_px 1)" 0 20 1 border_px)"
PASTER_CFG_BACKGROUND="$(_paster_color "$(paster_cfg background '#10141a')" '#10141a' background)"
PASTER_CFG_FOREGROUND="$(_paster_color "$(paster_cfg foreground '#d8dee9')" '#d8dee9' foreground)"

# ---- paste behavior (paste-back.sh). WM_CLASS names (case-insensitive)
# that get terminal_paste_key instead of paste_key; the default list is the
# one v3 shipped hardcoded in paste-back.sh.
PASTER_DEFAULT_TERMINAL_CLASSES='alacritty|kitty|urxvt|rxvt|xterm|st|st-256color|gnome-terminal|gnome-terminal-server|xfce4-terminal|konsole|terminator|tilix|termite|guake|lxterminal|sakura|qterminal|eterm|wezterm|org.wezfurlong.wezterm'
PASTER_CFG_AUTO_PASTE="$(_paster_bool "$(paster_cfg auto_paste true)" true auto_paste)"
PASTER_CFG_PASTE_DELAY_MS="$(_paster_int "$(paster_cfg paste_delay_ms 150)" 0 5000 150 paste_delay_ms)"
PASTER_CFG_PASTE_KEY="$(_paster_keystroke "$(paster_cfg paste_key 'ctrl+v')" 'ctrl+v' paste_key)"
PASTER_CFG_TERMINAL_PASTE_KEY="$(_paster_keystroke "$(paster_cfg terminal_paste_key 'ctrl+shift+v')" 'ctrl+shift+v' terminal_paste_key)"
PASTER_CFG_TERMINAL_CLASSES="$(_paster_classes "$(paster_cfg terminal_classes "$PASTER_DEFAULT_TERMINAL_CLASSES")" "$PASTER_DEFAULT_TERMINAL_CLASSES" terminal_classes)"
PASTER_CFG_PRESS_ENTER="$(_paster_bool "$(paster_cfg press_enter false)" false press_enter)"
