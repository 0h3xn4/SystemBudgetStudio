"""Pre-release audit, critical GUI findings: a scenario edit must land in the open project (GUI-1),
and saving a unit must not lose what the table does not show (GUI-2)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow
from tests.gui_helpers import set_mode_value

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def copy(name: str, tmp_path: Path, as_name: str) -> Path:
    shutil.copytree(EXAMPLES / name, tmp_path / as_name)
    return tmp_path / as_name


# ---- GUI-1: the scenario editor follows the project --------------------------------------------
def test_a_scenario_edit_is_saved_into_the_open_project_not_the_previous_one(
    window: MainWindow, tmp_path: Path
) -> None:
    a = copy("microsat_250kg_eps", tmp_path, "projA")
    b = copy("microsat_250kg", tmp_path, "projB")  # also has a scenario called one_day
    window.open_project(a)
    window.open_project(b)
    editor = window.scenario_view.editor
    editor.add_segment(100.0, 200.0)
    before_a = (a / "scenarios/one_day.yaml").read_bytes()
    before_b = (b / "scenarios/one_day.yaml").read_bytes()
    assert editor.save()
    assert (a / "scenarios/one_day.yaml").read_bytes() == before_a
    assert (b / "scenarios/one_day.yaml").read_bytes() != before_b
    assert len(load_project(b).project.scenarios["one_day"].segments) == 1  # type: ignore[union-attr]


def test_the_editor_root_follows_a_reload_of_another_folder(
    window: MainWindow, tmp_path: Path
) -> None:
    a = copy("microsat_250kg_eps", tmp_path, "projA")
    b = copy("microsat_250kg", tmp_path, "projB")
    window.open_project(a)
    window.open_project(b)
    assert window.scenario_view.editor.root == b


# ---- GUI-2: hidden keys survive a unit save ---------------------------------------------------
def test_saving_a_unit_without_an_edit_leaves_the_file_byte_identical(
    window: MainWindow, tmp_path: Path
) -> None:
    project = copy("microsat_250kg_eps", tmp_path, "p")
    window.open_project(project)
    page = window.show_unit("adcs")
    assert page is not None
    before = (project / "units/adcs.yaml").read_bytes()
    assert b"heat_dissipation_ratio" in before
    assert page.add_mode()
    page.table.select_cell(page.modes.rows_of("adcs")[-1], 1)
    assert page.remove_mode()  # edited twice, but equal to the file again
    assert not window.document.is_modified() and window.save_model()
    assert (project / "units/adcs.yaml").read_bytes() == before


def test_a_unit_edit_keeps_heat_dissipation_ratio_of_every_mode(
    window: MainWindow, tmp_path: Path
) -> None:
    project = copy("microsat_250kg_eps", tmp_path, "p")
    window.open_project(project)
    assert set_mode_value(window, "adcs", "safe", "avg_power_w", "0.45")
    assert window.save_model()
    unit = load_project(project).project.units["adcs"]  # type: ignore[union-attr]
    assert [m.heat_dissipation_ratio for m in unit.modes] == [1.0] * len(unit.modes)
    assert unit.modes[1].avg_power_w == 0.45


def test_the_heat_ratio_of_a_mode_stays_with_its_row_when_a_row_is_removed(
    window: MainWindow, tmp_path: Path
) -> None:
    project = copy("microsat_250kg_eps", tmp_path, "p")
    path = project / "units/adcs.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("heat_dissipation_ratio: 1.0", "heat_dissipation_ratio: 0.5", 1),
        encoding="utf-8",
    )
    window.open_project(project)
    page = window.show_unit("adcs")
    assert page is not None
    page.table.select_cell(page.modes.rows_of("adcs")[0], 1)
    assert page.remove_mode()  # the 'off' mode that carries 0.5
    assert window.save_model()
    unit = load_project(project).project.units["adcs"]  # type: ignore[union-attr]
    assert [m.name for m in unit.modes][0] == "safe"
    assert all(m.heat_dissipation_ratio == 1.0 for m in unit.modes)
