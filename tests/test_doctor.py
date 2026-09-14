from modules import doctor
from fakes import make_probe, write_dropin


def by_id(report, id):
    return next(c for c in report["checks"] if c["id"] == id)


def test_all_green_on_a_healthy_regolith_host(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    rt.mkdir()
    write_dropin(home, "Ctrl+space", str(paths.toggle_script))
    report = doctor.run_checks(paths, make_probe(home, rt), port=6012)
    assert report["summary"]["fail"] == 0 and report["summary"]["warn"] == 0, report["checks"]
    assert report["flavour"] == "regolith" and report["display"] is True
    assert by_id(report, "binding")["detail"].startswith("Ctrl+space → ")
    assert by_id(report, "hotkey")["detail"] == "Ctrl+space"
    assert by_id(report, "dep-rofi")["detail"].endswith("(1.7.5)")
    assert by_id(report, "compositor")["detail"] == "picom: real transparency"
    assert by_id(report, "state-paster-last-tab")["status"] == "na"
    assert report["entries"]["tabs"] == 3


def test_missing_dropin_is_the_fail_this_host_showed(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    (home / ".config" / "regolith3" / "i3" / "config.d").mkdir(parents=True)
    report = doctor.run_checks(paths, make_probe(home, rt))
    b = by_id(report, "binding")
    assert b["status"] == "fail" and "90_paster" in b["detail"] and "install.sh" in b["fix"]
    assert report["hotkey_drift"] is False


def test_a_dropin_pointing_at_another_checkout_is_stale(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    write_dropin(home, "Ctrl+space", str(tmp_path / "old" / "bin" / "toggle.sh"))
    report = doctor.run_checks(paths, make_probe(home, rt))
    assert by_id(report, "binding")["status"] == "warn"
    assert "different checkout" in by_id(report, "binding")["detail"]


def test_hotkey_drift_between_config_and_binding(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    write_dropin(home, "Mod4+p", str(paths.toggle_script))
    report = doctor.run_checks(paths, make_probe(home, rt))
    assert report["hotkey_drift"] is True
    assert by_id(report, "hotkey")["status"] == "warn"
    assert "config.yaml says Ctrl+space" in by_id(report, "hotkey")["detail"]


def test_plain_i3_block_and_leftovers(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    cfg = home / ".config" / "i3" / "config"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("# >>> paster v1 >>>\nbindsym Mod1+p exec x\n# <<< paster v1 <<<\n"
                   f"# >>> paster v3 >>>\nbindsym Mod1+p exec --no-startup-id {paths.toggle_script}\n# <<< paster v3 <<<\n")
    report = doctor.run_checks(paths, make_probe(home, rt))
    assert report["flavour"] == "plain"
    assert by_id(report, "binding")["status"] == "ok"
    assert by_id(report, "leftover-paster-v1")["status"] == "warn"
    # config.yaml says Ctrl+space, the block binds Mod1+p: that is drift
    assert by_id(report, "hotkey")["status"] == "warn" and report["hotkey_drift"] is True


def test_session_and_display_states(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    wl = doctor.run_checks(paths, make_probe(home, rt, env={"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}))
    assert by_id(wl, "session")["status"] == "fail"
    nod = doctor.run_checks(paths, make_probe(home, rt, env={}))
    assert by_id(nod, "session")["status"] == "warn" and nod["display"] is False


def test_dependencies_and_compositor(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    probe = make_probe(home, rt, found={"rofi", "xdotool"}, procs={"i3"}, rofi_out="Version: 1.5.4")
    report = doctor.run_checks(paths, probe)
    assert by_id(report, "dep-rofi")["status"] == "warn" and "< 1.6" in by_id(report, "dep-rofi")["detail"]
    assert by_id(report, "dep-xclip")["status"] == "fail" and "apt install xclip" in by_id(report, "dep-xclip")["fix"]
    assert by_id(report, "dep-xprop")["fix"].startswith("sudo apt install x11-utils")
    assert by_id(report, "compositor")["status"] == "warn"
    none = doctor.run_checks(paths, make_probe(home, rt, found=set(), procs=set()))
    assert by_id(none, "dep-rofi")["status"] == "fail" and by_id(none, "i3")["status"] == "fail"


def test_state_files_config_warnings_entries_and_service(paths, tmp_path):
    home, rt = tmp_path / "home", tmp_path / "rt"
    rt.mkdir()
    (rt / "paster-last-tab").write_text("Coding\n")
    (rt / "paster.rasi").write_text("* {}")
    paths.config_file.write_text("width_pct: 999\n")
    (paths.entries_dir / "40_Empty").mkdir()
    (paths.entries_dir / "40_Empty" / "content.md").write_text("")
    (paths.entries_dir / "50_NoContent").mkdir()
    probe = make_probe(home, rt, env={"DISPLAY": ":1", "INVOCATION_ID": "abc"})
    report = doctor.run_checks(paths, probe, port=6012, last_test_run={"rc": 0, "started": "now"})
    assert by_id(report, "state-paster-last-tab")["detail"].endswith("Coding")
    assert by_id(report, "state-paster.rasi")["detail"].endswith("rendered theme")
    assert by_id(report, "config")["status"] == "warn" and "width_pct" in by_id(report, "config")["detail"]
    e = by_id(report, "entries")
    assert e["status"] == "warn" and "empty: 40_Empty" in e["detail"] and "ignored" in e["detail"]
    assert by_id(report, "tests")["status"] == "ok"
    assert report["under_systemd"] is True and "systemd user unit" in by_id(report, "service")["detail"]
    assert by_id(report, "hotkey")["detail"] == "Mod1+p"      # empty hotkey → the plain-i3 default


def test_default_probe_reads_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    probe = doctor.default_probe()
    assert probe.runtime_dir == tmp_path and probe.which("bash")
    rc, out = probe.run(["bash", "-c", "echo hi"])
    assert rc == 0 and out.strip() == "hi"
    assert probe.run(["/nonexistent/binary"])[0] == 127
