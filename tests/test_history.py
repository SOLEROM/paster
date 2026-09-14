from modules import fileio, history


def test_snapshot_ring_keeps_the_last_fifty(paths):
    rel = "entries/10_Coding/content.md"
    for i in range(55):
        fileio.checked_write(paths, rel, f"line {i}\n", None)
    snaps = history.list_snapshots(paths, rel)
    assert len(snaps) == history.RING
    newest = history.read_snapshot(paths, rel, snaps[0].ts)
    assert newest == "line 53\n"          # the version replaced by the last write


def test_snapshot_of_a_missing_file_is_none(paths):
    assert history.snapshot(paths, "config.yaml", paths.config_file.with_name("absent")) is None


def test_read_snapshot_refuses_path_tricks(paths):
    import pytest
    for ts in ["../x", "..", ".hidden", "", "a/b"]:
        with pytest.raises(FileNotFoundError):
            history.read_snapshot(paths, "config.yaml", ts)


def test_checked_write_refuses_a_stale_rev(paths):
    import pytest
    rel = "config.yaml"
    _, rev = fileio.read_text(paths.config_file)
    fileio.checked_write(paths, rel, "hotkey: x\n", rev)
    with pytest.raises(fileio.StaleRevision) as exc:
        fileio.checked_write(paths, rel, "hotkey: y\n", rev)
    assert exc.value.current == fileio.rev_of(b"hotkey: x\n")
    assert paths.config_file.read_text() == "hotkey: x\n"


def test_checked_write_is_atomic_and_leaves_no_temp(paths):
    fileio.checked_write(paths, "config.yaml", "a: 1\n", None)
    assert [p.name for p in paths.repo_root.iterdir() if p.name.startswith(".config")] == []


def test_resolve_relpath_confines(paths):
    import pytest
    assert fileio.resolve_relpath(paths, "config.yaml") == paths.config_file
    assert fileio.resolve_relpath(paths, "entries/10_Coding/content.md") == paths.entries_dir / "10_Coding" / "content.md"
    for bad in ["entries/../config.yaml", "/etc/passwd", "entries/.git/content.md", "entries/x/y/content.md",
                "entries/10_Coding/other.md", "README.md", "entries/a/b/../content.md"]:
        with pytest.raises(fileio.BadRelpath):
            fileio.resolve_relpath(paths, bad)
