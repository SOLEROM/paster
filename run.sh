#!/usr/bin/env bash
# paster front — launcher for the control plane (the web GUI over entries/
# and config.yaml). The rofi popup itself needs none of this: bin/toggle.sh
# runs on its own from the i3 binding.
#
# What it does for you, every time:
#   * creates the venv if it is missing or broken, installs
#     control-plane/requirements.txt and RE-installs when that file changes;
#   * refreshes the kit copy-ins (4ColThems, vsCodeFront, cldBar) from the
#     sibling solBench checkout — skipped under --skip-deps;
#   * checks that webterm is installed editable from that same checkout and
#     repairs it if not (every start, --skip-deps included).
#
# Usage:
#   ./run.sh                        # 127.0.0.1, port: --port › .port › 8790
#   ./run.sh --public               # bind 0.0.0.0 — NO AUTHENTICATION and the
#                                   # Sessions view is a real shell: trusted
#                                   # networks (the tailnet) only
#   ./run.sh --vname .venv-host     # use/create this venv (default .venv)
#   ./run.sh --test [pytest args]   # tests/run.sh (bash) + pytest with coverage
#   ./run.sh --skip-deps            # no kit refresh (the unit passes this)
# Any other flag is forwarded to control-plane/server.py (--port, --host).
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# solBench checkout: $SOLBENCH_HOME (other layouts) › sibling ../solBench (the bench layout)
SOLBENCH_HOME="${SOLBENCH_HOME:-$(dirname "$ROOT")/solBench}"
if [[ ! -f "$SOLBENCH_HOME/webterm/pyproject.toml" ]]; then
  echo "[warn] solBench not found at $SOLBENCH_HOME (set SOLBENCH_HOME on a host with another layout)" \
       "— no terminal and no kit refresh this run." >&2
  SOLBENCH_HOME=""
fi

VNAME=""
USER_PROVIDED_VENV=0
RUN_TESTS=0
SKIP_DEPS=0
FORWARD=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vname)
      [[ $# -ge 2 ]] || { echo "--vname requires a path" >&2; exit 64; }
      VNAME="$2"; USER_PROVIDED_VENV=1; shift 2 ;;
    --vname=*)
      VNAME="${1#*=}"; USER_PROVIDED_VENV=1; shift ;;
    --test)      RUN_TESTS=1; shift ;;
    --skip-deps) SKIP_DEPS=1; shift ;;
    -h|--help)   sed -n '2,25p' "$0"; exit 0 ;;
    *)           FORWARD+=("$1"); shift ;;
  esac
done

if [[ -z "$VNAME" ]]; then
  VENV="$ROOT/.venv"
elif [[ "$VNAME" = /* || "$VNAME" = ~* ]]; then
  VENV="${VNAME/#\~/$HOME}"
else
  VENV="$ROOT/$VNAME"
fi
REQ="$ROOT/control-plane/requirements.txt"
STAMP="$VENV/.paster-requirements-sha"
STATIC="$ROOT/control-plane/static"

ensure_python() {
  command -v python3 >/dev/null 2>&1 || { echo "python3 is not installed (apt install python3 python3-venv)" >&2; exit 3; }
  python3 -c "import venv" >/dev/null 2>&1 || { echo "python3 has no venv module (apt install python3-venv)" >&2; exit 3; }
}

venv_works() {
  [[ -x "$VENV/bin/python3" ]] && "$VENV/bin/python3" -c "import sys" >/dev/null 2>&1
}

ensure_venv() {
  venv_works && return 0
  if [[ "$USER_PROVIDED_VENV" -eq 1 && -d "$VENV" ]]; then
    echo "venv at $VENV is broken — fix or recreate it, or pass another --vname (refusing to delete a user-provided path)" >&2
    exit 4
  fi
  [[ -d "$VENV" ]] && { echo "Stale venv at $VENV — recreating."; rm -rf "$VENV"; }
  echo "Creating venv at $VENV ..."
  python3 -m venv "$VENV"
  "$VENV/bin/python3" -m pip install --quiet --upgrade pip
  rm -f "$STAMP"
}

# Re-install whenever requirements.txt changes (a pull that adds a dependency
# must not surface as an ImportError at startup). Always python -m pip.
requirements_sha() {
  "$VENV/bin/python3" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$REQ"
}
ensure_requirements() {
  local want have_sha=""
  want="$(requirements_sha)"
  [[ -f "$STAMP" ]] && have_sha="$(cat "$STAMP")"
  [[ "$want" == "$have_sha" ]] && return 0
  echo "Installing Python dependencies into $VENV ..."
  "$VENV/bin/python3" -m pip install --quiet -r "$REQ"
  printf '%s' "$want" >"$STAMP"
}

# The kits are copy-ins (committed, so a lone clone runs); refreshed from the
# sibling checkout so an upstream fix lands on the next start. Their
# installers prove their own suites first; a failing kit leaves the last
# good copies in place.
ensure_kits() {
  mkdir -p "$STATIC/css" "$STATIC/js" "$STATIC/fonts" "$STATIC/vendor"
  "$SOLBENCH_HOME/4ColThems/install.sh" --css "$STATIC/css" --js "$STATIC/js" --data "$STATIC" --py "$STATIC" >/dev/null \
    || echo "[warn] 4ColThems refresh failed — keeping the current copies" >&2
  "$SOLBENCH_HOME/vsCodeFront/install.sh" --static "$STATIC" >/dev/null \
    || echo "[warn] vsCodeFront refresh failed — keeping the current copies" >&2
  "$SOLBENCH_HOME/cldBar/install.sh" "$STATIC/js" >/dev/null \
    || echo "[warn] cldBar refresh failed — keeping the current copy" >&2
}

# webterm self-repair: every start, --skip-deps included (that flag means
# "don't refresh"; this is repair, and it survives solBench moving).
webterm_ok() {  # cwd / and -I: from inside a solBench parent, cwd would shadow the install (webterm/install.sh:62-65)
  [[ -n "$SOLBENCH_HOME" ]] || return 0
  (cd / && "$VENV/bin/python3" -I - "$SOLBENCH_HOME/webterm/webterm" <<'PY'
import os, sys
try:
    import webterm
except Exception:
    sys.exit(1)
sys.exit(0 if os.path.samefile(os.path.dirname(webterm.__file__), sys.argv[1]) else 1)
PY
  ) 2>/dev/null
}
ensure_webterm() {
  webterm_ok && return 0
  echo "[setup] installing webterm from $SOLBENCH_HOME ..."
  "$SOLBENCH_HOME/webterm/install.sh" "$VENV" >/dev/null \
    || echo "[warn] webterm install failed — the Sessions view is off this run." >&2
}

ensure_python
ensure_venv
ensure_requirements
if [[ "$SKIP_DEPS" -eq 0 && -n "$SOLBENCH_HOME" ]]; then ensure_kits; fi
ensure_webterm

if [[ "$RUN_TESTS" -eq 1 ]]; then
  echo "== bash suite (tests/run.sh)"
  bash "$ROOT/tests/run.sh"
  echo "== pytest (control plane)"
  exec "$VENV/bin/python" -m pytest --cov=modules --cov-report=term-missing --cov-fail-under=80 \
    ${FORWARD[@]+"${FORWARD[@]}"}
fi

exec "$VENV/bin/python" control-plane/server.py ${FORWARD[@]+"${FORWARD[@]}"}
