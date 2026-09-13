#!/usr/bin/env bash
# paster v3 — runs every tests/test-*.sh; exit 0 only if all are green.
set -uo pipefail
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rc=0
for t in "$TESTS_DIR"/test-*.sh; do
  printf '== %s\n' "$(basename "$t")"
  bash "$t" || rc=1
done
exit "$rc"
