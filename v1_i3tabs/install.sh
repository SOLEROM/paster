#!/usr/bin/env bash
# paster v1 installer.
#
#   ./install.sh [KEY]
#
# KEY is the hotkey to bind (anything i3 bindsym accepts), e.g.:
#   ./install.sh              # default: $mod+p on Regolith, Mod1+p on plain i3
#   ./install.sh 'Mod4+p'     # Super+p
#   ./install.sh 'Mod1+space' # Alt+Space
# Re-running with a different KEY rebinds (idempotent).
#
# Installs alacritty if missing, then wires the i3 snippet into whichever
# config the session actually uses: a drop-in file for Regolith i3, or an
# appended block in ~/.config/i3/config for plain i3. Installing v1 replaces
# a previous paster v0i3 install (same hotkey, same drop-in file).
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTER_KEY_ARG="${1:-}"
REGOLITH_DROPIN_DIR="$HOME/.config/regolith3/i3/config.d"
I3_USER_CONFIG="$HOME/.config/i3/config"
I3_SYSTEM_CONFIG="/etc/i3/config"
# Blocks these markers delimit are removed before appending ours ("paster v1"
# first in the list = the one we then append). Keeps upgrades from v0i3 clean.
MARKER_NAMES=('paster v1' 'paster v0i3')

info() { printf '[paster] %s\n' "$*"; }
die()  { printf '[paster] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Environment sanity — this version is i3/X11 only.
[[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] \
  && die "Wayland session detected — paster v1 requires X11."
command -v i3 >/dev/null 2>&1 || die "i3 not found — paster v1 targets i3."

# 2. Dependencies.
for dep in fzf xdotool xclip xprop i3-msg jq; do
  command -v "$dep" >/dev/null 2>&1 || die "missing dependency: $dep"
done

if ! command -v alacritty >/dev/null 2>&1; then
  info "alacritty not found — installing via apt (sudo required)…"
  sudo apt-get install -y alacritty
fi

# 3. Executable bits on the scripts.
chmod +x "$PASTER_DIR"/bin/*.sh "$PASTER_DIR/install.sh"

# 4. Global settings from config.yaml (hotkey, border; the rest is read live
#    by toggle.sh). CLI argument > config.yaml hotkey > per-flavor default.
source "$PASTER_DIR/bin/lib-config.sh"

# 5. Wire the snippet into whichever config this session actually uses.
#    Regolith i3 starts as `i3 -c /etc/regolith/i3/config` and never reads
#    ~/.config/i3/config — its user extension point is the config.d drop-in
#    directory instead.
render_snippet() {
  sed -e "s|__PASTER_DIR__|$PASTER_DIR|g" \
      -e "s|__PASTER_KEY__|$PASTER_KEY|g" \
      -e "s|__PASTER_BORDER__|$PASTER_CFG_BORDER_PX|g" \
      "$PASTER_DIR/config/i3.conf.snippet"
}

if [[ -d "$REGOLITH_DROPIN_DIR" ]]; then
  # Regolith defines $mod (Super)
  PASTER_KEY="${PASTER_KEY_ARG:-${PASTER_CFG_HOTKEY:-\$mod+p}}"
  render_snippet > "$REGOLITH_DROPIN_DIR/90_paster"
  info "Regolith i3 detected — wrote $REGOLITH_DROPIN_DIR/90_paster"
else
  # plain i3: Alt+p, no $mod assumed
  PASTER_KEY="${PASTER_KEY_ARG:-${PASTER_CFG_HOTKEY:-Mod1+p}}"
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

# 6. A Paster window from a previous install (or with stale config.yaml look
#    values) may still sit in the scratchpad running the old menu loop —
#    close it so the next toggle spawns a fresh one.
i3-msg -q '[class="Paster"] kill' >/dev/null 2>&1 || true

# 7. Reload i3 so the binding and window rule take effect now.
if i3-msg -q reload >/dev/null 2>&1; then
  info "i3 reloaded."
else
  info "could not reach i3 — run 'i3-msg reload' from inside your session."
fi

info "done — hotkey is: $PASTER_KEY  (rebind any time: ./install.sh '<key>')"
