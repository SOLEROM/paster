#!/usr/bin/env bash
# paster v0i3 installer.
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
# appended block in ~/.config/i3/config for plain i3.
set -euo pipefail

PASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTER_KEY_ARG="${1:-}"
REGOLITH_DROPIN_DIR="$HOME/.config/regolith3/i3/config.d"
I3_USER_CONFIG="$HOME/.config/i3/config"
I3_SYSTEM_CONFIG="/etc/i3/config"
MARKER_BEGIN='# >>> paster v0i3 >>>'
MARKER_END='# <<< paster v0i3 <<<'

info() { printf '[paster] %s\n' "$*"; }
die()  { printf '[paster] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Environment sanity — this version is i3/X11 only.
[[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] \
  && die "Wayland session detected — paster v0i3 requires X11."
command -v i3 >/dev/null 2>&1 || die "i3 not found — paster v0i3 targets i3."

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

# 4. Wire the snippet into whichever config this session actually uses.
#    Regolith i3 starts as `i3 -c /etc/regolith/i3/config` and never reads
#    ~/.config/i3/config — its user extension point is the config.d drop-in
#    directory instead.
render_snippet() {
  sed -e "s|__PASTER_DIR__|$PASTER_DIR|g" \
      -e "s|__PASTER_KEY__|$PASTER_KEY|g" \
      "$PASTER_DIR/config/i3.conf.snippet"
}

if [[ -d "$REGOLITH_DROPIN_DIR" ]]; then
  PASTER_KEY="${PASTER_KEY_ARG:-\$mod+p}"   # Regolith defines $mod (Super)
  render_snippet > "$REGOLITH_DROPIN_DIR/90_paster"
  info "Regolith i3 detected — wrote $REGOLITH_DROPIN_DIR/90_paster"
else
  PASTER_KEY="${PASTER_KEY_ARG:-Mod1+p}"    # plain i3: Alt+p, no $mod assumed
  if [[ ! -f "$I3_USER_CONFIG" ]]; then
    [[ -f "$I3_SYSTEM_CONFIG" ]] \
      || die "no i3 config found at $I3_USER_CONFIG or $I3_SYSTEM_CONFIG"
    info "no user i3 config — seeding $I3_USER_CONFIG from $I3_SYSTEM_CONFIG"
    mkdir -p "$(dirname "$I3_USER_CONFIG")"
    cp "$I3_SYSTEM_CONFIG" "$I3_USER_CONFIG"
  fi

  cp "$I3_USER_CONFIG" "$I3_USER_CONFIG.paster-backup"
  info "backed up i3 config to $I3_USER_CONFIG.paster-backup"

  if grep -qF "$MARKER_BEGIN" "$I3_USER_CONFIG"; then
    info "existing paster block found — replacing it"
    sed -i "\|^$MARKER_BEGIN\$|,\|^$MARKER_END\$|d" "$I3_USER_CONFIG"
  fi

  { echo ""; render_snippet; } >> "$I3_USER_CONFIG"
  info "appended paster block to $I3_USER_CONFIG"
fi

# 5. Reload i3 so the binding and window rule take effect now.
if i3-msg -q reload >/dev/null 2>&1; then
  info "i3 reloaded."
else
  info "could not reach i3 — run 'i3-msg reload' from inside your session."
fi

info "done — hotkey is: $PASTER_KEY  (rebind any time: ./install.sh '<key>')"
