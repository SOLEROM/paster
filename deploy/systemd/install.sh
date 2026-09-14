#!/usr/bin/env bash
# Installs the paster front as a systemd user service on Ubuntu/Debian hosts.
# Run as the user who will own the service (not root).
#
# Usage:
#   ./install.sh                          # auto-detects project root (two levels up)
#   ./install.sh --project /path/to/repo  # explicit project root
#   ./install.sh --vname .venv-ubuntu24   # venv used by the service (default: .venv)
#   ./install.sh --bench-origins "http://<shell-host>:<shell-port> ..."
#                                         # allow a mainBench shell on ANOTHER
#                                         # machine to frame this app (space-
#                                         # separated origins, solBench plan
#                                         # §7). A shell on this same host
#                                         # needs nothing: the app always
#                                         # allows its own hostname.
#   ./install.sh --no-start               # install + enable only, don't start now
#   ./install.sh --uninstall              # stop, disable, and remove the service
#
# The listen port is taken from the `.port` file at the repo root (one line,
# just the number), falling back to 8790 — no unit edit needed. Change the
# port with `echo 6012 > <repo>/.port` then restart, and mirror the roster
# row in solBench/myApps.md.
#
# Bench origins precedence: --bench-origins › a BENCH_SHELL_ORIGINS variable
# in this script's environment › the value already in the installed unit (a
# reinstall never silently drops a cross-host shell) › empty (same-host
# shells only, which is all a single-machine bench needs).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
VENV_NAME=".venv"
START_NOW=1
UNINSTALL=0
SERVICE_NAME="paster"
BENCH_ORIGINS="${BENCH_SHELL_ORIGINS:-}"
BENCH_ORIGINS_FROM_FLAG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)   PROJECT_PATH="$2"; shift 2 ;;
    --project=*) PROJECT_PATH="${1#*=}"; shift ;;
    --vname)     VENV_NAME="$2"; shift 2 ;;
    --vname=*)   VENV_NAME="${1#*=}"; shift ;;
    --bench-origins)   BENCH_ORIGINS="$2"; BENCH_ORIGINS_FROM_FLAG=1; shift 2 ;;
    --bench-origins=*) BENCH_ORIGINS="${1#*=}"; BENCH_ORIGINS_FROM_FLAG=1; shift ;;
    --no-start)  START_NOW=0; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)   sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1"; exit 64 ;;
  esac
done

SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME.service"
TEMPLATE="$SCRIPT_DIR/paster.service.template"

if [[ "$UNINSTALL" -eq 1 ]]; then
  echo "Uninstalling $SERVICE_NAME service..."
  systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
  rm -f "$SERVICE_FILE"
  systemctl --user daemon-reload
  echo "Done. Service removed."
  exit 0
fi

[[ -f "$TEMPLATE" ]] || { echo "ERROR: service template not found at $TEMPLATE"; exit 1; }
[[ -x "$PROJECT_PATH/run.sh" ]] || {
  echo "ERROR: run.sh not found or not executable at $PROJECT_PATH/run.sh"
  echo "  Pass the correct project root with --project /path/to/repo"; exit 1; }
systemctl --user status >/dev/null 2>&1 || {
  echo "ERROR: systemd user session is not available (run as a normal user with a D-Bus session)."; exit 1; }

# Neither flag nor env given: inherit the installed unit's value, so a
# reinstall never silently un-docks this host.
if [[ "$BENCH_ORIGINS_FROM_FLAG" -eq 0 && -z "$BENCH_ORIGINS" && -f "$SERVICE_FILE" ]]; then
  BENCH_ORIGINS="$(sed -n 's/^Environment="BENCH_SHELL_ORIGINS=\(.*\)"$/\1/p' "$SERVICE_FILE" | head -n1)"
fi
# A malformed origin would put the service in a crash loop — the app refuses
# to start rather than serve a dropped or spliced CSP — so catch it here.
for origin in $BENCH_ORIGINS; do
  if [[ ! "$origin" =~ ^https?://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._-]+)(:[0-9]{1,5})?/?$ ]]; then
    echo "ERROR: bench origin '$origin' is not an http(s) origin (scheme://host[:port], space-separated)"; exit 64
  fi
done

echo "Installing $SERVICE_NAME systemd user service"
echo "  project : $PROJECT_PATH"
echo "  venv    : $VENV_NAME"
echo "  service : $SERVICE_FILE"
if [[ -n "$BENCH_ORIGINS" ]]; then echo "  bench   : same-host shells + $BENCH_ORIGINS"
else echo "  bench   : same-host shells (--bench-origins only for a shell on another machine)"; fi
if [[ -f "$PROJECT_PATH/.port" ]]; then echo "  port    : $(tr -d '[:space:]' < "$PROJECT_PATH/.port") (from .port)"
else echo "  port    : 8790 (default — drop a .port file to change)"; fi
echo

mkdir -p "$SERVICE_DIR"
sed \
  -e "s|__PROJECT_PATH__|${PROJECT_PATH}|g" \
  -e "s|__VENV_NAME__|${VENV_NAME}|g" \
  -e "s|__BENCH_SHELL_ORIGINS__|${BENCH_ORIGINS}|g" \
  "$TEMPLATE" > "$SERVICE_FILE"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
if loginctl enable-linger "$(whoami)" 2>/dev/null; then
  echo "  linger  : enabled (service will start at boot without login)"
else
  echo "  linger  : could not enable (may need: sudo loginctl enable-linger $(whoami))"
fi

if [[ "$START_NOW" -eq 1 ]]; then
  systemctl --user start "$SERVICE_NAME"
  echo
  systemctl --user status "$SERVICE_NAME" --no-pager || true
else
  echo; echo "Service installed and enabled. Start it with: systemctl --user start $SERVICE_NAME"
fi
echo
echo "Useful commands:"
echo "  systemctl --user status  $SERVICE_NAME"
echo "  systemctl --user restart $SERVICE_NAME"
echo "  journalctl --user -u $SERVICE_NAME -f"
