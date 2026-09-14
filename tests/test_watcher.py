import os

from modules import watcher


def bump(path):
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns + 1_000_000_000, st.st_mtime_ns + 1_000_000_000))


def test_scan_and_diff_report_each_kind_of_change(paths):
    before = watcher.scan(paths)
    assert watcher.diff(before, before) == ()
    bump(paths.entries_dir / "10_Coding" / "content.md")
    after = watcher.scan(paths)
    assert [e.name for e in watcher.diff(before, after)] == ["entries_changed"]
    assert watcher.diff(before, after)[0].payload == {"tab": "10_Coding"}
    bump(paths.config_file)
    (paths.entries_dir / "40_New").mkdir()
    (paths.entries_dir / "40_New" / "content.md").write_text("x\n")
    names = [e.name for e in watcher.diff(after, watcher.scan(paths))]
    assert names == ["config_changed", "tabs_changed"]


def test_poll_once_emits_and_advances(paths):
    seen = []
    w = watcher.Watcher(paths, lambda name, payload: seen.append((name, payload)), interval=0.01)
    assert w.poll_once() == ()
    bump(paths.config_file)
    assert [e.name for e in w.poll_once()] == ["config_changed"]
    assert w.poll_once() == ()
    assert seen == [("config_changed", {})]


def test_a_failing_emit_does_not_stop_the_poll(paths):
    def boom(*_):
        raise RuntimeError("socket gone")
    w = watcher.Watcher(paths, boom)
    bump(paths.config_file)
    assert [e.name for e in w.poll_once()] == ["config_changed"]


def test_mark_clean_forgets_a_pending_change(paths):
    w = watcher.Watcher(paths, lambda *_: None)
    bump(paths.config_file)
    w.mark_clean()
    assert w.poll_once() == ()
