#!/usr/bin/env bash
# paster v2 — config.yaml reader. Source this file: it loads validated
# PASTER_CFG_* variables from <paster root>/config.yaml (flat "key: value"
# YAML only; quotes optional, trailing "# comments" allowed). Invalid or
# missing values fall back to the built-in defaults with a warning.

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

PASTER_CFG_HOTKEY="$(paster_cfg hotkey '')"
PASTER_CFG_WIDTH_PCT="$(_paster_int "$(paster_cfg width_pct 100)" 20 100 100 width_pct)"
PASTER_CFG_HEIGHT_PCT="$(_paster_int "$(paster_cfg height_pct 40)" 10 100 40 height_pct)"
PASTER_CFG_OPACITY_PCT="$(_paster_int "$(paster_cfg opacity_pct 85)" 10 100 85 opacity_pct)"
PASTER_CFG_FONT_SIZE="$(_paster_int "$(paster_cfg font_size 12)" 6 72 12 font_size)"
PASTER_CFG_BORDER_PX="$(_paster_int "$(paster_cfg border_px 1)" 0 20 1 border_px)"
PASTER_CFG_BACKGROUND="$(_paster_color "$(paster_cfg background '#10141a')" '#10141a' background)"
PASTER_CFG_FOREGROUND="$(_paster_color "$(paster_cfg foreground '#d8dee9')" '#d8dee9' foreground)"
