"""Scenario view: compute in a worker, edit rules and segments, stale results, errors, export."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_gui.main_window import MainWindow
from tests.helpers import edit

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.scenario_view.computed, timeout=120000):
        window.scenario_view.compute()


def test_the_scenario_is_listed_and_not_computed_yet(window: MainWindow) -> None:
    view = window.scenario_view
    assert [view.combo.itemText(i) for i in range(view.combo.count())] == ["one_day"]
    assert view.last_run is None and "Not computed" in view.status.text()
    assert (
        window.tree.file_item_count() >= 6 + 5 + 2 + 4 + 2 + 1 + 1 + 1
    )  # incl. orbit, sites, scenario


def test_compute_runs_in_a_worker_and_fills_timeline_and_tables(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    view = window.scenario_view
    run = view.last_run
    assert run is not None and run.scenario_id == "one_day"
    assert view.eclipse_table.rowCount() == len(run.env.eclipses) >= 12
    assert view.passes_table.rowCount() == sum(len(v.passes) for v in run.env.sites.values())
    assert view.timeline_table.rowCount() == len(run.timeline)
    assert view.timeline.rows() == ["Sunlight", "gs_north", "gs_south", "tgt_plains", "Mode"]
    assert "eclipse" in view.status.text().lower() and not view.is_stale
    assert view.compute_button.isEnabled()


def test_editing_the_default_mode_rebuilds_the_timeline_without_recomputing(
    window: MainWindow, project: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    view = window.scenario_view
    env_before = view.last_run.env  # type: ignore[union-attr]
    view.editor.default_mode.setCurrentText("safe")
    assert view.editor.is_modified()
    assert view.editor.save() is True
    assert "default_mode: safe" in (project / "scenarios" / "one_day.yaml").read_text(
        encoding="utf-8"
    )
    assert view.last_run is not None and view.last_run.env is env_before  # environment reused
    assert view.last_run.scenario.default_mode == "safe"
    assert "timeline updated" in view.status.text().lower()
    assert not view.editor.is_modified()


def test_rules_can_be_added_changed_and_removed(window: MainWindow, project: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    editor = window.scenario_view.editor
    before = editor.rules_table.rowCount()
    editor.add_rule()
    editor.set_rule(before, kind="in_sunlight", site="", mode="charging")
    editor.remove_rule(0)
    assert editor.save() is True
    text = (project / "scenarios" / "one_day.yaml").read_text(encoding="utf-8")
    assert "in_sunlight" in text and text.count("kind: in_eclipse") == 0
    assert editor.rules_table.rowCount() == before


def test_an_invalid_rule_is_explained_and_not_saved(window: MainWindow, project: Path) -> None:
    editor = window.scenario_view.editor
    before = (project / "scenarios" / "one_day.yaml").read_bytes()
    editor.add_rule()
    editor.set_rule(editor.rules_table.rowCount() - 1, kind="during_pass", site="", mode="safe")
    assert editor.save() is False
    assert "site" in editor.error_label.text().lower()
    assert (project / "scenarios" / "one_day.yaml").read_bytes() == before


def test_selecting_a_range_on_the_timeline_adds_a_manual_segment(
    window: MainWindow, project: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    view = window.scenario_view
    view.timeline.range_selected.emit(100.0, 400.0)
    assert view.editor.segments_table.rowCount() == 1
    assert view.editor.segment(0) == (100.0, 300.0, view.editor.default_mode.currentText())
    view.editor.set_segment(0, start=100.0, duration=300.0, mode="safe")
    assert view.editor.save() is True
    assert "mode: safe" in (project / "scenarios" / "one_day.yaml").read_text(encoding="utf-8")
    seg = next(s for s in view.last_run.timeline if s.start_s == 100.0)  # type: ignore[union-attr]
    assert (seg.end_s, seg.mode) == (400.0, "safe")


def test_overlapping_segments_are_reported(window: MainWindow) -> None:
    editor = window.scenario_view.editor
    editor.add_segment(0.0, 500.0)
    editor.add_segment(100.0, 500.0)
    assert editor.save() is False and "overlap" in editor.error_label.text().lower()


def test_changing_environment_parameters_marks_results_stale(
    window: MainWindow, project: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    view = window.scenario_view
    window.tree.request_file("scenarios/one_day.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    from PySide6.QtGui import QTextCursor

    cursor = QTextCursor(editor.document())
    cursor.select(QTextCursor.SelectionType.Document)
    cursor.insertText(editor.toPlainText().replace("step_s: 10.0", "step_s: 20.0"))
    assert window.save_current() is True
    assert view.is_stale and "changed" in view.status.text().lower()
    compute(window, qtbot)
    assert not view.is_stale and view.last_run.scenario.step_s == 20.0  # type: ignore[union-attr]


def test_project_errors_disable_the_view(window: MainWindow, project: Path) -> None:
    edit(project, "scenarios/one_day.yaml", "orbit: leo", "orbit: nope")
    window.session.reload()
    view = window.scenario_view
    assert view.empty_label.isVisibleTo(window) or not view.compute_button.isEnabled()
    assert not view.compute_button.isEnabled()


def test_a_failing_run_is_a_plain_message_not_a_traceback(
    window: MainWindow, project: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    folder = project / "imports" / "run1"
    folder.mkdir(parents=True)
    (folder / "orbit.csv").write_text(
        "time_utc,x_m,y_m,z_m,vx_mps,vy_mps,vz_mps\nSECRET,1\n", encoding="utf-8"
    )
    edit(
        project,
        "scenarios/one_day.yaml",
        "environment_source: elements\norbit: leo",
        "environment_source: spacemissionstudio\nimport_dir: imports/run1",
    )
    window.session.reload()
    view = window.scenario_view
    with qtbot.waitSignal(view.compute_failed, timeout=60000):
        view.compute()
    text = view.status.text()
    assert "ENV_INPUT_INVALID" in text and "orbit.csv" in text
    assert "Traceback" not in text and "SECRET" not in text
    assert view.compute_button.isEnabled() and view.last_run is None


def test_export_writes_the_scenario_files(window: MainWindow, qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    written = window.scenario_view.export_to(tmp_path / "out")
    assert sorted(p.name for p in written) == [
        "one_day_eclipses.csv",
        "one_day_environment.json",
        "one_day_passes.csv",
        "one_day_provenance.csv",
        "one_day_timeline.csv",
    ]


def test_unsaved_scenario_edits_block_closing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    window.scenario_view.editor.default_mode.setCurrentText("safe")
    assert window.editors.has_unsaved_changes()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert window.close() is False
    window.editors.discard_all_changes()
    assert not window.editors.has_unsaved_changes()


# ---- File menu: export the scenario results ----------------------------------------------------


def _menu_action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for menu in window.menuBar().findChildren(type(window.menuBar().actions()[0].menu())):
        for action in menu.actions():
            if action.text().replace("&", "") == text:
                return action
    raise AssertionError(f"no menu entry {text!r}")


def test_the_file_menu_exports_the_scenario_results(
    window: MainWindow, qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QFileDialog

    compute(window, qtbot)
    out = tmp_path / "chosen"
    out.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(out))
    _menu_action(window, "Export scenario results…").trigger()
    assert sorted(p.name for p in out.iterdir()) == [
        "one_day_eclipses.csv",
        "one_day_environment.json",
        "one_day_passes.csv",
        "one_day_provenance.csv",
        "one_day_timeline.csv",
    ]


def test_exporting_before_computing_explains_what_to_do(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, text: shown.append(text))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: pytest.fail("no folder prompt")
    )
    _menu_action(window, "Export scenario results…").trigger()
    assert len(shown) == 1
    assert "Scenario tab" in shown[0] and "Compute" in shown[0]
    assert "Ctrl+R" not in shown[0]  # there is no such shortcut


def test_a_folder_that_cannot_be_written_gives_a_plain_message(
    window: MainWindow, qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    compute(window, qtbot)
    not_a_folder = tmp_path / "file.txt"
    not_a_folder.write_text("x", encoding="utf-8")
    warned: list[str] = []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(not_a_folder))
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warned.append(text))
    _menu_action(window, "Export scenario results…").trigger()
    assert len(warned) == 1 and "Traceback" not in warned[0]
    assert "folder" in warned[0]
