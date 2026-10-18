"""Pre-release audit, medium and low GUI findings (GUI-13 to GUI-35)."""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton, QTableView

from budget_core.io.project_loader import load_project
from budget_core.power.time_domain import Violation
from budget_core.problems import Problem, Severity
from budget_gui import timeline_view as tv
from budget_gui.main_window import MainWindow
from budget_gui.problems_panel import ProblemsPanel
from budget_gui.theme import WHITE, apply_theme, stylesheet

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg", tmp_path / "p")
    root = tmp_path / "p"
    path = root / "scenarios/one_day.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("step_s: 10.0", "step_s: 60.0"), encoding="utf-8"
    )
    return root


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def stub_messages(
    monkeypatch: pytest.MonkeyPatch, answer=QMessageBox.StandardButton.Yes
) -> list[str]:  # type: ignore[no-untyped-def]
    seen: list[str] = []

    def fake(_parent, _title, text, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        seen.append(text)
        return answer

    for name in ("question", "information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(fake))
    return seen


@pytest.fixture
def themed():  # type: ignore[no-untyped-def]
    """The look of the real application (14 px text), which sets the real minimum sizes."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    font = app.font()
    apply_theme(app)
    yield
    app.setStyleSheet("")
    app.setFont(font)


def compute_timeline(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.timeline_view.computed, timeout=120000):
        window.timeline_view.compute()


# ---- GUI-14: the export is built off the GUI thread ------------------------------------------
def test_the_timeline_export_is_built_in_the_worker_thread(
    window: MainWindow, tmp_path: Path, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    on_gui_thread: list[bool] = []
    original = tv.timeline_output

    def spy(*args, **kwargs):  # type: ignore[no-untyped-def]
        on_gui_thread.append(QThread.currentThread() is QCoreApplication.instance().thread())
        return original(*args, **kwargs)

    monkeypatch.setattr(tv, "timeline_output", spy)
    view = window.timeline_view
    with qtbot.waitSignal(view.export_finished, timeout=120000):
        view.export_to(tmp_path / "out", {"csv"})
        assert on_gui_thread == []  # nothing was built before control returned
    assert on_gui_thread == [False]


# ---- GUI-15: old tab pages are deleted ---------------------------------------------------------
def test_reloading_does_not_pile_up_table_views(window: MainWindow) -> None:
    def tables() -> int:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        window.power_view.build_pages()  # the sheets are made when first shown
        return len(window.power_view.findChildren(QTableView))

    window.session.reload()
    baseline = tables()
    assert baseline > 0
    for _ in range(8):
        window.session.reload()
    assert tables() == baseline


# ---- GUI-16: the text tab does not overwrite a file that changed on disk ----------------------
def test_saving_a_tab_over_a_newer_file_asks_first(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    editor.textCursor().insertText("# mine\n")
    path = project / "project.yaml"
    theirs = path.read_text(encoding="utf-8") + "# theirs\n"
    path.write_text(theirs, encoding="utf-8")
    seen = stub_messages(monkeypatch, QMessageBox.StandardButton.No)
    assert window.save_current() is False
    assert seen and "changed on disk" in seen[0]
    assert path.read_text(encoding="utf-8") == theirs and editor.document().isModified()
    stub_messages(monkeypatch, QMessageBox.StandardButton.Yes)
    assert window.save_current() is True
    assert "# mine" in path.read_text(encoding="utf-8")


# ---- GUI-17: table editors keep comments and key order, and write atomically --------------------
def test_a_unit_edit_keeps_the_comments_of_the_file(window: MainWindow, project: Path) -> None:
    path = project / "units/camera.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        "# source: vendor datasheet rev C\n"
        + text.replace("  - name: imaging", "  # measured\n  - name: imaging"),
        encoding="utf-8",
    )
    window.session.reload()
    editor = window.open_unit_editor("camera")
    assert editor is not None
    editor.table.item(1, 1).setText("2.5")
    assert editor.save()
    saved = path.read_text(encoding="utf-8")
    assert saved.startswith("# source: vendor datasheet rev C\n") and "  # measured\n" in saved
    assert "avg_power_w: 2.5" in saved and saved.index("name:") < saved.index("modes:")
    assert load_project(project).project is not None


def test_a_scenario_edit_keeps_the_comments_of_the_file(window: MainWindow, project: Path) -> None:
    path = project / "scenarios/one_day.yaml"
    path.write_text(
        "# Reviewed 2026-05-04\n"
        + path.read_text(encoding="utf-8").replace(
            "shadow_model:", "# eclipse model\nshadow_model:"
        ),
        encoding="utf-8",
    )
    window.session.reload()
    editor = window.scenario_view.editor
    editor.add_segment(100.0, 200.0)
    assert editor.save()
    saved = path.read_text(encoding="utf-8")
    assert saved.startswith("# Reviewed 2026-05-04\n") and "# eclipse model\n" in saved
    assert "segments:" in saved and "start_s: 100.0" in saved
    assert load_project(project).project is not None


def test_a_failed_unit_save_leaves_the_file_and_no_temporary_file(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    editor = window.open_unit_editor("camera")
    assert editor is not None
    before = (project / "units/camera.yaml").read_bytes()
    editor.table.item(1, 1).setText("2.5")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("budget_core.reports.files.os.replace", refuse)
    assert editor.save() is False
    assert "could not be written" in editor.error_label.text()
    assert (project / "units/camera.yaml").read_bytes() == before
    assert not [p for p in (project / "units").iterdir() if p.name.endswith(".tmp")]


# ---- GUI-18: link files are in the tree ---
def test_the_project_tree_lists_the_link_files(window: MainWindow) -> None:
    top = window.tree.topLevelItem(0)
    titles = [top.child(i).text(0) for i in range(top.childCount())]
    group = next(top.child(i) for i in range(top.childCount()) if titles[i].startswith("Links"))
    assert group.childCount() >= 1
    rels = {group.child(i).data(0, 0x100) for i in range(group.childCount())}
    assert all(str(r).startswith("links/") for r in rels)


# ---- GUI-19: an export from the menu says what happened ---------------------------------------
def test_the_menu_export_of_a_stale_timeline_explains_instead_of_doing_nothing(
    window: MainWindow, qtbot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    window.timeline_view.basis_combo.setCurrentText("margined")  # stale
    seen = stub_messages(monkeypatch)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    window._choose_timeline_export()
    assert seen and "out of date" in seen[0]


def test_a_finished_tab_export_names_the_folder_in_the_status_bar(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    with qtbot.waitSignal(window.timeline_view.export_finished, timeout=120000):
        window.timeline_view.export_to(tmp_path / "out", {"csv"})
    assert str(tmp_path / "out") in window.statusBar().currentMessage()


def test_a_failed_tab_export_is_shown_in_the_status_bar(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    window.timeline_view.basis_combo.setCurrentText("margined")
    window.timeline_view.export_to(Path("/nonexistent"), {"csv"})
    assert "changed" in window.statusBar().currentMessage()


# ---- GUI-20: link-pass findings reach the Problems panel ---
def test_link_pass_problems_are_listed_in_the_problems_panel(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    view = window.link_passes_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    assert view.result is not None
    finding = Problem(Severity.WARNING, "LINK_PASS_TEST", "A finding of the pass series only.")
    view.result = replace(view.result, problems=[*view.result.problems, finding])
    window._update_problems()
    assert "LINK_PASS_TEST" in {p.code for p in window.problems_panel._problems}
    window.session.reload()  # the project changed: the stale findings leave the panel
    assert "LINK_PASS_TEST" not in {p.code for p in window.problems_panel._problems}


# ---- GUI-21 and GUI-22: the text tab keeps line ends, BOM, cursor and undo ----------------------
def test_saving_a_text_tab_keeps_crlf_and_bom(window: MainWindow, project: Path) -> None:
    path = project / "project.yaml"
    path.write_bytes(
        b"\xef\xbb\xbf" + path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    )
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    editor.moveCursor(QTextCursor.MoveOperation.End)
    editor.textCursor().insertText("# end\n")
    assert window.save_current()
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"# end\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_saving_does_not_reload_the_editor_so_cursor_and_undo_stay(
    window: MainWindow,
) -> None:
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    cursor = editor.textCursor()
    cursor.setPosition(20)
    editor.setTextCursor(cursor)
    editor.textCursor().insertText("# x")
    position = editor.textCursor().position()
    assert window.save_current()
    assert editor.textCursor().position() == position
    assert editor.document().isUndoAvailable() and not editor.document().isModified()


def test_an_editor_follows_a_file_changed_by_another_program(
    window: MainWindow, project: Path
) -> None:
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    path = project / "project.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "# outside\n", encoding="utf-8")
    window.session.reload()
    assert "# outside" in editor.toPlainText()


# ---- GUI-23: jumping to a violation keeps its zoom ---
def test_jumping_to_a_violation_of_the_other_case_keeps_the_zoom(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    view = window.timeline_view
    assert view.result is not None
    finding = Violation("eol", "BATTERY_DEPLETED", 1000.0, 1200.0, None, None, "", "", "")
    view.result = replace(view.result, violations=[finding])
    view.case_combo.setCurrentText("BOL")
    view.select_violation(0)
    assert view.case_combo.currentText() == "EOL"
    assert view.plot.view() == (700.0, 1500.0) and view.plot.pinned_s() == 1000.0


# ---- GUI-24: the window fits a 1366 x 768 screen ---
def test_the_minimum_window_size_fits_a_1366_by_768_screen(
    window: MainWindow, themed: None
) -> None:
    window.show()
    QApplication.processEvents()
    for index in range(window.workspace.count()):
        window.workspace.setCurrentIndex(index)
        QApplication.processEvents()
        size = window.minimumSizeHint()
        assert size.height() <= 650 and size.width() <= 1200, window.workspace.tabText(index)


# ---- GUI-25: disabled and focused controls look different ---
def test_a_disabled_button_does_not_look_like_an_enabled_one(qtbot) -> None:  # type: ignore[no-untyped-def]
    sheet = stylesheet(WHITE)
    assert "QPushButton:disabled" in sheet and ":focus" in sheet
    button = QPushButton("Export")
    qtbot.addWidget(button)
    button.setStyleSheet(sheet)
    button.resize(120, 40)
    button.show()
    enabled = button.grab().toImage().pixelColor(60, 6)
    button.setEnabled(False)
    disabled = button.grab().toImage().pixelColor(60, 6)
    assert enabled != disabled


# ---- GUI-26: the guided wizard's parent folder ---
def test_the_wizard_expands_a_home_folder_and_refuses_a_blank_or_bad_parent(
    qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    from budget_gui.guided import GuidedWizard

    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.folder_edit.setText("~/Projects")
    assert wizard._target().parent == Path.home() / "Projects"
    wizard.folder_edit.setText("   ")
    assert wizard.issues_for("Project")
    plain = tmp_path / "afile"
    plain.write_text("x", encoding="utf-8")
    wizard.folder_edit.setText(str(plain))
    assert any("folder" in i.message.lower() for i in wizard.issues_for("Project"))


# ---- GUI-27: a flat plot does not crash ---
def test_a_panel_with_equal_limits_paints(qtbot) -> None:  # type: ignore[no-untyped-def]
    import numpy as np

    from budget_core.plots.spec import Panel, PlotSpec, Series
    from budget_gui.plot_widget import PlotWidget

    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    series = Series("s", np.array([0.0, 1.0]), np.array([2.0, 2.0]))
    widget.set_spec(PlotSpec("t", (Panel("p", "y", (series,), y_min=2.0, y_max=2.0),)))
    widget.grab()


# ---- GUI-29: small things ---
def test_ctrl_s_on_the_scenario_tab_saves_the_scenario(window: MainWindow, project: Path) -> None:
    window.show_view(window.scenario_view)
    window.scenario_view.editor.add_segment(5.0, 50.0)
    assert window.save_current() is True
    assert not window.scenario_view.editor.is_modified()
    assert load_project(project).project.scenarios["one_day"].segments  # type: ignore[union-attr]


def test_the_tree_selection_survives_a_reload(window: MainWindow) -> None:
    item = window.tree.find_item("units/gnss.yaml", kind="file")
    assert item is not None
    window.tree.setCurrentItem(item)
    chosen = window.tree.current_unit_id()
    assert chosen == "gnss"
    window.session.reload()
    assert window.tree.current_unit_id() == chosen


def test_opening_a_file_that_does_not_exist_says_so(window: MainWindow) -> None:
    window.open_file("config/not_there.yaml")
    assert "does not exist" in window.statusBar().currentMessage()


def test_menu_mnemonics_are_unique(window: MainWindow) -> None:
    keys: list[str] = []
    for action in window.menuBar().actions():
        menu = action.menu()
        assert menu is not None
        for item in menu.actions():
            text = item.text()
            if "&" in text:
                keys.append(f"{action.text()}:{text[text.index('&') + 1].lower()}")
    assert len(keys) == len(set(keys))


def test_a_cell_with_an_underscore_or_a_decimal_comma_is_not_a_number(
    window: MainWindow,
) -> None:
    editor = window.open_unit_editor("camera")
    assert editor is not None
    editor.table.item(1, 1).setText("1_0")
    assert editor.error_label.text() and editor.save() is False
    editor.table.item(1, 1).setText("1,5")
    assert "decimal point" in editor.error_label.text()
    editor.table.item(1, 1).setText("2.4")
    assert editor.error_label.text() == ""


# ---- GUI-30: the Problems panel ---
def test_errors_come_first_in_the_problems_panel(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = ProblemsPanel()
    qtbot.addWidget(panel)
    panel.set_problems(
        [
            Problem(Severity.WARNING, "W1", "a", file="a.yaml"),
            Problem(Severity.INFO, "I1", "b", file="b.yaml"),
            Problem(Severity.ERROR, "E1", "c", file="z.yaml"),
        ]
    )
    assert panel.codes() == ["E1", "W1", "I1"]
    emitted: list[tuple[str, int]] = []
    panel.jump_requested.connect(lambda f, line: emitted.append((f, line)))
    panel.activate_row(0)
    assert emitted == [("z.yaml", 1)]


def test_the_problems_panel_opens_tall_enough_for_several_rows(window: MainWindow) -> None:
    window.resize(1400, 860)
    window.show()
    QApplication.processEvents()
    assert window.problems_panel.view.height() >= 80


# ---- GUI-31: a missing comparison folder is named as such ---
def test_a_missing_comparison_folder_gets_its_own_message(
    window: MainWindow, tmp_path: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    view = window.compare_view
    view.set_other_folder(tmp_path / "nowhere")
    with qtbot.waitSignal(view.compute_failed, timeout=60000) as blocker:
        view.compare()
    assert "does not exist" in blocker.args[0]
    view.other_edit.setText("~/budget-studio-no-such-folder")
    with qtbot.waitSignal(view.compute_failed, timeout=60000) as blocker:
        view.compare()
    assert "does not exist" in blocker.args[0]


# ---- GUI-32: contrast and a missing assets folder ---
def test_severity_colours_are_readable_on_the_layer_of_both_themes() -> None:
    from budget_gui.theme import DARK, WHITE, contrast_ratio, severity_colour

    for tokens in (WHITE, DARK):
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            colour = severity_colour(tokens, severity.value)
            assert contrast_ratio(colour, tokens.layer) >= 4.5, (tokens.name, severity)


def test_missing_fonts_do_not_stop_the_start(monkeypatch: pytest.MonkeyPatch) -> None:
    from budget_gui import theme

    def missing() -> Path:
        raise FileNotFoundError("assets")

    monkeypatch.setattr(theme, "assets_dir", missing)
    assert theme.load_fonts() == []


# ---- GUI-33 and GUI-34 ---
def test_a_scenario_result_that_arrives_after_a_reload_says_the_project_changed(
    window: MainWindow, qtbot
) -> None:  # type: ignore[no-untyped-def]
    view = window.scenario_view
    view.compute()
    window.session.reload()
    with qtbot.waitSignal(view.computed, timeout=120000):
        pass
    assert view.is_stale and "changed while this ran" in view.status.text()


def test_a_second_export_is_accepted_right_after_the_first(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    compute_timeline(window, qtbot)
    view = window.timeline_view
    refused: list[str] = []
    view.export_failed.connect(refused.append)
    with qtbot.waitSignal(view.export_finished, timeout=120000):
        view.export_to(tmp_path / "a", {"csv"})
    with qtbot.waitSignal(view.export_finished, timeout=120000):
        view.export_to(tmp_path / "b", {"csv"})
    assert refused == []


def test_saving_a_text_tab_keeps_a_symbolic_link(window: MainWindow, project: Path) -> None:
    store = project / "store"
    store.mkdir()
    real = store / "camera.store"
    path = project / "units/camera.yaml"
    shutil.move(path, real)
    try:
        os.symlink(real, path)
    except OSError:
        pytest.skip("no symbolic links here")
    window.session.reload()
    window.open_file("units/camera.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    editor.textCursor().insertText("# via link\n")
    assert window.save_current()
    assert path.is_symlink() and "# via link" in real.read_text(encoding="utf-8")


# ---- GUI-26: a new project the user did not open is still announced ------------------------------
def test_a_new_project_that_is_not_opened_is_announced(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(window, "open_project", lambda _path: False)
    window._guided_created(tmp_path / "new")
    assert "was created" in window.statusBar().currentMessage()
