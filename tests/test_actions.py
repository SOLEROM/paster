import re
import threading

import pytest

from conftest import REPO_ROOT
from modules import actions
from fakes import FakeRunner


def runner_for(paths, fake, *, display=":1", clock=None, tmp=None):
    env = {"DISPLAY": display, "I3SOCK": "/stale/sock"} if display else {}
    kwargs = {"env_provider": lambda: dict(env), "runner": fake}
    if clock:
        kwargs["clock"] = clock
    if tmp:
        kwargs["runtime_dir"] = str(tmp)
    return actions.ActionRunner(paths, **kwargs)


def test_open_popup_runs_toggle_sh_with_a_fresh_i3sock(paths):
    fake = FakeRunner()
    result = runner_for(paths, fake).run("open_popup")
    assert result.rc == 0 and result.output == "ok" and result.name == "open_popup"
    argv, kwargs = fake.calls[-1]
    assert argv == ["bash", str(paths.toggle_script)]
    assert kwargs["env"]["I3SOCK"] == "/run/i3/sock" and kwargs["timeout"] == 5
    assert kwargs["cwd"] == str(paths.repo_root)


def test_a_stale_i3sock_is_dropped_when_i3_does_not_answer(paths):
    fake = FakeRunner(i3sock=None)
    runner_for(paths, fake).run("apply_install")
    assert "I3SOCK" not in fake.calls[-1][1]["env"]
    assert fake.calls[-1][0] == ["bash", str(paths.install_script)]


def test_display_gating(paths):
    fake = FakeRunner()
    r = runner_for(paths, fake, display="")
    with pytest.raises(actions.NoDisplay):
        r.run("open_popup")
    assert r.run("run_tests").rc == 0                 # no display needed
    assert fake.calls[-1][0] == ["bash", str(paths.tests_runner)]
    avail = {a["name"]: a for a in r.available()}
    assert avail["open_popup"]["enabled"] is False and "DISPLAY" in avail["open_popup"]["reason"]
    assert avail["run_tests"]["enabled"] is True and avail["clear_state"]["argv"] == ["(in-process)"]


def test_unknown_action(paths):
    with pytest.raises(actions.UnknownAction):
        runner_for(paths, FakeRunner()).run("rm_rf")


def test_one_at_a_time(paths):
    fake = FakeRunner(sleep=0.4)
    r = runner_for(paths, fake)
    results = []
    t = threading.Thread(target=lambda: results.append(r.run("run_tests")))
    t.start()
    assert fake.started.wait(2)
    with pytest.raises(actions.AlreadyRunning):
        r.run("run_tests")
    t.join()
    assert results[0].rc == 0
    assert len([c for c in fake.calls if c[0][-1].endswith("run.sh")]) == 1


def test_cooldown_after_a_run(paths):
    now = [100.0]
    r = runner_for(paths, FakeRunner(), clock=lambda: now[0])
    r.run("run_tests")
    with pytest.raises(actions.Cooldown) as exc:
        r.run("run_tests")
    assert 0 < exc.value.seconds_left <= 2
    now[0] += 3
    assert r.run("run_tests").rc == 0


def test_timeout_and_oserror_are_reported_not_raised(paths):
    r = runner_for(paths, FakeRunner(raise_timeout=True))
    res = r.run("run_tests")
    assert res.timed_out and res.rc == -1 and "timed out" in res.output and res.output.startswith("partial")
    r2 = runner_for(paths, FakeRunner(raise_oserror=True))
    assert r2.run("run_tests").rc == 127


def test_clear_state_removes_the_runtime_files(paths, tmp_path):
    for name in ("paster-prev-win", "paster-last-tab"):
        (tmp_path / name).write_text("x")
    r = runner_for(paths, FakeRunner(), tmp=tmp_path)
    res = r.run("clear_state")
    assert res.rc == 0 and "paster-prev-win, paster-last-tab" in res.output
    assert not (tmp_path / "paster-last-tab").exists()
    assert r.last("clear_state").as_dict()["ok"] is True


def test_no_shell_true_anywhere_in_the_modules():
    for path in (REPO_ROOT / "control-plane" / "modules").glob("*.py"):
        assert not re.search(r"shell\s*=\s*True", path.read_text()), path.name
        assert "os.system(" not in path.read_text(), path.name
