"""The bridge runs the real scripts (no X) and reports what they say."""
import pytest

from modules import bash_bridge
from modules.paths import for_repo_copy


def test_list_tabs_reads_the_copy(paths):
    rows = bash_bridge.list_tabs(paths)
    assert [label for label, _ in rows] == ["Coding", "Writing", "General"]
    assert all(folder.parent == paths.entries_dir for _, folder in rows)


def test_list_tabs_with_no_entries_dir_is_empty(tmp_path):
    paths = for_repo_copy(tmp_path / "nope", tmp_path / "data")
    assert bash_bridge.list_tabs(paths) == ()


def test_dump_config_returns_effective_values_and_warnings(paths):
    paths.config_file.write_text('width_pct: 999\nbackground: "#10141a"\nauto_paste: yes\n')
    dump = bash_bridge.dump_config(paths)
    assert dump.values["width_pct"] == "100"          # invalid → default
    assert dump.values["background"] == "#10141a"
    assert dump.values["auto_paste"] == "true"        # yes → true
    assert dump.values["terminal_classes"].startswith("alacritty|")
    assert any("width_pct" in w for w in dump.warnings)
    assert not any("background" in w for w in dump.warnings)


def test_dump_config_of_the_shipped_file_has_no_warnings(paths):
    dump = bash_bridge.dump_config(paths)
    assert dump.warnings == ()
    assert set(dump.values) >= {"hotkey", "width_pct", "height_pct", "opacity_pct", "font_size",
                                "border_px", "background", "foreground", "auto_paste",
                                "paste_delay_ms", "paste_key", "terminal_paste_key",
                                "terminal_classes", "press_enter"}


def test_a_missing_script_is_a_bridge_error(tmp_path):
    paths = for_repo_copy(tmp_path, tmp_path / "data", bin_dir=tmp_path / "nobin")
    with pytest.raises(bash_bridge.BridgeError):
        bash_bridge.list_tabs(paths)
