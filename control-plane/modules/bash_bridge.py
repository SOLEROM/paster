"""Ask the bash scripts instead of re-implementing them (plan D4).

* ``list_tabs`` → ``bin/toggle.sh --list-tabs`` (labels as rofi shows them)
* ``dump_config`` → source ``bin/lib-config.sh`` on a file and read back the
  ``PASTER_CFG_*`` it resolved plus the warnings it printed

Both are argv subprocesses with a timeout; neither touches X11.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import Paths

TIMEOUT_S = 10
# Warnings go to stderr as lib-config.sh prints them; values come back
# NUL-separated so no quoting rule of `declare -p` has to be parsed.
_DUMP_SCRIPT = (
    'PASTER_CONFIG_FILE="$1"; source "$2"; '
    'for v in "${!PASTER_CFG_@}"; do printf "%s=%s\\0" "$v" "${!v}"; done'
)


class BridgeError(RuntimeError):
    """The script could not be run — a broken checkout, not bad user input."""


@dataclass(frozen=True)
class ConfigDump:
    values: dict           # key (lowercase, no prefix) → effective value
    warnings: tuple        # the "paster: config …" lines lib-config.sh printed


def _run(argv: list[str], env: dict) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, text=False, env=env,
                              timeout=TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        # The name only: TimeoutExpired's str() carries the whole argv.
        raise BridgeError(f"could not run {os.path.basename(argv[1])}: {type(exc).__name__}") from exc


def list_tabs(paths: Paths) -> tuple[tuple[str, Path], ...]:
    """(label, folder) per tab, in the order rofi shows them."""
    env = {**os.environ, "PASTER_ENTRIES_DIR": str(paths.entries_dir),
           "PASTER_CONFIG_FILE": str(paths.config_file)}
    proc = _run(["bash", str(paths.toggle_script), "--list-tabs"], env)
    if proc.returncode != 0:
        raise BridgeError(f"toggle.sh --list-tabs failed: {proc.stderr.decode(errors='replace').strip()}")
    rows = []
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        label, sep, folder = line.partition("\t")
        if sep and label:
            rows.append((label, Path(folder)))
    return tuple(rows)


def dump_config(paths: Paths, config_file: Path | None = None) -> ConfigDump:
    """What lib-config.sh resolves for ``config_file`` (default: the live one)."""
    target = config_file or paths.config_file
    env = {**os.environ}
    env.pop("PASTER_CONFIG_FILE", None)
    proc = _run(["bash", "-c", _DUMP_SCRIPT, "_", str(target), str(paths.lib_config)], env)
    if proc.returncode != 0:
        raise BridgeError(f"lib-config.sh failed: {proc.stderr.decode(errors='replace').strip()}")
    values = {}
    for item in proc.stdout.decode("utf-8", errors="replace").split("\0"):
        name, sep, value = item.partition("=")
        if sep and name.startswith("PASTER_CFG_"):
            values[name[len("PASTER_CFG_"):].lower()] = value
    warnings = tuple(line for line in proc.stderr.decode("utf-8", errors="replace").splitlines()
                     if line.startswith("paster: config"))
    return ConfigDump(values=values, warnings=warnings)
