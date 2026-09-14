import pytest

from modules import entries_store as es
from modules import fileio


def ids(paths):
    return [t.id for t in es.list_tabs(paths).tabs]


def test_list_tabs_reports_labels_counts_and_ignored(paths):
    (paths.entries_dir / "40_NoContent").mkdir()
    (paths.entries_dir / "50_,,").mkdir()
    (paths.entries_dir / "50_,," / "content.md").write_text("x\n")
    listing = es.list_tabs(paths)
    assert [(t.id, t.label, t.count) for t in listing.tabs] == [
        ("10_Coding", "Coding", 5), ("20_Writing", "Writing", 4), ("30_General", "General", 4)]
    assert listing.ignored == ("40_NoContent",)
    assert listing.unlabeled == ("50_,,",)


def test_read_tab_drops_blank_lines_and_cr(paths):
    (paths.entries_dir / "10_Coding" / "content.md").write_text("a\r\n\n  \nb\n")
    assert es.read_tab(paths, "10_Coding").lines == ("a", "b")


@pytest.mark.parametrize("bad", ["../10_Coding", "/etc", ".git", "", "nope", "10_Coding/.."])
def test_unknown_or_unsafe_ids_are_not_found(paths, bad):
    with pytest.raises(es.NotFound):
        es.read_tab(paths, bad)


def test_write_tab_round_trips_byte_exact_except_the_edit(paths):
    tab = es.read_tab(paths, "10_Coding")
    lines = list(tab.lines)
    lines[1] = "Refactor it, keep behaviour"
    es.write_tab(paths, "10_Coding", lines, tab.rev)
    text = (paths.entries_dir / "10_Coding" / "content.md").read_text()
    assert text == "".join(f"{l}\n" for l in lines)


def test_write_tab_refuses_stale_rev_newlines_and_non_strings(paths):
    tab = es.read_tab(paths, "10_Coding")
    with pytest.raises(es.Invalid):
        es.write_tab(paths, "10_Coding", ["a\nb"], tab.rev)
    with pytest.raises(es.Invalid):
        es.write_tab(paths, "10_Coding", [1], tab.rev)
    with pytest.raises(es.Invalid):
        es.write_tab(paths, "10_Coding", "not a list", tab.rev)
    with pytest.raises(es.Invalid):
        es.write_tab(paths, "10_Coding", ["x" * 5000], tab.rev)
    es.write_tab(paths, "10_Coding", ["fresh"], tab.rev)
    with pytest.raises(fileio.StaleRevision):
        es.write_tab(paths, "10_Coding", ["stale"], tab.rev)
    assert es.read_tab(paths, "10_Coding").lines == ("fresh",)


def test_every_write_is_snapshotted(paths):
    from modules import history
    tab = es.read_tab(paths, "10_Coding")
    es.write_tab(paths, "10_Coding", ["one"], tab.rev)
    snaps = history.list_snapshots(paths, "entries/10_Coding/content.md")
    assert len(snaps) == 1
    assert "Explain this code" in history.read_snapshot(paths, "entries/10_Coding/content.md", snaps[0].ts)


def test_create_tab_appends_with_the_next_prefix(paths):
    new, renames = es.create_tab(paths, "Prompts")
    assert new == "40_Prompts" and renames == ()
    assert (paths.entries_dir / new / "content.md").read_text() == ""
    assert ids(paths)[-1] == "40_Prompts"


def test_create_tab_after_renumbers_the_rest(paths):
    new, renames = es.create_tab(paths, "Mid", after="10_Coding")
    assert new == "20_Mid"
    assert dict(renames) == {"20_Writing": "30_Writing", "30_General": "40_General"}
    assert ids(paths) == ["10_Coding", "20_Mid", "30_Writing", "40_General"]
    assert (paths.entries_dir / "30_Writing" / "content.md").read_text().startswith("Summarize")


def test_create_tab_refuses_bad_names_and_label_clashes(paths):
    with pytest.raises(es.Invalid):
        es.create_tab(paths, "../x")
    with pytest.raises(es.Conflict):
        es.create_tab(paths, "Coding")
    with pytest.raises(es.NotFound):
        es.create_tab(paths, "Ok", after="99_Nope")
    assert ids(paths) == ["10_Coding", "20_Writing", "30_General"]


def test_rename_tab_keeps_the_prefix(paths):
    assert es.rename_tab(paths, "20_Writing", "Prose") == "20_Prose"
    assert ids(paths) == ["10_Coding", "20_Prose", "30_General"]
    assert es.rename_tab(paths, "20_Prose", "Prose") == "20_Prose"
    with pytest.raises(es.Conflict):
        es.rename_tab(paths, "20_Prose", "General")


def test_reorder_tabs_renumbers_through_temp_names(paths):
    plan = es.reorder_tabs(paths, ["30_General", "10_Coding", "20_Writing"])
    assert dict(plan) == {"30_General": "10_General", "10_Coding": "20_Coding", "20_Writing": "30_Writing"}
    assert ids(paths) == ["10_General", "20_Coding", "30_Writing"]
    assert es.read_tab(paths, "10_General").lines[0].startswith("Write one concise Git commit")
    assert not [p for p in paths.entries_dir.iterdir() if p.name.startswith(".renaming")]


def test_reorder_needs_every_tab_exactly_once(paths):
    for bad in [["10_Coding"], ["10_Coding", "10_Coding", "20_Writing"], "10_Coding", ["10_Coding", "20_Writing", "99_X"]]:
        with pytest.raises(es.Invalid):
            es.reorder_tabs(paths, bad)


def test_delete_tab_moves_to_trash(paths):
    target = es.delete_tab(paths, "20_Writing")
    assert target.parent == paths.trash_dir and target.name.endswith("_20_Writing")
    assert (target / "content.md").is_file()
    assert ids(paths) == ["10_Coding", "30_General"]
    with pytest.raises(es.NotFound):
        es.delete_tab(paths, "20_Writing")


def test_move_entry_between_tabs_is_all_or_nothing(paths):
    src, dst = es.read_tab(paths, "10_Coding"), es.read_tab(paths, "20_Writing")
    moved = src.lines[0]
    es.move_entry(paths, "10_Coding", 0, "20_Writing", 1, src.rev, dst.rev)
    assert es.read_tab(paths, "10_Coding").lines == src.lines[1:]
    assert es.read_tab(paths, "20_Writing").lines[1] == moved
    # stale target rev: nothing changes in either file
    src2 = es.read_tab(paths, "10_Coding")
    with pytest.raises(fileio.StaleRevision):
        es.move_entry(paths, "10_Coding", 0, "20_Writing", None, src2.rev, dst.rev)
    assert es.read_tab(paths, "10_Coding").lines == src2.lines
    with pytest.raises(es.Invalid):
        es.move_entry(paths, "10_Coding", 99, "20_Writing", None, None, None)
    with pytest.raises(es.Invalid):
        es.move_entry(paths, "10_Coding", 0, "10_Coding", None, None, None)


def test_search_is_case_insensitive_across_tabs(paths):
    hits = es.search(paths, "the following")
    assert {h.tab for h in hits} == {"10_Coding", "20_Writing", "30_General"}
    assert all("the following" in h.line.lower() for h in hits)
    assert len(es.search(paths, "")) == 13


def test_health_reports_duplicates_long_lines_and_empty_tabs(paths):
    es.create_tab(paths, "Empty")
    tab = es.read_tab(paths, "10_Coding")
    es.write_tab(paths, "10_Coding", list(tab.lines) + ["Translate the following text to English", "x" * 301], tab.rev)
    h = es.health(paths)
    assert h["tabs"] == 4 and h["empty_tabs"] == ["40_Empty"]
    assert h["duplicates"][0]["tabs"] == ["10_Coding", "30_General"]
    assert h["long_lines"][0]["tab"] == "10_Coding"


def test_move_entry_rolls_the_source_back_when_the_target_write_fails(paths, monkeypatch):
    src, dst = es.read_tab(paths, "10_Coding"), es.read_tab(paths, "20_Writing")
    real = fileio.checked_write
    calls = []

    def flaky(p, relpath, text, base_rev, **kw):
        calls.append(relpath)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(p, relpath, text, base_rev, **kw)

    monkeypatch.setattr(fileio, "checked_write", flaky)
    with pytest.raises(OSError):
        es.move_entry(paths, "10_Coding", 0, "20_Writing", None, src.rev, dst.rev)
    assert es.read_tab(paths, "10_Coding").lines == src.lines
    assert es.read_tab(paths, "20_Writing").lines == dst.lines


def test_search_and_health_spawn_bash_once(paths, monkeypatch):
    from modules import bash_bridge
    real = bash_bridge.list_tabs
    calls = []
    monkeypatch.setattr(bash_bridge, "list_tabs", lambda p: (calls.append(1), real(p))[1])
    es.search(paths, "the")
    assert len(calls) == 1
    calls.clear()
    es.health(paths)
    assert len(calls) == 1
