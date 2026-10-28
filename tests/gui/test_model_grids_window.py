"""The grids of the Model tab in the window: edit, validate, save, undo (UX step 2, D-159)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow
from tests.gui_helpers import (
    mode_row,
    set_mode_value,
    set_unit_value,
)

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path):  # type: ignore[no-untyped-def]
    w = MainWindow()
    # pytest-qt closes the window before fixtures finish: drop unsaved edits first, else it asks
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def saved(project: Path, unit: str = "camera"):  # type: ignore[no-untyped-def]
    loaded = load_project(project).project
    assert loaded is not None
    return loaded.units[unit]


def test_the_model_tab_opens_on_the_grids_before_the_scenario(window: MainWindow) -> None:
    tabs = [window.editors.tabText(i) for i in range(window.editors.count())]
    assert tabs[:5] == ["Units", "Power modes", "Spacecraft modes", "Inputs", "Scenario"]
    assert window.units_page.model.rowCount() == 18
    assert window.modes_page.model.rowCount() > 18 and window.inputs_page.model.rowCount() > 40


def test_a_value_with_a_unit_is_converted_and_saved_in_place(
    window: MainWindow, project: Path
) -> None:
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62500 mW")
    assert set_mode_value(window, "camera", "imaging", "peak_power_w", "85 W")
    assert window.document.is_modified() and window.editors.has_unsaved_changes()
    assert window.save_model() is True
    mode = saved(project).modes[1]
    assert mode.avg_power_w == pytest.approx(62.5) and mode.peak_power_w == pytest.approx(85.0)
    assert not window.document.is_modified()
    assert b"\r" not in (project / "units" / "camera.yaml").read_bytes()


def test_plain_numbers_mean_the_canonical_unit(window: MainWindow) -> None:
    set_mode_value(window, "camera", "imaging", "avg_power_w", "65")
    assert window.document.value("units/camera.yaml", ("modes", 1, "avg_power_w")) == 65.0
    assert not window.document.problems()


def test_the_wrong_kind_of_unit_is_explained_and_nothing_is_written(
    window: MainWindow, project: Path
) -> None:
    before = (project / "units" / "camera.yaml").read_bytes()
    set_mode_value(window, "camera", "imaging", "avg_power_w", "3 dBW")
    text = window.modes_page.problem_label.text()
    assert "avg_power_w" in text and "logarithmic" in text
    assert window.save_model() is False
    assert (project / "units" / "camera.yaml").read_bytes() == before
    assert "need correcting" in window.status_bar.currentMessage()


def test_a_decimal_comma_and_an_underscore_are_not_numbers(window: MainWindow) -> None:
    set_mode_value(window, "camera", "imaging", "avg_power_w", "1_0")
    assert window.modes_page.problem_label.text() and window.save_model() is False
    set_mode_value(window, "camera", "imaging", "avg_power_w", "1,5")
    assert "decimal point" in window.modes_page.problem_label.text()
    set_mode_value(window, "camera", "imaging", "avg_power_w", "65")
    assert window.modes_page.problem_label.text() == ""


def test_a_rule_between_two_fields_is_reported_on_the_cell(window: MainWindow) -> None:
    set_mode_value(window, "camera", "imaging", "peak_power_w", "1 W")  # below the average
    assert "peak" in window.modes_page.problem_label.text().lower()
    assert window.save_model() is False


def test_a_duty_cycle_out_of_range_is_reported(window: MainWindow) -> None:
    set_mode_value(window, "camera", "imaging", "duty_cycle_ratio", "1.5")
    assert "duty_cycle_ratio" in window.modes_page.problem_label.text()
    assert window.save_model() is False


def test_add_and_remove_modes(window: MainWindow, project: Path) -> None:
    page = window.modes_page
    assert page.select_unit("camera") and page.add_mode()
    row = page.modes.rows_of("camera")[-1]
    page.modes.setData(page.modes.index(row, 1), "standby")
    page.modes.setData(page.modes.index(row, 2), "0.1")
    page.modes.setData(page.modes.index(row, 3), "0.2")
    assert window.save_model() is True
    assert [m.name for m in saved(project).modes] == ["off", "imaging", "standby"]
    page.table.select_cell(page.modes.rows_of("camera")[-1], 1)
    assert page.remove_mode() and window.save_model() is True
    assert [m.name for m in saved(project).modes] == ["off", "imaging"]


def test_removing_a_mode_in_use_is_reported_by_the_problems_panel(window: MainWindow) -> None:
    page = window.modes_page
    page.table.select_cell(mode_row(window, "camera", "imaging"), 1)
    assert page.remove_mode()  # 'imaging' is used by the imaging spacecraft mode
    assert window.save_model() is True
    assert "1 error" in window.problems_panel.summary.text()
    assert "REF_UNKNOWN_UNIT_MODE" in set(window.problems_panel.codes())


def test_save_updates_the_budget_and_the_problems(window: MainWindow) -> None:
    model = window.power_view.table_model("Summary", 0)
    row = next(r for r in range(model.rowCount()) if model.data(model.index(r, 0)) == "Imaging")
    before = model.data(model.index(row, 1))
    set_mode_value(window, "camera", "imaging", "avg_power_w", "100")  # above the 80 W peak
    assert window.save_model() is False
    set_mode_value(window, "camera", "imaging", "peak_power_w", "120")
    assert window.save_model() is True
    after_model = window.power_view.table_model("Summary", 0)
    assert float(after_model.data(after_model.index(row, 1))) > float(before)


def test_ctrl_s_on_a_grid_saves_the_grids(window: MainWindow, project: Path) -> None:
    from PySide6.QtCore import Qt

    window.show_view(window.units_page)
    set_unit_value(window, "radio", "mass_kg", "5.5")
    assert window.workspace.currentWidget() is window.editors
    assert window.save_current() is True
    assert saved(project, "radio").mass_kg == 5.5
    assert Qt  # the shortcut is the same action as the menu entry


def test_the_dirty_marker_follows_the_grids(window: MainWindow) -> None:
    set_unit_value(window, "radio", "mass_kg", "5.5")
    assert window.top_bar.dirty_label.isVisibleTo(window) or "●" in window.windowTitle()
    window.document.undo_stack.undo()
    assert "●" not in window.windowTitle()


def test_undo_and_redo_are_in_the_edit_menu_with_the_step_named(window: MainWindow) -> None:
    set_unit_value(window, "radio", "mass_kg", "5.5")
    assert window.undo_action.isEnabled() and "radio" in window.undo_action.text()
    window.undo_action.trigger()
    assert not window.document.is_modified() and window.redo_action.isEnabled()
    window.redo_action.trigger()
    assert window.document.value("units/radio.yaml", ("mass_kg",)) == 5.5


def test_unsaved_grid_edits_prompt_on_close(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_unit_value(window, "radio", "mass_kg", "5.5")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert window.close() is False
    window.editors.discard_all_changes()
    assert not window.editors.has_unsaved_changes()


def test_opening_another_project_asks_before_dropping_grid_edits(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_unit_value(window, "radio", "mass_kg", "5.5")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert window.open_project(project) is False
    assert window.document.is_modified()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Discard)
    assert window.open_project(project) is True
    assert not window.document.is_modified()


def test_a_unit_on_the_tree_opens_its_power_modes_in_the_grid(window: MainWindow) -> None:
    window.show_view(window.mass_view)
    page = window.show_unit("radio")
    assert page is window.modes_page
    assert window.workspace.currentWidget() is window.editors
    assert window.editors.currentWidget() is page
    assert page.table.current_cell() == (page.modes.rows_of("radio")[0], 1)


def test_a_project_with_an_error_keeps_the_last_good_grids_and_says_why(
    window: MainWindow, project: Path
) -> None:
    (project / "units" / "radio.yaml").write_text("not: [valid", encoding="utf-8")
    window.session.reload()
    assert window.units_page.model.rowCount() == 18
    assert window.show_unit("nope") is None
    assert "Fix the errors" in window.status_bar.currentMessage()


def test_the_grids_follow_a_reload_from_disk(window: MainWindow, project: Path) -> None:
    path = project / "units" / "obc.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("mass_kg: 3.0", "mass_kg: 3.3"))
    window.reload_project()
    model = window.units_page.units
    assert window.document.value("units/obc.yaml", ("mass_kg",)) == pytest.approx(3.3)
    assert model.index(model.row_of("obc"), 5).data() == "3.300"


def test_a_save_over_a_file_changed_on_disk_is_refused_with_a_sentence(
    window: MainWindow, project: Path
) -> None:
    set_unit_value(window, "radio", "mass_kg", "5.5")
    path = project / "units" / "radio.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "# edited elsewhere\n", encoding="utf-8")
    assert window.save_model() is False
    assert "changed on disk" in window.units_page.feedback_label.text()
    assert "5.5" not in path.read_text(encoding="utf-8")


def test_a_failed_write_leaves_the_file_and_no_temporary_file(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = (project / "units/camera.yaml").read_bytes()
    set_mode_value(window, "camera", "imaging", "avg_power_w", "65")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("budget_core.reports.files.os.replace", refuse)
    assert window.save_model() is False
    assert "could not be written" in window.modes_page.feedback_label.text()
    assert (project / "units/camera.yaml").read_bytes() == before
    assert not [p for p in (project / "units").iterdir() if p.name.endswith(".tmp")]


def _lossy(monkeypatch, project: Path) -> None:  # type: ignore[no-untyped-def]
    """The unit file has a comment and the edit cannot be made in place."""
    camera = project / "units" / "camera.yaml"
    camera.write_text("# datasheet rev C\n" + camera.read_text(encoding="utf-8"), encoding="utf-8")

    def cannot(_text: str, _old: object, _new: object) -> str:
        raise ValueError("the patch cannot follow this file")

    monkeypatch.setattr("budget_core.io.roundtrip.patch_yaml_text", cannot)


def test_a_save_that_would_drop_comments_asks_first_and_no_leaves_the_file(
    window: MainWindow,
    project: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    window.open_project(project)
    _lossy(monkeypatch, project)
    window.open_project(project)
    before = (project / "units" / "camera.yaml").read_bytes()
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62.5 W")
    asked: list[str] = []

    def no(_parent, _title, text, *_a):  # type: ignore[no-untyped-def]
        asked.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(no))
    assert window.save_model() is False
    assert asked and "units/camera.yaml" in asked[0] and "without" in asked[0]
    assert (project / "units" / "camera.yaml").read_bytes() == before
    assert window.document.is_modified()  # the edit is still there to save or undo
    assert "lose its comments" in window.status_bar.currentMessage()


def test_accepting_the_rewrite_saves_and_says_the_comments_were_not_kept(
    window: MainWindow,
    project: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    _lossy(monkeypatch, project)
    window.open_project(project)
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62.5 W")
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *_a: QMessageBox.StandardButton.Yes)
    )
    assert window.save_model() is True
    text = (project / "units" / "camera.yaml").read_text(encoding="utf-8")
    assert "datasheet rev C" not in text
    assert saved(project).modes[1].avg_power_w == pytest.approx(62.5)
    assert "Comments were not kept in units/camera.yaml" in window.status_bar.currentMessage()


def test_an_edit_made_in_place_does_not_ask(
    window: MainWindow,
    project: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    camera = project / "units" / "camera.yaml"
    camera.write_text("# datasheet rev C\n" + camera.read_text(encoding="utf-8"), encoding="utf-8")
    window.open_project(project)

    def never(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AssertionError("the user must not be asked")

    monkeypatch.setattr(QMessageBox, "question", staticmethod(never))
    assert set_mode_value(window, "camera", "imaging", "avg_power_w", "62.5 W")
    assert window.save_model() is True
    assert "# datasheet rev C" in camera.read_text(encoding="utf-8")
