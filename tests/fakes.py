"""Test doubles shared by the doctor/action/route tests."""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from modules import doctor


def make_probe(home: Path, runtime_dir: Path, *, env: dict | None = None, found: set | None = None,
               procs: set | None = None, rofi_out: str = "Version: 1.7.5", i3_ok: bool = True) -> doctor.Probe:
    found = {"rofi", "xdotool", "xclip", "xprop", "i3"} if found is None else found
    procs = {"i3", "picom"} if procs is None else procs
    env = {"DISPLAY": ":1", "XDG_SESSION_TYPE": "x11"} if env is None else env

    def run(argv):
        if argv[:2] == ["rofi", "-version"]:
            return 0, rofi_out
        if argv == ["i3", "--get-socketpath"]:
            return (0, "/run/user/1000/i3/ipc-socket.1\n") if i3_ok else (1, "")
        return 127, "unknown"

    return doctor.Probe(env=env, home=home, runtime_dir=runtime_dir,
                        which=lambda b: f"/usr/bin/{b}" if b in found else None,
                        run=run, process_running=lambda n: n in procs)


def write_dropin(home: Path, hotkey: str, script: str) -> Path:
    dropin = home / ".config" / "regolith3" / "i3" / "config.d" / "90_paster"
    dropin.parent.mkdir(parents=True, exist_ok=True)
    dropin.write_text(f"# >>> paster v3 >>>\nbindsym {hotkey} exec --no-startup-id {script}\n# <<< paster v3 <<<\n")
    return dropin


class FakeRunner:
    """A subprocess.run stand-in: records calls, answers per argv[0..1]."""

    def __init__(self, *, sleep: float = 0.0, rc: int = 0, out: str = "ok", i3sock: str | None = "/run/i3/sock",
                 raise_timeout: bool = False, raise_oserror: bool = False):
        self.calls = []
        self.sleep, self.rc, self.out = sleep, rc, out
        self.i3sock, self.raise_timeout, self.raise_oserror = i3sock, raise_timeout, raise_oserror
        self.started = threading.Event()

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if argv == ["i3", "--get-socketpath"]:
            return subprocess.CompletedProcess(argv, 0 if self.i3sock else 1, (self.i3sock or "") + "\n", "")
        self.started.set()
        if self.raise_oserror:
            raise OSError("no such binary")
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 0), output="partial", stderr="")
        if self.sleep:
            time.sleep(self.sleep)
        return subprocess.CompletedProcess(argv, self.rc, self.out, "")
