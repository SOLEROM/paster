#!/usr/bin/env bash
# paster v2 installer — any Ubuntu desktop, not just i3.
#
#   ./install.sh [KEY] [--sxhkd] [--dry-run]
#   ./install.sh --uninstall
#
# KEY is an i3-style hotkey ("Ctrl+space", "Mod4+p"); it overrides the
# hotkey in config.yaml. The installer detects the running session and
# wires the hotkey through whatever that desktop actually provides:
#
#   i3 / Regolith      i3 config drop-in / appended block       (Tier 1)
#   GNOME on Xorg      gsettings custom shortcut                (Tier 1)
#   GNOME on Wayland   gsettings custom shortcut     (Tier 2: no auto-paste)
#   Cinnamon / MATE    gsettings / dconf custom shortcut        (Tier 1)
#   XFCE               xfconf custom command                    (Tier 1)
#   KDE / other        manual instructions, or --sxhkd          (Tier 1 once bound)
#
# --sxhkd     use the sxhkd fallback (installs sxhkd, markered rc block,
#             autostart entry) instead of desktop-native wiring.
# --dry-run   print detection result + intended actions, change nothing.
# --uninstall reverse whatever a previous run wired, then exit.
#
# Re-running is idempotent (replaces previous wiring, including v0i3/v1
# blocks on i3). PASTER_FORCE_WIRING=<i3|gnome|cinnamon|mate|xfce|manual>
# overrides detection — for testing only.
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$PASTER_DIR/.install-state"
REGOLITH_DROPIN_DIR="$HOME/.config/regolith3/i3/config.d"
I3_USER_CONFIG="$HOME/.config/i3/config"
I3_SYSTEM_CONFIG="/etc/i3/config"
SXHKD_RC="$HOME/.config/sxhkd/sxhkdrc"
SXHKD_AUTOSTART="$HOME/.config/autostart/paster-sxhkd.desktop"
# Blocks these markers delimit are removed before appending ours ("paster v2"
# first = the one we then append). Keeps upgrades from v0i3/v1 clean.
MARKER_NAMES=('paster v2' 'paster v1' 'paster v0i3')

GNOME_LIST_SCHEMA='org.gnome.settings-daemon.plugins.media-keys'
GNOME_KB_SCHEMA='org.gnome.settings-daemon.plugins.media-keys.custom-keybinding'
GNOME_KB_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/paster/'
CINN_LIST_SCHEMA='org.cinnamon.desktop.keybindings'
CINN_KB_SCHEMA='org.cinnamon.desktop.keybindings.custom-keybinding'
CINN_KB_PATH='/org/cinnamon/desktop/keybindings/custom-keybindings/paster/'
MATE_KB_PATH='/org/mate/desktop/keybindings/paster/'

info() { printf '[paster] %s\n' "$*"; }
die()  { printf '[paster] ERROR: %s\n' "$*" >&2; exit 1; }

# --- arguments ---------------------------------------------------------------
PASTER_KEY_ARG=""
DO_SXHKD=0 DO_UNINSTALL=0 DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --sxhkd)     DO_SXHKD=1 ;;
    --uninstall) DO_UNINSTALL=1 ;;
    --dry-run)   DRY_RUN=1 ;;
    --*)         die "unknown flag: $arg" ;;
    *)           PASTER_KEY_ARG="$arg" ;;
  esac
done

source "$PASTER_DIR/bin/lib-config.sh"
source "$PASTER_DIR/bin/lib-hotkey.sh"

# --- detection ---------------------------------------------------------------
SESSION="${XDG_SESSION_TYPE:-x11}"
DESKTOP="${XDG_CURRENT_DESKTOP:-}"
WIRING="" I3_FLAVOR=""

detect_wiring() {
  if [[ -n "${PASTER_FORCE_WIRING:-}" ]]; then
    WIRING="$PASTER_FORCE_WIRING"
    if [[ "$WIRING" == "i3" ]]; then
      [[ -d "$REGOLITH_DROPIN_DIR" ]] && I3_FLAVOR="regolith" || I3_FLAVOR="plain"
    fi
    return 0
  fi
  shopt -s nocasematch
  if [[ -d "$REGOLITH_DROPIN_DIR" ]]; then
    WIRING="i3"; I3_FLAVOR="regolith"
  elif i3-msg -t get_version >/dev/null 2>&1 || [[ "$DESKTOP" == *i3* || "$DESKTOP" == *regolith* ]]; then
    WIRING="i3"; I3_FLAVOR="plain"
  elif [[ "$DESKTOP" == *gnome* || "$DESKTOP" == *ubuntu* || "$DESKTOP" == *unity* ]]; then
    WIRING="gnome"
  elif [[ "$DESKTOP" == *cinnamon* ]]; then
    WIRING="cinnamon"
  elif [[ "$DESKTOP" == *mate* ]]; then
    WIRING="mate"
  elif [[ "$DESKTOP" == *xfce* ]]; then
    WIRING="xfce"
  else
    WIRING="manual"
  fi
  shopt -u nocasematch
}
detect_wiring
(( DO_SXHKD )) && WIRING="sxhkd"

TIER=1
if [[ "$SESSION" == "wayland" && $DO_UNINSTALL -eq 0 ]]; then
  if [[ "$WIRING" == "gnome" ]]; then
    TIER=2
  else
    die "Wayland session with desktop '$DESKTOP' is unsupported — log in with an Xorg session (e.g. 'Ubuntu on Xorg' at the login screen), or use GNOME Wayland for the degraded (no auto-paste) mode."
  fi
fi

# --- gsettings list helpers (flat bash munging, no python dependency) --------
gsettings_list_add() {  # SCHEMA KEY ITEM
  local cur new
  cur="$(gsettings get "$1" "$2" 2>/dev/null)" || return 1
  case "$cur" in
    *"'$3'"*) return 0 ;;
    "@as []"|"[]") new="['$3']" ;;
    *) new="${cur%]}, '$3']" ;;
  esac
  gsettings set "$1" "$2" "$new"
}

gsettings_list_remove() {  # SCHEMA KEY ITEM
  local cur new
  cur="$(gsettings get "$1" "$2" 2>/dev/null)" || return 0
  [[ "$cur" == *"'$3'"* ]] || return 0
  new="$(printf '%s' "$cur" | sed -e "s|'$3', ||" -e "s|, '$3'||" -e "s|'$3'||")"
  [[ "$new" == "[]" ]] && new="@as []"
  gsettings set "$1" "$2" "$new" 2>/dev/null || true
}

# --- uninstall ---------------------------------------------------------------
uninstall_all() {
  local xfce_prop=""
  [[ -f "$STATE_FILE" ]] \
    && xfce_prop="$(sed -n 's/^xfce_prop=//p' "$STATE_FILE" | head -n1)"

  if (( DRY_RUN )); then
    info "dry-run: would remove i3 blocks/drop-in, gsettings/dconf/xfconf shortcuts, sxhkd block, autostart entry, state file, and close the Paster window."
    return 0
  fi

  # i3 / Regolith
  [[ -f "$REGOLITH_DROPIN_DIR/90_paster" ]] \
    && { rm -f "$REGOLITH_DROPIN_DIR/90_paster"; info "removed Regolith drop-in"; }
  if [[ -f "$I3_USER_CONFIG" ]]; then
    local name
    for name in "${MARKER_NAMES[@]}"; do
      if grep -qF "# >>> $name >>>" "$I3_USER_CONFIG"; then
        cp "$I3_USER_CONFIG" "$I3_USER_CONFIG.paster-backup"
        sed -i "\|^# >>> $name >>>\$|,\|^# <<< $name <<<\$|d" "$I3_USER_CONFIG"
        info "removed $name block from $I3_USER_CONFIG"
      fi
    done
  fi
  i3-msg -q reload >/dev/null 2>&1 || true

  # GNOME / Cinnamon / MATE
  if command -v gsettings >/dev/null 2>&1; then
    gsettings_list_remove "$GNOME_LIST_SCHEMA" custom-keybindings "$GNOME_KB_PATH"
    gsettings_list_remove "$CINN_LIST_SCHEMA" custom-list "paster"
  fi
  if command -v dconf >/dev/null 2>&1; then
    dconf reset -f "$GNOME_KB_PATH" 2>/dev/null || true
    dconf reset -f "$CINN_KB_PATH" 2>/dev/null || true
    dconf reset -f "$MATE_KB_PATH" 2>/dev/null || true
  fi

  # XFCE
  if command -v xfconf-query >/dev/null 2>&1 && [[ -n "$xfce_prop" ]]; then
    xfconf-query -c xfce4-keyboard-shortcuts -r -p "$xfce_prop" 2>/dev/null || true
  fi

  # sxhkd
  if [[ -f "$SXHKD_RC" ]] && grep -qF '# >>> paster v2 >>>' "$SXHKD_RC"; then
    sed -i '\|^# >>> paster v2 >>>$|,\|^# <<< paster v2 <<<$|d' "$SXHKD_RC"
    info "removed sxhkd block"
    pkill -USR1 -x sxhkd 2>/dev/null || true
  fi
  rm -f "$SXHKD_AUTOSTART"

  # Popup + state
  source "$PASTER_DIR/bin/lib-wm.sh"
  wm_kill_paster
  rm -f "$STATE_FILE"
  info "uninstalled."
}

if (( DO_UNINSTALL )); then
  uninstall_all
  exit 0
fi

# --- dependencies ------------------------------------------------------------
missing_pkgs=()
need() { command -v "$1" >/dev/null 2>&1 || missing_pkgs+=("$2"); }
need fzf fzf; need xdotool xdotool; need xclip xclip; need xprop x11-utils
need alacritty alacritty
if [[ "$WIRING" == "i3" ]]; then
  need jq jq
else
  need wmctrl wmctrl; need xrandr x11-xserver-utils
fi
[[ "$WIRING" == "mate" ]] && need dconf dconf-cli
[[ "$TIER" == 2 ]] && need notify-send libnotify-bin
[[ "$WIRING" == "sxhkd" ]] && need sxhkd sxhkd

if (( ${#missing_pkgs[@]} )); then
  if (( DRY_RUN )); then
    info "dry-run: would apt-get install: ${missing_pkgs[*]}"
  else
    info "installing missing packages via apt (sudo required): ${missing_pkgs[*]}"
    sudo apt-get install -y "${missing_pkgs[@]}"
  fi
fi

chmod +x "$PASTER_DIR"/bin/*.sh "$PASTER_DIR/install.sh"

# --- hotkey resolution: CLI arg > config.yaml > per-desktop default ----------
case "$WIRING:$I3_FLAVOR" in
  i3:regolith) DEFAULT_KEY='$mod+p' ;;
  i3:*)        DEFAULT_KEY='Mod1+p' ;;
  *)           DEFAULT_KEY='Ctrl+space' ;;
esac
PASTER_KEY="${PASTER_KEY_ARG:-${PASTER_CFG_HOTKEY:-$DEFAULT_KEY}}"

# --- wiring strategies -------------------------------------------------------
render_snippet() {
  sed -e "s|__PASTER_DIR__|$PASTER_DIR|g" \
      -e "s|__PASTER_KEY__|$PASTER_KEY|g" \
      -e "s|__PASTER_BORDER__|$PASTER_CFG_BORDER_PX|g" \
      "$PASTER_DIR/config/i3.conf.snippet"
}

wire_i3() {
  if (( DRY_RUN )); then
    info "dry-run: would wire i3 ($I3_FLAVOR) with bindsym $PASTER_KEY and reload i3."
    return 0
  fi
  if [[ "$I3_FLAVOR" == "regolith" ]]; then
    render_snippet > "$REGOLITH_DROPIN_DIR/90_paster"
    info "Regolith i3 detected — wrote $REGOLITH_DROPIN_DIR/90_paster"
  else
    if [[ ! -f "$I3_USER_CONFIG" ]]; then
      [[ -f "$I3_SYSTEM_CONFIG" ]] \
        || die "no i3 config found at $I3_USER_CONFIG or $I3_SYSTEM_CONFIG"
      info "no user i3 config — seeding $I3_USER_CONFIG from $I3_SYSTEM_CONFIG"
      mkdir -p "$(dirname "$I3_USER_CONFIG")"
      cp "$I3_SYSTEM_CONFIG" "$I3_USER_CONFIG"
    fi
    cp "$I3_USER_CONFIG" "$I3_USER_CONFIG.paster-backup"
    info "backed up i3 config to $I3_USER_CONFIG.paster-backup"
    local name
    for name in "${MARKER_NAMES[@]}"; do
      if grep -qF "# >>> $name >>>" "$I3_USER_CONFIG"; then
        info "existing $name block found — removing it"
        sed -i "\|^# >>> $name >>>\$|,\|^# <<< $name <<<\$|d" "$I3_USER_CONFIG"
      fi
    done
    { echo ""; render_snippet; } >> "$I3_USER_CONFIG"
    info "appended paster block to $I3_USER_CONFIG"
  fi
  if i3-msg -q reload >/dev/null 2>&1; then
    info "i3 reloaded."
  else
    info "could not reach i3 — run 'i3-msg reload' from inside your session."
  fi
}

wire_gnome() {
  local gtk_key
  gtk_key="$(hotkey_to_gtk "$PASTER_KEY")" || die "cannot translate hotkey '$PASTER_KEY' for GNOME"
  if (( DRY_RUN )); then
    info "dry-run: would register gsettings shortcut 'paster' = $gtk_key -> bin/toggle.sh"
    return 0
  fi
  gsettings_list_add "$GNOME_LIST_SCHEMA" custom-keybindings "$GNOME_KB_PATH" \
    || die "gsettings schema $GNOME_LIST_SCHEMA not available — is this really GNOME?"
  gsettings set "$GNOME_KB_SCHEMA:$GNOME_KB_PATH" name 'paster'
  gsettings set "$GNOME_KB_SCHEMA:$GNOME_KB_PATH" command "$PASTER_DIR/bin/toggle.sh"
  gsettings set "$GNOME_KB_SCHEMA:$GNOME_KB_PATH" binding "$gtk_key"
  info "GNOME shortcut registered: $gtk_key"
}

wire_cinnamon() {
  local gtk_key
  gtk_key="$(hotkey_to_gtk "$PASTER_KEY")" || die "cannot translate hotkey '$PASTER_KEY' for Cinnamon"
  if (( DRY_RUN )); then
    info "dry-run: would register Cinnamon shortcut 'paster' = $gtk_key -> bin/toggle.sh"
    return 0
  fi
  gsettings_list_add "$CINN_LIST_SCHEMA" custom-list "paster" \
    || die "gsettings schema $CINN_LIST_SCHEMA not available — is this really Cinnamon?"
  gsettings set "$CINN_KB_SCHEMA:$CINN_KB_PATH" name 'paster'
  gsettings set "$CINN_KB_SCHEMA:$CINN_KB_PATH" command "$PASTER_DIR/bin/toggle.sh"
  gsettings set "$CINN_KB_SCHEMA:$CINN_KB_PATH" binding "['$gtk_key']"
  info "Cinnamon shortcut registered: $gtk_key"
}

wire_mate() {
  local gtk_key
  gtk_key="$(hotkey_to_gtk "$PASTER_KEY")" || die "cannot translate hotkey '$PASTER_KEY' for MATE"
  if (( DRY_RUN )); then
    info "dry-run: would register MATE (dconf) shortcut 'paster' = $gtk_key -> bin/toggle.sh"
    return 0
  fi
  dconf write "${MATE_KB_PATH}name" "'paster'"
  dconf write "${MATE_KB_PATH}action" "'$PASTER_DIR/bin/toggle.sh'"
  dconf write "${MATE_KB_PATH}binding" "'$gtk_key'"
  info "MATE shortcut registered: $gtk_key"
}

wire_xfce() {
  local gtk_key prop
  gtk_key="$(hotkey_to_gtk "$PASTER_KEY")" || die "cannot translate hotkey '$PASTER_KEY' for XFCE"
  prop="/commands/custom/$gtk_key"
  if (( DRY_RUN )); then
    info "dry-run: would set xfconf $prop -> bin/toggle.sh"
    return 0
  fi
  # Remove the previously wired key first (it may differ from the new one).
  local old_prop=""
  [[ -f "$STATE_FILE" ]] && old_prop="$(sed -n 's/^xfce_prop=//p' "$STATE_FILE" | head -n1)"
  [[ -n "$old_prop" && "$old_prop" != "$prop" ]] \
    && xfconf-query -c xfce4-keyboard-shortcuts -r -p "$old_prop" 2>/dev/null || true
  xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -n -t string \
      -s "$PASTER_DIR/bin/toggle.sh" 2>/dev/null \
    || xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" \
      -s "$PASTER_DIR/bin/toggle.sh"
  XFCE_PROP="$prop"
  info "XFCE shortcut registered: $gtk_key"
}

wire_sxhkd() {
  local sx_key
  sx_key="$(hotkey_to_sxhkd "$PASTER_KEY")" || die "cannot translate hotkey '$PASTER_KEY' for sxhkd"
  if (( DRY_RUN )); then
    info "dry-run: would add sxhkd binding '$sx_key' + autostart entry."
    return 0
  fi
  mkdir -p "$(dirname "$SXHKD_RC")"
  touch "$SXHKD_RC"
  sed -i '\|^# >>> paster v2 >>>$|,\|^# <<< paster v2 <<<$|d' "$SXHKD_RC"
  printf '\n# >>> paster v2 >>>\n%s\n    %s/bin/toggle.sh\n# <<< paster v2 <<<\n' \
    "$sx_key" "$PASTER_DIR" >> "$SXHKD_RC"
  info "sxhkd binding written: $sx_key"
  if pgrep -x sxhkd >/dev/null 2>&1; then
    pkill -USR1 -x sxhkd 2>/dev/null || true
    info "sxhkd reloaded."
  else
    mkdir -p "$(dirname "$SXHKD_AUTOSTART")"
    printf '[Desktop Entry]\nType=Application\nName=sxhkd (paster hotkey)\nExec=sxhkd\nX-GNOME-Autostart-enabled=true\n' \
      > "$SXHKD_AUTOSTART"
    (sxhkd >/dev/null 2>&1 &) || true
    info "sxhkd started + autostart entry written."
  fi
}

wire_manual() {
  info "no automatic hotkey wiring for desktop '$DESKTOP'."
  info "Bind a key of your choice to run:  $PASTER_DIR/bin/toggle.sh"
  info "  KDE:  System Settings -> Shortcuts -> Custom Shortcuts -> New -> Command"
  info "  LXQt: Preferences -> Shortcut Keys"
  info "Or re-run  ./install.sh --sxhkd  for an automatic sxhkd-based hotkey."
}

XFCE_PROP=""
case "$WIRING" in
  i3)       wire_i3 ;;
  gnome)    wire_gnome ;;
  cinnamon) wire_cinnamon ;;
  mate)     wire_mate ;;
  xfce)     wire_xfce ;;
  sxhkd)    wire_sxhkd ;;
  manual)   wire_manual ;;
  *)        die "unknown wiring '$WIRING'" ;;
esac

# --- state, stale window, report --------------------------------------------
if (( DRY_RUN )); then
  info "dry-run: detection = wiring:$WIRING${I3_FLAVOR:+ ($I3_FLAVOR)}, session:$SESSION, tier:$TIER, hotkey:$PASTER_KEY — nothing changed."
  exit 0
fi

{
  printf 'wiring=%s\n' "$WIRING"
  printf 'key=%s\n' "$PASTER_KEY"
  if [[ -n "$XFCE_PROP" ]]; then printf 'xfce_prop=%s\n' "$XFCE_PROP"; fi
} > "$STATE_FILE"

# A Paster window from a previous install (or with stale config.yaml look
# values) may still be alive running the old menu loop — close it so the
# next toggle spawns a fresh one.
source "$PASTER_DIR/bin/lib-wm.sh"
wm_kill_paster

[[ "$TIER" == 2 ]] && info "NOTE: Wayland degraded mode — entries are copied to the clipboard, but auto-paste into the previous window is not possible; paste with Ctrl+V."
info "done — hotkey is: $PASTER_KEY  (rebind any time: ./install.sh '<key>'; remove: ./install.sh --uninstall)"
