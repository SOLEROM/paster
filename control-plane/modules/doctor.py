"""The Doctor: is the hotkey wired, is everything installed, what state is
lying around (plan §6). Pure functions over an injected ``Probe`` so every
check has a red, green and "not applicable" test with stub binaries.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from . import bash_bridge, entries_store
from .paths import Paths

DEPS = (("rofi", "rofi"), ("xdotool", "xdotool"), ("xclip", "xclip"), ("xprop", "x11-utils"))
ROFI_MIN = (1, 6)
DROPIN = ("regolith3", "i3", "config.d", "90_paster")
I3_USER_CONFIG = ("i3", "config")
MARKERS = ("paster v3", "paster v1", "paster v0i3")
STATE_FILES = ("paster-prev-win", "paster-last-tab", "paster.rasi")
BINDSYM_RE = re.compile(r"^\s*bindsym\s+(\S+)\s+exec\s+(?:--no-startup-id\s+)?(\S+)", re.M)


@dataclass(frozen=True)
class Probe:
    env: Mapping[str, str]
    home: Path
    runtime_dir: Path
    which: Callable[[str], str | None]
    run: Callable[[list], tuple[int, str]]          # (rc, combined output)
    process_running: Callable[[str], bool]


def _run_default(argv: list) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr)


def _pgrep(name: str) -> bool:
    rc, _ = _run_default(["pgrep", "-x", name])
    return rc == 0


def default_probe() -> Probe:
    return Probe(env=dict(os.environ), home=Path.home(),
                 runtime_dir=Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp"),
                 which=shutil.which, run=_run_default, process_running=_pgrep)


def check(id: str, title: str, status: str, detail: str, fix: str | None = None) -> dict:
    return {"id": id, "title": title, "status": status, "detail": detail, "fix": fix}


# ---------------------------------------------------------------- pieces ---

def flavour(probe: Probe) -> str:
    return "regolith" if (probe.home.joinpath(".config", *DROPIN[:-1])).is_dir() else "plain"


def default_hotkey(flav: str) -> str:
    return "$mod+p" if flav == "regolith" else "Mod1+p"


def binding(paths: Paths, probe: Probe) -> dict:
    """Where the hotkey is wired, and to which script."""
    flav = flavour(probe)
    if flav == "regolith":
        dropin = probe.home.joinpath(".config", *DROPIN)
        if not dropin.is_file():
            return {"flavour": flav, "file": str(dropin), "present": False, "hotkey": None,
                    "script": None, "stale": False, "leftovers": []}
        text = dropin.read_text(encoding="utf-8", errors="replace")
        block, leftovers = text, []
    else:
        cfg = probe.home.joinpath(".config", *I3_USER_CONFIG)
        text = cfg.read_text(encoding="utf-8", errors="replace") if cfg.is_file() else ""
        leftovers = [m for m in MARKERS[1:] if f"# >>> {m} >>>" in text]
        m = re.search(r"# >>> paster v3 >>>(.*?)# <<< paster v3 <<<", text, re.S)
        if not m:
            return {"flavour": flav, "file": str(cfg), "present": False, "hotkey": None,
                    "script": None, "stale": False, "leftovers": leftovers}
        block, dropin = m.group(1), cfg
    bind = BINDSYM_RE.search(block)
    hotkey = bind.group(1) if bind else None
    script = bind.group(2) if bind else None
    stale = False
    if script:
        try:
            stale = Path(script).resolve() != paths.toggle_script.resolve()
        except OSError:
            stale = True
    return {"flavour": flav, "file": str(dropin), "present": True, "hotkey": hotkey,
            "script": script, "stale": stale, "leftovers": leftovers}


def rofi_version(probe: Probe) -> tuple[int, ...] | None:
    if not probe.which("rofi"):
        return None
    rc, out = probe.run(["rofi", "-version"])
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out or "")
    if rc != 0 or not m:
        return ()
    return tuple(int(x) for x in m.groups() if x is not None)


# ---------------------------------------------------------------- report ---

def run_checks(paths: Paths, probe: Probe, *, port: int | None = None,
               last_test_run: dict | None = None) -> dict:
    checks = []
    env = probe.env
    display = bool(env.get("DISPLAY"))
    session = env.get("XDG_SESSION_TYPE", "")

    # -- session
    if session == "wayland":
        checks.append(check("session", "Session", "fail", "Wayland session — paster v3 is X11 only."))
    elif display:
        checks.append(check("session", "Session", "ok", f"X11, DISPLAY={env['DISPLAY']}"))
    else:
        checks.append(check("session", "Session", "warn", "No DISPLAY in this server's environment — "
                            "desktop actions (open popup, apply) are disabled here.",
                            "Run the front from a user session that carries DISPLAY (systemd --user does on this host)."))

    # -- i3
    i3_up = probe.process_running("i3")
    flav = flavour(probe)
    checks.append(check("i3", "i3", "ok" if i3_up else "fail",
                        f"{'running' if i3_up else 'not running'} · {flav} layout", None if i3_up else "Start an i3 session."))

    # -- binding
    b = binding(paths, probe)
    if not b["present"]:
        checks.append(check("binding", "Hotkey binding", "fail",
                            f"not wired: {b['file']} is missing", "Run ./install.sh (Doctor › Apply hotkey)."))
    elif b["stale"]:
        checks.append(check("binding", "Hotkey binding", "warn",
                            f"{b['hotkey']} → {b['script']} (a different checkout)", "Run ./install.sh from this repo."))
    else:
        checks.append(check("binding", "Hotkey binding", "ok", f"{b['hotkey']} → {b['script']} in {b['file']}"))
    for leftover in b["leftovers"]:
        checks.append(check(f"leftover-{leftover.replace(' ', '-')}", "Old paster block", "warn",
                            f"a '{leftover}' block is still in the i3 config", "Run ./install.sh — it removes older blocks."))

    # -- hotkey drift
    try:
        dump = bash_bridge.dump_config(paths)
        config_hotkey = dump.values.get("hotkey") or default_hotkey(flav)
        config_warnings = list(dump.warnings)
    except bash_bridge.BridgeError as exc:
        config_hotkey, config_warnings = None, [str(exc)]
    drift = bool(b["present"] and config_hotkey and b["hotkey"] and b["hotkey"] != config_hotkey)
    if drift:
        checks.append(check("hotkey", "Hotkey", "warn",
                            f"config.yaml says {config_hotkey}, the i3 binding is {b['hotkey']}",
                            "Apply (runs ./install.sh) to rebind."))
    elif config_hotkey:
        checks.append(check("hotkey", "Hotkey", "ok", config_hotkey))

    # -- dependencies
    for binary, package in DEPS:
        found = probe.which(binary)
        if binary == "rofi" and found:
            ver = rofi_version(probe)
            if ver and ver < ROFI_MIN:
                checks.append(check("dep-rofi", "rofi", "warn", f"{'.'.join(map(str, ver))} < 1.6", "apt install rofi"))
                continue
            label = ".".join(map(str, ver)) if ver else "version unknown"
            checks.append(check("dep-rofi", "rofi", "ok", f"{found} ({label})"))
            continue
        checks.append(check(f"dep-{binary}", binary, "ok" if found else "fail",
                            found or "not found", None if found else f"sudo apt install {package} (or ./install.sh)"))

    # -- compositor
    comp = next((n for n in ("picom", "compton", "xcompmgr") if probe.process_running(n)), None)
    checks.append(check("compositor", "Compositor", "ok" if comp else "warn",
                        f"{comp}: real transparency" if comp else "none running — rofi uses pseudo-transparency",
                        None if comp else "Start picom for real alpha (optional)."))

    # -- state files
    for name in STATE_FILES:
        f = probe.runtime_dir / name
        if f.is_file():
            body = f.read_text(errors="replace").strip()[:60] if name != "paster.rasi" else "rendered theme"
            checks.append(check(f"state-{name}", name, "ok", f"{f} · {body}"))
        else:
            checks.append(check(f"state-{name}", name, "na", "absent"))

    # -- config warnings
    if config_warnings:
        for w in config_warnings:
            checks.append(check("config", "config.yaml", "warn", w, "Fix the value in Config."))
    else:
        checks.append(check("config", "config.yaml", "ok", "every value valid"))

    # -- entries health
    try:
        h = entries_store.health(paths)
        detail = f"{h['tabs']} tabs · {h['entries']} entries"
        problems = []
        if h["empty_tabs"]:
            problems.append(f"empty: {', '.join(h['empty_tabs'])}")
        if h["ignored"]:
            problems.append(f"ignored (no content.md): {', '.join(h['ignored'])}")
        if h["unlabeled"]:
            problems.append(f"skipped by rofi (empty label): {', '.join(h['unlabeled'])}")
        if h["duplicates"]:
            problems.append(f"{len(h['duplicates'])} duplicate line(s) across tabs")
        if h["long_lines"]:
            problems.append(f"{len(h['long_lines'])} line(s) over {entries_store.LONG_LINE} chars")
        checks.append(check("entries", "Entries", "warn" if problems else "ok",
                            detail + (" · " + "; ".join(problems) if problems else "")))
        health = h
    except bash_bridge.BridgeError as exc:
        checks.append(check("entries", "Entries", "fail", str(exc)))
        health = None

    # -- tests
    if last_test_run:
        ok = last_test_run.get("rc") == 0
        checks.append(check("tests", "Bash test suite", "ok" if ok else "fail",
                            f"last run {last_test_run.get('started', '')}: rc={last_test_run.get('rc')}"))
    else:
        checks.append(check("tests", "Bash test suite", "na", "not run from here yet"))

    # -- service
    under_systemd = bool(env.get("INVOCATION_ID"))
    port_file = paths.port_file.read_text().strip() if paths.port_file.is_file() else None
    checks.append(check("service", "Service", "ok",
                        f"{'systemd user unit' if under_systemd else 'foreground'} · port {port}"
                        f"{' (.port says ' + port_file + ')' if port_file and str(port) != port_file else ''}"))

    counts = {s: sum(1 for c in checks if c["status"] == s) for s in ("ok", "warn", "fail", "na")}
    return {"checks": checks, "summary": counts, "display": display, "flavour": flav,
            "binding": b, "config_hotkey": config_hotkey, "hotkey_drift": drift,
            "entries": health, "under_systemd": under_systemd}
