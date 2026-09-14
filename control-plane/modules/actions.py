"""Desktop actions, gated (plan D7, §13): argv subprocesses with a timeout,
DISPLAY/XAUTHORITY from the server's own environment, I3SOCK re-resolved
per call, one run at a time per action and a cooldown after each.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .paths import Paths

COOLDOWN_S = 2.0
OUTPUT_CAP = 64_000
STATE_FILES = ("paster-prev-win", "paster-last-tab", "paster.rasi")


class ActionError(Exception):
    status = 400


class UnknownAction(ActionError):
    status = 404


class AlreadyRunning(ActionError):
    status = 409


class Cooldown(ActionError):
    status = 409

    def __init__(self, name: str, seconds_left: float):
        super().__init__(f"{name} ran a moment ago — try again in {seconds_left:.0f}s")
        self.seconds_left = seconds_left


class NoDisplay(ActionError):
    status = 503


@dataclass(frozen=True)
class Spec:
    name: str
    title: str
    description: str
    argv: Callable[[Paths], list]      # None → handled in-process
    timeout: int
    needs_display: bool


@dataclass(frozen=True)
class Result:
    name: str
    rc: int
    output: str
    started: str
    duration_s: float
    timed_out: bool = False

    def as_dict(self) -> dict:
        return {"name": self.name, "rc": self.rc, "output": self.output, "started": self.started,
                "duration_s": round(self.duration_s, 3), "timed_out": self.timed_out, "ok": self.rc == 0}


SPECS = {
    "open_popup": Spec("open_popup", "Open the popup", "Runs bin/toggle.sh — the real rofi popup, on the laptop's screen.",
                       lambda p: ["bash", str(p.toggle_script)], 5, True),
    "apply_install": Spec("apply_install", "Apply hotkey (install.sh)",
                          "Runs ./install.sh: rewrites the i3 binding from config.yaml and reloads i3.",
                          lambda p: ["bash", str(p.install_script)], 120, True),
    "run_tests": Spec("run_tests", "Run the bash tests", "Runs tests/run.sh (config, paste-back, list-tabs).",
                      lambda p: ["bash", str(p.tests_runner)], 120, False),
    "clear_state": Spec("clear_state", "Clear stale state",
                        "Deletes paster-prev-win, paster-last-tab and the rendered paster.rasi in $XDG_RUNTIME_DIR.",
                        None, 5, False),
}


class ActionRunner:
    def __init__(self, paths: Paths, *, env_provider: Callable[[], dict] | None = None,
                 clock: Callable[[], float] = time.monotonic, runner=subprocess.run,
                 cooldown_s: float = COOLDOWN_S, runtime_dir: str | None = None):
        self._paths = paths
        self._env = env_provider or (lambda: dict(os.environ))
        self._clock = clock
        self._runner = runner
        self._cooldown = cooldown_s
        self._runtime_dir = runtime_dir
        self._locks = {name: threading.Lock() for name in SPECS}
        self._last_end: dict = {}
        self._last: dict = {}

    # -- introspection ------------------------------------------------------
    def available(self) -> list:
        env = self._env()
        out = []
        for spec in SPECS.values():
            reason = None
            if spec.needs_display and not env.get("DISPLAY"):
                reason = "no DISPLAY in the server's environment"
            argv = spec.argv(self._paths) if spec.argv else ["(in-process)"]
            out.append({"name": spec.name, "title": spec.title, "description": spec.description,
                        "argv": argv, "enabled": reason is None, "reason": reason,
                        "running": self._locks[spec.name].locked(),
                        "last": self._last[spec.name].as_dict() if spec.name in self._last else None})
        return out

    def last(self, name: str) -> Result | None:
        return self._last.get(name)

    # -- running --------------------------------------------------------------
    def run(self, name: str) -> Result:
        spec = SPECS.get(name)
        if spec is None:
            raise UnknownAction(f"unknown action: {name!r}")
        env = self._env()
        if spec.needs_display and not env.get("DISPLAY"):
            raise NoDisplay(f"{spec.title}: no DISPLAY in the server's environment")
        lock = self._locks[name]
        if not lock.acquire(blocking=False):
            raise AlreadyRunning(f"{name} is already running")
        try:
            left = self._cooldown - (self._clock() - self._last_end.get(name, -1e9))
            if left > 0:
                raise Cooldown(name, left)
            result = self._clear_state() if spec.argv is None else self._subprocess(spec, env)
            self._last[name] = result
            return result
        finally:
            self._last_end[name] = self._clock()
            lock.release()

    def _subprocess(self, spec: Spec, env: dict) -> Result:
        env = self._fresh_i3sock(dict(env))
        started = datetime.now(timezone.utc).isoformat()
        t0 = self._clock()
        argv = spec.argv(self._paths)
        try:
            proc = self._runner(argv, capture_output=True, text=True, timeout=spec.timeout,
                                env=env, cwd=str(self._paths.repo_root), check=False)
            rc, output, timed_out = proc.returncode, (proc.stdout or "") + (proc.stderr or ""), False
        except subprocess.TimeoutExpired as exc:
            rc, timed_out = -1, True
            output = _text(exc.stdout) + _text(exc.stderr) + f"\n[timed out after {spec.timeout}s]"
        except OSError as exc:
            rc, output, timed_out = 127, str(exc), False
        return Result(spec.name, rc, output[-OUTPUT_CAP:], started, self._clock() - t0, timed_out)

    def _fresh_i3sock(self, env: dict) -> dict:
        """I3SOCK carries i3's pid in its name and goes stale on an i3 restart;
        ask i3 for the current one under this DISPLAY, or drop the stale value."""
        env.pop("I3SOCK", None)
        if not env.get("DISPLAY"):
            return env
        try:
            proc = self._runner(["i3", "--get-socketpath"], capture_output=True, text=True,
                                timeout=5, env=env, check=False)
            path = (proc.stdout or "").strip()
            if proc.returncode == 0 and path.startswith("/"):
                env["I3SOCK"] = path
        except (OSError, subprocess.TimeoutExpired):
            pass
        return env

    def _clear_state(self) -> Result:
        started = datetime.now(timezone.utc).isoformat()
        t0 = self._clock()
        root = self._runtime_dir or self._env().get("XDG_RUNTIME_DIR") or "/tmp"
        removed = []
        for name in STATE_FILES:
            target = os.path.join(root, name)
            try:
                os.unlink(target)
                removed.append(name)
            except FileNotFoundError:
                pass
            except OSError as exc:
                return Result("clear_state", 1, f"could not remove {target}: {exc}", started, self._clock() - t0)
        return Result("clear_state", 0, f"removed: {', '.join(removed) or 'nothing (already clean)'}",
                      started, self._clock() - t0)


def _text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
