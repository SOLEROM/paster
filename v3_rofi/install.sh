#!/usr/bin/env bash
# paster v3 installer.
#
#   ./install.sh [KEY]
#
# KEY is the hotkey to bind (anything i3 bindsym accepts), e.g.:
#   ./install.sh              # default: $mod+p on Regolith, Mod1+p on plain i3
#   ./install.sh 'Mod4+p'     # Super+p
#   ./install.sh 'Mod1+space' # Alt+Space
# Re-running with a different KEY rebinds (idempotent).
#
# Checks the dependencies and apt-installs any that are missing, then wires
# the i3 snippet into whichever config the session actually uses: a drop-in
# file for Regolith i3, or an appended block in ~/.config/i3/config for
# plain i3. Installing v3 replaces a previous paster v1/v0i3 install (same
# hotkey slot, same drop-in file) and closes their leftover popup window.
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTER_KEY_ARG="${1:-}"
REGOLITH_DROPIN_DIR="$HOME/.config/regolith3/i3/config.d"
I3_USER_CONFIG="$HOME/.config/i3/config"
I3_SYSTEM_CONFIG="/etc/i3/config"
# Blocks these markers delimit are removed before appending ours ("paster v3"
# first in the list = the one we then append). Keeps upgrades from v1/v0 clean.
MARKER_NAMES=('paster v3' 'paster v1' 'paster v0i3')

info() { printf '[paster] %s\n' "$*"; }
die()  { printf '[paster] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Environment sanity — this version is i3/X11 only.
[[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] \
  && die "Wayland session detected — paster v3 requires X11."
command -v i3 >/dev/null 2>&1 || die "i3 not found — paster v3 targets i3."

# 2. Dependencies — install whatever is missing via apt.
declare -A DEP_PKG=([rofi]=rofi [xdotool]=xdotool [xclip]=xclip [xprop]=x11-utils)
missing_pkgs=()
for dep in "${!DEP_PKG[@]}"; do
  command -v "$dep" >/dev/null 2>&1 || missing_pkgs+=("${DEP_PKG[$dep]}")
done
if (( ${#missing_pkgs[@]} > 0 )); then
  info "installing missing dependencies via apt (sudo required): ${missing_pkgs[*]}"
  sudo apt-get install -y "${missing_pkgs[@]}"
  for dep in "${!DEP_PKG[@]}"; do
    command -v "$dep" >/dev/null 2>&1 || die "dependency still missing after install: $dep"
  done
fi

# 3. Executable bits on the scripts.
chmod +x "$PASTER_DIR"/bin/*.sh "$PASTER_DIR/install.sh"

# 4. Global settings from config.yaml (hotkey; look/size keys are read live
#    by toggle.sh). CLI argument > config.yaml hotkey > per-flavor default.
source "$PASTER_DIR/bin/lib-config.sh"

# 5. Wire the snippet into whichever config this session actually uses.
#    Regolith i3 starts as `i3 -c /etc/regolith/i3/config` and never reads
#    ~/.config/i3/config — its user extension point is the config.d drop-in
#    directory instead.
#    The hotkey is validated (it's free text from config.yaml/CLI) and the
#    install path sed-escaped before substitution, so a stray character
#    can't corrupt the rendered i3 config.
check_key() {
  [[ "$PASTER_KEY" =~ ^[A-Za-z0-9_+\$]+$ ]] \
    || die "hotkey '$PASTER_KEY' contains characters i3 bindsym won't accept — use e.g. 'Mod4+p', 'Ctrl+space'"
}
render_snippet() {
  sed -e "s|__PASTER_DIR__|$(printf '%s' "$PASTER_DIR" | sed 's/[&|\\]/\\&/g')|g" \
      -e "s|__PASTER_KEY__|$(printf '%s' "$PASTER_KEY" | sed 's/[&|\\]/\\&/g')|g" \
      "$PASTER_DIR/config/i3.conf.snippet"
}

if [[ -d "$REGOLITH_DROPIN_DIR" ]]; then
  # Regolith defines $mod (Super)
  PASTER_KEY="${PASTER_KEY_ARG:-${PASTER_CFG_HOTKEY:-\$mod+p}}"
  check_key
  render_snippet > "$REGOLITH_DROPIN_DIR/90_paster.tmp"
  mv "$REGOLITH_DROPIN_DIR/90_paster.tmp" "$REGOLITH_DROPIN_DIR/90_paster"
  info "Regolith i3 detected — wrote $REGOLITH_DROPIN_DIR/90_paster"
else
  # plain i3: Alt+p, no $mod assumed
  PASTER_KEY="${PASTER_KEY_ARG:-${PASTER_CFG_HOTKEY:-Mod1+p}}"
  check_key
  if [[ ! -f "$I3_USER_CONFIG" ]]; then
    [[ -f "$I3_SYSTEM_CONFIG" ]] \
      || die "no i3 config found at $I3_USER_CONFIG or $I3_SYSTEM_CONFIG"
    info "no user i3 config — seeding $I3_USER_CONFIG from $I3_SYSTEM_CONFIG"
    mkdir -p "$(dirname "$I3_USER_CONFIG")"
    cp "$I3_SYSTEM_CONFIG" "$I3_USER_CONFIG"
  fi

  cp "$I3_USER_CONFIG" "$I3_USER_CONFIG.paster-backup"
  info "backed up i3 config to $I3_USER_CONFIG.paster-backup"

  for name in "${MARKER_NAMES[@]}"; do
    if grep -qF "# >>> $name >>>" "$I3_USER_CONFIG"; then
      info "existing $name block found — removing it"
      sed -i "\|^# >>> $name >>>\$|,\|^# <<< $name <<<\$|d" "$I3_USER_CONFIG"
    fi
  done

  { echo ""; render_snippet; } >> "$I3_USER_CONFIG"
  info "appended paster block to $I3_USER_CONFIG"
fi

# 6. Leftovers from previous versions: a v0/v1 alacritty window may still sit
#    in the scratchpad running the old menu loop, and a live v3 rofi popup
#    may hold stale settings — close both so the next toggle starts fresh.
i3-msg -q '[class="Paster"] kill' >/dev/null 2>&1 || true
pkill -f 'rofi .*/paster\.rasi' 2>/dev/null || true

# 7. Reload i3 so the binding takes effect now.
if i3-msg -q reload >/dev/null 2>&1; then
  info "i3 reloaded."
else
  info "could not reach i3 — run 'i3-msg reload' from inside your session."
fi

info "done — hotkey is: $PASTER_KEY  (rebind any time: ./install.sh '<key>')"
