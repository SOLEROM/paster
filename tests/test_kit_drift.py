"""The kit copy-ins under control-plane/static are refreshed by run.sh and
never edited here (plan D2). Each kit's installer has a --verify mode that
reports a copy that has drifted; on a bench host a skip here is a failed
check (run pytest -rs).
"""
import subprocess
from pathlib import Path

import pytest

from conftest import REPO_ROOT, solbench_home

STATIC = REPO_ROOT / "control-plane" / "static"


def run_verify(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=300)


def test_4colthems_copy_matches_the_kit():
    kit = solbench_home() / "4ColThems"
    proc = run_verify([str(kit / "install.sh"), "--verify", "--css", str(STATIC / "css"),
                       "--js", str(STATIC / "js"), "--data", str(STATIC), "--py", str(STATIC)])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_vscodefront_copy_matches_the_kit():
    kit = solbench_home() / "vsCodeFront"
    proc = run_verify([str(kit / "install.sh"), "--verify", "--static", str(STATIC)])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cldbar_copy_is_not_a_local_fork():
    kit = solbench_home() / "cldBar"
    assert (STATIC / "js" / "cldbar.js").read_bytes() == (kit / "cldbar.js").read_bytes()


@pytest.mark.parametrize("name", ["socket.io.min.js", "marked.min.js", "purify.min.js"])
def test_vendor_files_come_from_the_skeleton(name):
    src = solbench_home() / "vsCodeFront" / "skeleton" / "static" / "vendor" / name
    assert (STATIC / "vendor" / name).read_bytes() == src.read_bytes()
