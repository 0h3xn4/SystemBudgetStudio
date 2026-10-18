"""The project tree: model nodes, badges, Enter opens (UX step 1, D-151)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_core.io.project_loader import load_project
from budget_core.problems import Problem, Severity
from budget_gui import problem_class as pc
from budget_gui.main_window import MainWindow
from budget_gui.problem_class import ProblemClass
from budget_gui.project_tree import (
    BADGE_ROLE,
    Node,
    ProjectTree,
    badge_counts,
    build_nodes,
    own_counts,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def child(node: Node, prefix: str) -> Node:
    return next(c for c in node.children if c.label.startswith(prefix))


@pytest.fixture(scope="module")
def eps() -> tuple[Path, Node]:
    root = EXAMPLES / "microsat_250kg_eps"
    return root, build_nodes(root, load_project(root).project)


def test_the_tree_follows_the_model(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    assert "Example 250 kg minisatellite" in top.label and "rev " in top.label
    assert [c.label.split(" (")[0] for c in top.children] == [
        "Spacecraft",
        "Units",
        "Spacecraft modes",
        "Expendables",
        "Solar array",
        "Battery",
        "Orbits",
        "Ground stations",
        "Imaging targets",
        "Scenarios",
        "Links",
        "Budget configuration",
        "Files",
    ]


def test_many_units_are_grouped_by_subsystem_and_shown_by_name(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    units = child(top, "Units")
    assert units.expanded and units.label == "Units (18)"
    groups = [c.label for c in units.children]
    assert groups == sorted(groups) and "ADCS (6)" in groups and "TTC (1)" in groups
    assert all(not c.expanded and c.kind == "group" for c in units.children)  # folded
    radio = child(child(units, "TTC"), "S-band")
    assert radio.label == "S-band transceiver" and radio.ident == "radio"
    assert radio.kind == "unit" and radio.unit_id == "radio" and radio.rel == "units/radio.yaml"
    assert not radio.children  # no arrow: nothing to open inside a unit


def test_few_units_are_not_grouped(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    for path in sorted((tmp_path / "p" / "units").glob("*.yaml"))[6:]:
        path.unlink()
    top = build_nodes(tmp_path / "p", load_project(tmp_path / "p").project)
    units = child(top, "Units")
    assert all(c.kind in {"unit", "file"} for c in units.children) and len(units.children) == 6


def test_solar_array_and_battery_open_their_field_and_links_their_file(
    eps: tuple[Path, Node],
) -> None:
    _root, top = eps
    array = child(top, "Solar array")
    assert (array.kind, array.rel, array.path) == (
        "field",
        "config/power_system.yaml",
        "solar_array",
    )
    link = child(child(top, "Links"), "S-band telemetry")
    assert link.rel == "links/sband_down.yaml" and link.ident == "sband_down"
    assert not link.children


def test_names_come_from_the_files_when_the_project_does_not_load(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    top = build_nodes(tmp_path / "p", None)
    units = child(top, "Units")
    radio = next(n for n in units.walk() if n.rel == "units/radio.yaml")
    assert radio.label == "radio" and radio.kind == "file"  # no name, so a plain file row


def test_badges_count_the_problems_of_a_node_and_of_its_parents(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    problems = [
        Problem(Severity.ERROR, "E", "x", file="units/radio.yaml", path="temperature_limits"),
        Problem(
            Severity.WARNING, "CONFIG_PLACEHOLDER", "p", "config/power_system.yaml", "solar_array.x"
        ),
        Problem(
            Severity.WARNING, "CONFIG_PLACEHOLDER", "p", "config/power_system.yaml", "battery.y"
        ),
        Problem(Severity.INFO, "I", "i", file=None),
    ]
    counts = badge_counts(top, problems)
    units = child(top, "Units")
    radio = next(n for n in units.walk() if n.unit_id == "radio")
    assert counts[id(radio)][ProblemClass.ERROR] == 1
    assert counts[id(child(units, "TTC"))][ProblemClass.ERROR] == 1  # the group of the unit
    assert counts[id(units)][ProblemClass.ERROR] == 1
    assert counts[id(child(top, "Solar array"))][ProblemClass.NOT_CHECKED] == 1
    assert counts[id(child(top, "Battery"))][ProblemClass.NOT_CHECKED] == 1
    assert counts[id(top)] == pc.counts(problems)  # the project: everything, also without a file
    config = child(top, "Budget configuration")
    assert counts[id(config)][ProblemClass.NOT_CHECKED] == 2
    assert own_counts(units, problems) == {c: 0 for c in ProblemClass}  # the group itself: none


def test_the_raw_file_list_does_not_repeat_the_problems_of_every_other_row(
    eps: tuple[Path, Node],
) -> None:
    _root, top = eps
    problems = [
        Problem(Severity.ERROR, "E", "x", file="units/radio.yaml", path="temperature_limits")
    ]
    counts = badge_counts(top, problems)
    files = child(top, "Files")
    assert counts[id(files)][ProblemClass.ERROR] == 0
    raw = next(n for n in files.children if n.rel == "units/radio.yaml")
    assert counts[id(raw)][ProblemClass.ERROR] == 1  # its own row still says so


def test_a_field_problem_does_not_count_on_its_sibling_field(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    problems = [
        Problem(Severity.WARNING, "W", "w", "config/power_system.yaml", "solar_array_extra")
    ]
    counts = badge_counts(top, problems)
    assert counts[id(child(top, "Solar array"))][ProblemClass.WARNING] == 0


# ---- the widget -----------------------------------------------------------------------------
@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w.open_project(EXAMPLES / "microsat_250kg_eps")
    return w


def test_the_badges_show_on_the_items(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None
    assert window.tree.badges_of(item).get(ProblemClass.ERROR) == 1  # THERMAL_MARGIN_INSUFFICIENT
    assert "1 error" in item.toolTip(0)
    top = window.tree.topLevelItem(0)
    assert top is not None and window.tree.badges_of(top)[ProblemClass.ERROR] >= 1


def test_a_folded_group_shows_what_is_inside_and_an_open_one_only_its_own(
    window: MainWindow,
) -> None:
    from budget_gui.project_tree import OWN_BADGE_ROLE

    ttc = window.tree.find_item("units/radio.yaml", kind="unit").parent()  # the TTC group
    assert ttc is not None and not ttc.isExpanded()
    assert window.tree.badges_of(ttc).get(ProblemClass.ERROR) == 1  # shown while folded
    assert not ttc.data(0, OWN_BADGE_ROLE)  # nothing of its own to show once open
    root_item = window.tree.topLevelItem(0)
    assert root_item is not None and not root_item.data(0, OWN_BADGE_ROLE)  # no repeated totals


def test_no_row_carries_a_not_checked_badge(window: MainWindow) -> None:
    stack = [window.tree.invisibleRootItem()]
    while stack:
        item = stack.pop()
        for i in range(item.childCount()):
            stack.append(item.child(i))
            assert ProblemClass.NOT_CHECKED not in {
                ProblemClass(c) for c, _n in item.child(i).data(0, BADGE_ROLE) or ()
            }


def test_what_the_user_folded_or_opened_stays_after_a_reload(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None
    group = item.parent()
    assert group is not None
    group.setExpanded(True)
    window.session.reload()
    again = window.tree.find_item("units/radio.yaml", kind="unit")
    assert again is not None and again.parent() is not None and again.parent().isExpanded()


def test_enter_opens_the_selected_file(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    item = window.tree.find_item("scenarios/one_day.yaml", kind="file")
    assert item is not None
    window.tree.setCurrentItem(item)
    window.tree.setFocus()
    with qtbot.waitSignal(window.tree.file_requested, timeout=1000) as blocker:
        qtbot.keyClick(window.tree, Qt.Key.Key_Return)
    assert blocker.args == ["scenarios/one_day.yaml"]
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "scenarios/one_day.yaml"


def test_enter_on_a_field_node_opens_the_file_at_the_field(window: MainWindow) -> None:
    item = window.tree.find_item("config/power_system.yaml", "battery", kind="field")
    assert item is not None
    window.tree.setCurrentItem(item)
    window.tree.activate_current()
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "config/power_system.yaml"
    text = editor.toPlainText().splitlines()
    # the jump lands on the first line inside the field, like every jump from a problem
    assert text[editor.current_line() - 2] == "battery:"


def test_enter_on_a_unit_opens_the_table_of_its_power_modes(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", kind="unit")
    assert item is not None
    window.tree.setCurrentItem(item)
    window.tree.activate_current()
    assert window.editors.unit_editor("radio") is not None


def test_the_tree_is_a_keyboard_widget(window: MainWindow) -> None:
    assert isinstance(window.tree, ProjectTree)
    assert window.tree.focusPolicy() & Qt.FocusPolicy.TabFocus


def test_every_file_is_still_reachable_in_the_files_group(window: MainWindow) -> None:
    files = window.tree.find_item("project.yaml")
    assert files is not None
    root = window.session.path
    assert root is not None
    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*.yaml")}
    assert window.tree.file_item_count() == len(on_disk)
