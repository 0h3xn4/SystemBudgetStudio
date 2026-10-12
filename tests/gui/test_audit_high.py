"""Pre-release audit, high GUI findings (GUI-3 to GUI-7, GUI-9 to GUI-12): editors that follow the
file, no silent loss of edits, a window that closes cleanly, and results that are tied to the
inputs they were computed from."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """cubesat_3u with a short step and a second scenario called 'two'."""
    shutil.copytree(EXAMPLES / "cubesat_3u", tmp_path / "p")
    root = tmp_path / "p"
    text = (root / "scenarios/one_day.yaml").read_text(encoding="utf-8")
    text = text.replace("step_s: 10.0", "step_s: 60.0")
    (root / "scenarios/one_day.yaml").write_text(text, encoding="utf-8")
    (root / "scenarios/two.yaml").write_text(
        text.replace("One day:", "Second:").replace("duration_s: 86400.0", "duration_s: 43200.0"),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def answer(monkeypatch: pytest.MonkeyPatch, button: QMessageBox.StandardButton) -> list[str]:
    asked: list[str] = []

    def fake(_parent, _title, text, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        asked.append(text)
        return button

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake))
    return asked


def warnings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def fake(_parent, _title, text, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        seen.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(fake))
    return seen


def compute_timeline(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.timeline_view.computed, timeout=120000):
        window.timeline_view.compute()


# ---- GUI-3: clean table editors follow the file ----------------------------------------------
def test_a_text_edit_is_not_reverted_by_the_next_save_in_the_unit_table(
    window: MainWindow, project: Path
) -> None:
    table = window.open_unit_editor("camera")
    assert table is not None
    window.open_file("units/camera.yaml")
    text = window.editors.current_editor()
    assert text is not None
    document = text.toPlainText()
    assert "avg_power_w: 2.4" in document
    text.setPlainText(document.replace("avg_power_w: 2.4", "avg_power_w: 2.6"))
    assert window.save_current()  # saves the text tab, the project reloads
    assert table.table.item(1, 1).text() == "2.6"  # the clean table shows the new file
    table.table.item(1, 2).setText("3.5")  # now an edit in the table (peak power)
    window.editors.setCurrentWidget(table)
    assert window.save_current()
    saved = load_project(project).project.units["camera"]  # type: ignore[union-attr]
    assert saved.modes[1].avg_power_w == 2.6 and saved.modes[1].peak_power_w == 3.5


def test_a_table_with_pending_edits_refuses_to_overwrite_a_newer_file(
    window: MainWindow, project: Path
) -> None:
    table = window.open_unit_editor("camera")
    assert table is not None
    table.table.item(0, 0).setText("off2")
    path = project / "units/camera.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("avg_power_w: 2.4", "avg_power_w: 2.7"),
        encoding="utf-8",
    )
    assert not table.save()
    assert "changed on disk" in table.error_label.text()
    assert "avg_power_w: 2.7" in path.read_text(encoding="utf-8")


# ---- GUI-4: switching the scenario asks before dropping edits ---------------------------------
def test_switching_the_scenario_with_unsaved_edits_asks_and_can_cancel(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = window.scenario_view
    assert view.selected_id() == "one_day"
    view.editor.add_segment(10.0, 20.0)
    asked = answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    view.combo.setCurrentText("two")
    assert asked
    assert view.selected_id() == "one_day"  # the combo went back
    assert view.editor.is_modified() and view.editor.segments_table.rowCount() == 1


def test_switching_the_scenario_and_discarding_loads_the_other_one(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = window.scenario_view
    view.editor.add_segment(10.0, 20.0)
    answer(monkeypatch, QMessageBox.StandardButton.Discard)
    view.combo.setCurrentText("two")
    assert view.selected_id() == "two" and view.editor.scenario_id == "two"
    assert not view.editor.is_modified() and view.editor.segments_table.rowCount() == 0


# ---- GUI-5: a reload without a project keeps the edits ----------------------------------------
def test_a_reload_that_finds_no_project_keeps_unsaved_scenario_edits(
    window: MainWindow, project: Path
) -> None:
    editor = window.scenario_view.editor
    editor.add_segment(10.0, 20.0)
    (project / "project.yaml").write_text("not: [valid\n", encoding="utf-8")
    window.session.reload()
    assert window.session.project is None
    assert editor.is_modified() and editor.segments_table.rowCount() == 1
    assert window.editors.has_unsaved_changes()


# ---- GUI-6: closing while a job runs ----------------------------------------------------------
def test_closing_the_window_while_a_job_runs_waits_for_it_without_freezing(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.show()
    window.scenario_view.compute()
    started = time.monotonic()
    closed = window.close()
    assert time.monotonic() - started < 2.0
    assert not closed and window.isVisible()  # ignored for now, no thread was destroyed
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=120000)  # closes when the job is done
    assert window.scenario_view.last_run is not None


# ---- GUI-7: a save that cannot be written says so in plain words -------------------------------
def test_saving_a_file_that_cannot_be_written_gives_a_plain_message(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = warnings(monkeypatch)
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    editor.textCursor().insertText("# edit\n")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr("budget_core.reports.files.os.replace", refuse)
    assert window.save_current() is False
    assert seen and "could not be saved" in seen[0]
    assert editor.document().isModified()


# ---- GUI-9: the scenario tab notices a changed orbit file ---------------------------------------
def test_editing_the_orbit_marks_the_computed_scenario_stale_and_blocks_its_export(
    window: MainWindow, project: Path, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    view = window.scenario_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    assert not view.is_stale
    orbit = project / "orbits/leo.yaml"
    text = orbit.read_text(encoding="utf-8")
    assert "inclination_deg: 97.6" in text
    orbit.write_text(
        text.replace("inclination_deg: 97.6", "inclination_deg: 51.6"), encoding="utf-8"
    )
    window.session.reload()
    assert view.is_stale
    assert view.reusable_run("one_day") is None
    with pytest.raises(Exception, match="out of date|Compute"):
        view.export_to(tmp_path / "out")
    assert not (tmp_path / "out").exists()


# ---- GUI-10: the demand basis is part of what a result was computed from ------------------------
def test_changing_the_demand_basis_marks_the_timeline_stale(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.timeline_view
    compute_timeline(window, qtbot)
    assert view.export_button.isEnabled() and view.output() is not None
    view.basis_combo.setCurrentText("margined")
    assert view.is_stale and not view.export_button.isEnabled() and view.output() is None
    assert "Compute" in view.status.text()
    view.basis_combo.setCurrentText("nominal")  # back to what was computed
    assert not view.is_stale and view.output() is not None


# ---- GUI-11: a result is only shown for the scenario it was computed for ------------------------
def test_a_timeline_result_for_another_scenario_is_not_shown_or_exportable(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    view = window.timeline_view
    view.scenario_combo.setCurrentText("one_day")
    view.compute()
    view.scenario_combo.setCurrentText("two")  # while it runs
    qtbot.waitUntil(lambda: view.compute_button.isEnabled(), timeout=120000)
    assert view.output() is None and not view.export_button.isEnabled()
    assert view.result is None or view.result.run.scenario_id == view.selected_id()


def test_a_link_result_for_another_scenario_is_not_shown_or_exportable(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    view = window.link_passes_view
    view.scenario_combo.setCurrentText("one_day")
    view.compute()
    view.scenario_combo.setCurrentText("two")
    qtbot.waitUntil(lambda: view.compute_button.isEnabled(), timeout=120000)
    assert view.output() is None and not view.export_button.isEnabled()
    assert view.result is None or view.result.run.scenario_id == view.selected_id()


def test_a_scenario_run_for_another_scenario_is_dropped(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.scenario_view
    view.compute()
    view.combo.setCurrentText("two")
    qtbot.waitUntil(lambda: view.compute_button.isEnabled(), timeout=120000)
    assert view.last_run is None or view.last_run.scenario_id == "two"


# ---- GUI-12: a comparison belongs to the project it compared ------------------------------------
def test_a_comparison_cannot_be_exported_after_the_project_changed(
    window: MainWindow, project: Path, tmp_path: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    view = window.compare_view
    other = tmp_path / "other"
    shutil.copytree(project, other)
    other_unit = other / "units/camera.yaml"
    other_unit.write_text(
        other_unit.read_text(encoding="utf-8").replace("avg_power_w: 2.4", "avg_power_w: 2.9"),
        encoding="utf-8",
    )
    view.set_other_folder(other)
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compare()
    assert view.export_button.isEnabled()
    window.session.reload()
    assert not view.export_button.isEnabled()
    failed: list[str] = []
    view.export_failed.connect(failed.append)
    view.export_to(tmp_path / "exp", {"csv"})
    assert failed and "Compare" in failed[0] and not (tmp_path / "exp").exists()


def test_a_comparison_goes_stale_when_the_other_folder_is_changed(
    window: MainWindow, project: Path, tmp_path: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    view = window.compare_view
    other = tmp_path / "other"
    shutil.copytree(project, other)
    view.set_other_folder(other)
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compare()
    view.set_other_folder(project)
    assert not view.export_button.isEnabled()


# ---- GUI-13 (Problems panel) -------------------------------------------------------------------
def test_findings_of_a_stale_timeline_leave_the_problems_panel(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    window.timeline_view.basis_combo.setCurrentText("margined")  # now stale
    assert window.timeline_view.problems() == []
