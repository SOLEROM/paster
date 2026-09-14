"""Where everything lives — one frozen record, built once, passed around.

No module builds a path from a literal: the repo knows only itself
(``Path(__file__)``), the data dir comes from ``PASTER_DATA_DIR`` or
``~/.paster`` (solBench plans/benchLayoutPlan.md §1). Tests build a record
that points ``entries_dir``/``config_file`` at a temporary copy while the
scripts under ``bin/`` stay the real ones.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE = REPO_ROOT / "control-plane"
DATA_DIR_ENV = "PASTER_DATA_DIR"


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    bin_dir: Path
    entries_dir: Path
    config_file: Path
    data_dir: Path
    static_dir: Path
    templates_dir: Path
    man_dir: Path
    tests_dir: Path

    @property
    def toggle_script(self) -> Path:
        return self.bin_dir / "toggle.sh"

    @property
    def lib_config(self) -> Path:
        return self.bin_dir / "lib-config.sh"

    @property
    def install_script(self) -> Path:
        return self.repo_root / "install.sh"

    @property
    def tests_runner(self) -> Path:
        return self.tests_dir / "run.sh"

    @property
    def port_file(self) -> Path:
        return self.repo_root / ".port"

    @property
    def history_dir(self) -> Path:
        return self.data_dir / "history"

    @property
    def trash_dir(self) -> Path:
        return self.data_dir / "trash"


def default_paths(repo_root: Path = REPO_ROOT, data_dir: Path | None = None) -> Paths:
    data = data_dir or Path(os.environ.get(DATA_DIR_ENV) or (Path.home() / ".paster"))
    return Paths(
        repo_root=repo_root,
        bin_dir=repo_root / "bin",
        entries_dir=repo_root / "entries",
        config_file=repo_root / "config.yaml",
        data_dir=Path(data).expanduser(),
        static_dir=CONTROL_PLANE / "static",
        templates_dir=CONTROL_PLANE / "templates",
        man_dir=repo_root / "man",
        tests_dir=repo_root / "tests",
    )


def for_repo_copy(copy_root: Path, data_dir: Path, *, bin_dir: Path | None = None,
                  tests_dir: Path | None = None) -> Paths:
    """A record for a copy of ``entries/`` + ``config.yaml`` (tests), with the
    real scripts unless told otherwise."""
    base = default_paths(REPO_ROOT, data_dir)
    return replace(base, repo_root=copy_root, entries_dir=copy_root / "entries",
                   config_file=copy_root / "config.yaml",
                   bin_dir=bin_dir or base.bin_dir, tests_dir=tests_dir or base.tests_dir)
