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
from budget_gui.project_tree import Node, ProjectTree, badge_counts, build_nodes

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def child(node: Node, prefix: str) -> Node:
    return next(c for c in node.children if c.label.startswith(prefix))


@pytest.fixture(scope="module")
def eps() -> tuple[Path, Node]:
    root = EXAMPLES / "cubesat_3u_eps"
    return root, build_nodes(root, load_project(root).project)


def test_the_tree_follows_the_model(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    assert "Example 3U CubeSat" in top.label and "rev " in top.label
    names = [c.label.split(" (")[0] for c in top.children]
    assert names == [
        "Spacecraft",
        "Orbit & ground stations",
        "Scenarios",
        "Links",
        "Budget configuration",
        "Files",
    ]
    spacecraft = child(top, "Spacecraft")
    assert [c.label.split(" (")[0] for c in spacecraft.children] == [
        "Units",
        "Spacecraft modes",
        "Solar array",
        "Battery",
    ]
    units = child(spacecraft, "Units")
    radio = child(units, "radio")
    assert radio.label == "radio: UHF/VHF radio" and radio.rel == "units/radio.yaml"
    assert radio.children[0].kind == "unit_modes" and radio.children[0].unit_id == "radio"


def test_solar_array_battery_and_antennas_open_their_field(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    array = child(child(top, "Spacecraft"), "Solar array")
    assert (array.kind, array.rel, array.path) == (
        "field",
        "config/power_system.yaml",
        "solar_array",
    )
    link = child(child(top, "Links"), "uhf_down")
    assert [(c.label, c.path) for c in link.children] == [
        ("Transmitter", "transmitter"),
        ("Receiver", "receiver"),
    ]


def test_names_come_from_the_files_when_the_project_does_not_load(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    top = build_nodes(tmp_path / "p", None)
    radio = child(child(child(top, "Spacecraft"), "Units"), "radio")
    assert radio.label == "radio"  # no name without a loaded project, but the node is there


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
    spacecraft = child(top, "Spacecraft")
    radio = child(child(spacecraft, "Units"), "radio")
    assert counts[id(radio)][ProblemClass.ERROR] == 1
    assert counts[id(radio.children[0])] == {c: 0 for c in ProblemClass}  # no badge on "modes"
    assert counts[id(child(spacecraft, "Solar array"))][ProblemClass.NOT_CHECKED] == 1
    assert counts[id(child(spacecraft, "Battery"))][ProblemClass.NOT_CHECKED] == 1
    assert counts[id(spacecraft)][ProblemClass.ERROR] == 1
    assert counts[id(spacecraft)][ProblemClass.NOT_CHECKED] == 2
    assert counts[id(top)] == pc.counts(problems)  # the project: everything, also without a file
    config = child(top, "Budget configuration")
    assert counts[id(config)][ProblemClass.NOT_CHECKED] == 2


def test_a_field_problem_does_not_count_on_its_sibling_field(eps: tuple[Path, Node]) -> None:
    _root, top = eps
    problems = [
        Problem(Severity.WARNING, "W", "w", "config/power_system.yaml", "solar_array_extra")
    ]
    counts = badge_counts(top, problems)
    spacecraft = child(top, "Spacecraft")
    assert counts[id(child(spacecraft, "Solar array"))][ProblemClass.WARNING] == 0


# ---- the widget -----------------------------------------------------------------------------
@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w.open_project(EXAMPLES / "cubesat_3u_eps")
    return w


def test_the_badges_show_on_the_items(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", kind="file")
    assert item is not None
    assert window.tree.badges_of(item).get(ProblemClass.ERROR) == 1  # THERMAL_MARGIN_INSUFFICIENT
    assert "1 error" in item.toolTip(0)
    top = window.tree.topLevelItem(0)
    assert top is not None and window.tree.badges_of(top)[ProblemClass.ERROR] >= 1


def test_enter_opens_the_selected_file(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    item = window.tree.find_item("units/obc.yaml", kind="file")
    assert item is not None
    window.tree.setCurrentItem(item)
    window.tree.setFocus()
    with qtbot.waitSignal(window.tree.file_requested, timeout=1000) as blocker:
        qtbot.keyClick(window.tree, Qt.Key.Key_Return)
    assert blocker.args == ["units/obc.yaml"]
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "units/obc.yaml"


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


def test_enter_on_the_power_modes_node_opens_the_table_editor(window: MainWindow) -> None:
    item = window.tree.find_item("units/radio.yaml", "modes", kind="unit_modes")
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
