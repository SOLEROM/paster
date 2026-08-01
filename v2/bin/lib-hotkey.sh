#!/usr/bin/env bash
# paster v2 — hotkey format conversion. config.yaml stores one canonical
# i3-style hotkey ("Ctrl+space", "Mod4+p", "Ctrl+Shift+F5"); the installer
# converts it to whatever the target desktop expects. Each converter prints
# the converted value, or prints the reason to stderr and returns 1 when the
# key cannot be translated ($mod is i3-only, unknown modifier names).

_hotkey_err() { printf 'paster: hotkey %s\n' "$*" >&2; }

_hotkey_is_mod() {  # true if $1 is a modifier name, not a key symbol
  case "${1,,}" in
    ctrl|control|shift|alt|mod1|super|mod4|win|'$mod') return 0 ;;
    *) return 1 ;;
  esac
}

hotkey_to_gtk() {  # "Ctrl+space" -> "<Control>space" (gsettings/dconf/xfconf)
  local key="${1:-}" out="" sym part
  [[ -z "$key" ]] && { _hotkey_err "is empty"; return 1; }
  local -a parts=()
  IFS='+' read -ra parts <<< "$key"
  local n=${#parts[@]}
  (( n == 0 )) && { _hotkey_err "'$key' has no key symbol"; return 1; }
  sym="${parts[n-1]}"
  if [[ -z "$sym" ]] || _hotkey_is_mod "$sym"; then
    _hotkey_err "'$key' has no key symbol"; return 1
  fi
  local i
  for (( i = 0; i < n - 1; i++ )); do
    part="${parts[i],,}"
    case "$part" in
      ctrl|control)   out+="<Control>" ;;
      shift)          out+="<Shift>" ;;
      alt|mod1)       out+="<Alt>" ;;
      super|mod4|win) out+="<Super>" ;;
      '$mod')
        _hotkey_err "'\$mod' is i3-specific — set an explicit key (e.g. Super+p) in config.yaml"
        return 1 ;;
      *)
        _hotkey_err "'$key': unknown modifier '${parts[i]}'"
        return 1 ;;
    esac
  done
  printf '%s%s' "$out" "$sym"
}

hotkey_to_sxhkd() {  # "Ctrl+space" -> "ctrl + space"
  local key="${1:-}" out="" sym part
  [[ -z "$key" ]] && { _hotkey_err "is empty"; return 1; }
  local -a parts=()
  IFS='+' read -ra parts <<< "$key"
  local n=${#parts[@]}
  (( n == 0 )) && { _hotkey_err "'$key' has no key symbol"; return 1; }
  sym="${parts[n-1]}"
  if [[ -z "$sym" ]] || _hotkey_is_mod "$sym"; then
    _hotkey_err "'$key' has no key symbol"; return 1
  fi
  # Single letters are lowercased (sxhkd keysyms); longer names (F5, space,
  # Return) pass through as-is.
  (( ${#sym} == 1 )) && sym="${sym,,}"
  local i
  for (( i = 0; i < n - 1; i++ )); do
    part="${parts[i],,}"
    case "$part" in
      ctrl|control)   out+="ctrl + " ;;
      shift)          out+="shift + " ;;
      alt|mod1)       out+="alt + " ;;
      super|mod4|win) out+="super + " ;;
      '$mod')
        _hotkey_err "'\$mod' is i3-specific — set an explicit key (e.g. Super+p) in config.yaml"
        return 1 ;;
      *)
        _hotkey_err "'$key': unknown modifier '${parts[i]}'"
        return 1 ;;
    esac
  done
  printf '%s%s' "$out" "$sym"
}
