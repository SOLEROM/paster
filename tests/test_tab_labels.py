"""tab_labels.py mirrors toggle.sh; the bridge is the truth (plan D4)."""
import pytest

from modules import bash_bridge, tab_labels
from modules.paths import for_repo_copy


@pytest.mark.parametrize("folder,label", [
    ("10_Coding", "Coding"), ("Coding", "Coding"), ("007_A,B:C'D\"E", "ABCDE"),
    ("10_", ""), ("10_,,", ""), ("40_10_Foo", "10_Foo"), ("3_x y", "x y"),
])
def test_label_for(folder, label):
    assert tab_labels.label_for(folder) == label


def test_labels_for_orders_and_suffixes_collisions():
    got = tab_labels.labels_for(["30_Coding", "10_Coding", "20_Coding", "05_,,", "Misc"])
    assert got == (("10_Coding", "Coding"), ("20_Coding", "Coding 2"),
                   ("30_Coding", "Coding 3"), ("Misc", "Misc"))


def test_parity_with_toggle_sh(tmp_path):
    """Same folders through toggle.sh --list-tabs and through labels_for()."""
    entries = tmp_path / "entries"
    folders = ["10_Coding", "20_Coding", "30_Writing", "40_,,", "50_A,B:C'D\"E", "Misc", "60_Ignored"]
    for name in folders:
        (entries / name).mkdir(parents=True)
        if name != "60_Ignored":
            (entries / name / "content.md").write_text("x\n")
    paths = for_repo_copy(tmp_path, tmp_path / "data")
    (tmp_path / "config.yaml").write_text("")
    bash = [(label, folder.name) for label, folder in bash_bridge.list_tabs(paths)]
    ours = [(label, folder) for folder, label in
            tab_labels.labels_for(f for f in folders if f != "60_Ignored")]
    assert bash == ours


@pytest.mark.parametrize("name", ["Coding", "my prompts", "A.b-c_d", "9lives"])
def test_validate_name_accepts(name):
    assert tab_labels.validate_name(f"  {name} ") == name


@pytest.mark.parametrize("name", ["", " ", "a/b", "../x", ".hidden", "-lead", "x" * 65, "a,b", "q\"", "tab\nx"])
def test_validate_name_refuses(name):
    with pytest.raises(ValueError):
        tab_labels.validate_name(name)


def test_collides_with_uses_the_rofi_label():
    assert tab_labels.collides_with("Coding", ["10_Coding"]) == "10_Coding"
    assert tab_labels.collides_with("Coding", ["10_Writing"]) is None
    # "Co,ding" would also show as "Coding" — a silent duplicate
    assert tab_labels.collides_with("Co.ding", ["10_Coding"]) is None


def test_plan_renumber_is_canonical_and_widens():
    assert tab_labels.plan_renumber(["10_A", "20_B"]) == ()
    assert tab_labels.plan_renumber(["20_B", "10_A"]) == (("20_B", "10_B"), ("10_A", "20_A"))
    assert tab_labels.plan_renumber(["A", "5_B"]) == (("A", "10_A"), ("5_B", "20_B"))
    ten = [f"{(i + 1) * 10}_T{i}" for i in range(10)]
    plan = dict(tab_labels.plan_renumber(ten))
    assert plan["10_T0"] == "010_T0" and "100_T9" not in plan     # already three wide
    assert all(len(new.split("_")[0]) == 3 for new in plan.values())


@pytest.mark.parametrize("folder,ok", [("10_A", True), ("a b", True), ("", False), ("a/b", False),
                                       (".git", False), ("..", False), ("x" * 121, False)])
def test_is_safe_id(folder, ok):
    assert tab_labels.is_safe_id(folder) is ok
