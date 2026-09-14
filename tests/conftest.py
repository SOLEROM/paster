"""Shared fixtures: a temporary copy of entries/ + config.yaml, the real
scripts under bin/, and an app whose data dir is inside tmp_path — nothing
in a developer's ~/.paster is ever touched by the suite.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = REPO_ROOT / "control-plane"
sys.path.insert(0, str(CONTROL_PLANE))

from modules import paths as paths_mod  # noqa: E402

CSRF = {"X-Requested-With": "paster"}


def solbench_home() -> Path:
    """The solBench checkout: $SOLBENCH_HOME › the sibling ../solBench (bench layout)."""
    env = os.environ.get("SOLBENCH_HOME")
    root = Path(env) if env else REPO_ROOT.parent / "solBench"
    if not (root / "webterm" / "pyproject.toml").is_file():
        if env:  # explicitly set but wrong: a broken host, not a missing kit
            pytest.fail(f"SOLBENCH_HOME={env} is not a solBench checkout")
        pytest.skip("solBench checkout not found beside this repo — set SOLBENCH_HOME",
                    allow_module_level=True)
    return root


@pytest.fixture
def paths(tmp_path):
    copy = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "entries", copy / "entries")
    shutil.copy(REPO_ROOT / "config.yaml", copy / "config.yaml")
    return paths_mod.for_repo_copy(copy, tmp_path / "data")


@pytest.fixture
def app(paths, monkeypatch):
    monkeypatch.delenv("BENCH_SHELL_ORIGINS", raising=False)
    monkeypatch.delenv("PASTER_REMDEV_URL", raising=False)
    from server import create_app
    application, _socketio = create_app(paths, use_webterm=False)
    application.testing = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def write_config(paths, text: str) -> None:
    paths.config_file.write_text(text, encoding="utf-8")
