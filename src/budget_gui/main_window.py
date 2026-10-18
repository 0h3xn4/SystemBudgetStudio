"""Main window: project tree, budget view and file editors, Problems panel, export."""

from __future__ import annotations

import time
from collections.abc import Collection
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from budget_core import APP_NAME
from budget_core.problems import sort_problems
from budget_core.reports.files import OutputError
from budget_core.reports.run import REPORT_KINDS
from budget_gui import theme
from budget_gui.compare_view import CompareView
from budget_gui.editor import EditorTabs, FileChangedError, YamlEditor
from budget_gui.guided import GuidedWizard
from budget_gui.help_view import GuideDialog
from budget_gui.layout_settings import LayoutSettings
from budget_gui.legend import LegendDialog
from budget_gui.link_view import LinkPassesView
from budget_gui.privacy import disable_settings_files
from budget_gui.problem_class import ProblemClass
from budget_gui.problems_panel import ProblemsPanel
from budget_gui.project_tree import ProjectTree
from budget_gui.reports_view import ReportsView
from budget_gui.run_controller import RunController, RunState
from budget_gui.scenario_view import ScenarioView
from budget_gui.session import ProjectSession
from budget_gui.status_bar import AppStatusBar
from budget_gui.timeline_view import PowerTimelineView
from budget_gui.top_bar import TopBar
from budget_gui.unit_editor import UnitEditor
from budget_gui.unit_table import export_unit_table, import_unit_table
from budget_gui.widgets import PowerView
from budget_gui.worker import ExportWorker
from budget_gui.workspace import TABS, SubTabs, Workspace


def _path_tokens(path: str) -> tuple[str | int, ...]:
    """'limits[0].limit_kg' -> ('limits', 0, 'limit_kg'), the keys of the file's line map."""
    tokens: list[str | int] = []
    for part in path.split("."):
        name, *indices = part.split("[")
        if name:
            tokens.append(name)
        for index in indices:
            digits = index.rstrip("]")
            if digits.isdigit():
                tokens.append(int(digits))
    return tuple(tokens)


class MainWindow(QMainWindow):
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        disable_settings_files()  # also when the window is made without create_app
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        self.session = ProjectSession()
        self.layout_settings = LayoutSettings.default()
        self.tree = ProjectTree()
        self.problems_panel = ProblemsPanel()
        self.power_view = PowerView()
        self.mass_view = PowerView()
        self.thermal_view = PowerView()
        self.link_view = PowerView()
        self.editors = EditorTabs()  # the Model tab: the scenario, the files, the unit tables
        self.scenario_view = ScenarioView()
        self.editors.add_fixed(self.scenario_view, "Scenario")
        self.editors.register_modifiable(self.scenario_view.editor)
        self.timeline_view = PowerTimelineView()
        self.timeline_view.run_provider = self.scenario_view.reusable_run
        self.link_passes_view = LinkPassesView()
        self.link_passes_view.run_provider = self.scenario_view.reusable_run
        self.compare_view = CompareView()
        self.reports_view = ReportsView()
        self.workspace = Workspace()
        self.workspace.add_page("Model", self.editors)
        self.workspace.add_page(
            "Power", SubTabs([("Budget", self.power_view), ("Timeline", self.timeline_view)])
        )
        self.workspace.add_page("Mass", self.mass_view)
        self.workspace.add_page("Thermal", self.thermal_view)
        self.workspace.add_page(
            "Link", SubTabs([("Budget", self.link_view), ("Passes", self.link_passes_view)])
        )
        self.workspace.add_page("Compare", self.compare_view)
        self.workspace.add_page("Reports", self.reports_view)
        self.top_bar = TopBar()
        self.run_controller = RunController(
            self.scenario_view, self.timeline_view, self.link_passes_view
        )
        self.scenario_view.use_shared_selector()
        self.timeline_view.use_shared_selectors()
        self.link_passes_view.use_shared_selector()
        central = QWidget()
        stack = QVBoxLayout(central)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)
        stack.addWidget(self.top_bar)
        stack.addWidget(self.workspace, 1)
        self.setCentralWidget(central)
        self.workspace.setCurrentIndex(1)  # Power: a project opens on its budgets
        self._worker: ExportWorker | None = None

        left = QDockWidget("Project", self)
        left.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left)
        bottom = QDockWidget("Problems", self)
        bottom.setWidget(self.problems_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom)
        self.resizeDocks([bottom], [170], Qt.Orientation.Vertical)  # room for several rows
        self.status_bar = AppStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "Offline. File > Open project, or File > New project (guided), starts a budget."
        )
        self.status_bar.not_checked_requested.connect(self.show_not_checked)
        self.problems_dock = bottom

        self._build_menu()
        self.session.changed.connect(self._refresh)
        self.session.loading_changed.connect(self._loading_changed)
        self.scenario_view.editor.saved.connect(self.reload_project)
        self.top_bar.scenario_chosen.connect(self.select_scenario)
        self.top_bar.case_chosen.connect(self.timeline_view.case_combo.setCurrentText)
        self.timeline_view.case_combo.currentTextChanged.connect(self.top_bar.set_case)
        self.top_bar.run_requested.connect(self.run_all)
        self.run_controller.changed.connect(self._update_run_state)
        self.editors.dirty_changed.connect(self._update_dirty)
        self.scenario_view.editor.modified_changed.connect(lambda _m: self._update_dirty())
        self.reports_view.reports_requested.connect(self._choose_export)
        self.reports_view.timeline_requested.connect(self._choose_timeline_export)
        self.reports_view.scenario_requested.connect(self._choose_scenario_export)
        self.tree.file_requested.connect(self._tree_file)
        self.tree.field_requested.connect(self.jump_to_input)
        self.tree.unit_requested.connect(lambda unit_id: self.open_unit_editor(unit_id))
        self.problems_panel.jump_requested.connect(lambda rel, line: self.open_file(rel, line))
        self._export_folder = Path()
        self.timeline_view.computed.connect(lambda _result: self._update_problems())
        self.link_passes_view.computed.connect(lambda _result: self._update_problems())
        for computing in (self.scenario_view, self.timeline_view, self.link_passes_view):
            computing.computed.connect(lambda _result: self._mark_run())
        self.timeline_view.jump_requested.connect(self.jump_to_input)
        for view in (self.timeline_view, self.link_passes_view, self.compare_view):
            view.export_finished.connect(self._view_export_done)
            view.export_failed.connect(self._view_export_failed)
        self._closing = False  # a close was asked for while a job runs
        self._last_run: datetime | None = None

    # ---- actions -----------------------------------------------------------------------------
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        def add(text: str, shortcut: QKeySequence | QKeySequence.StandardKey, slot: object) -> None:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)

        add("&New project (guided)…", QKeySequence.StandardKey.New, self.open_guided_wizard)
        add("&Open project…", QKeySequence.StandardKey.Open, self._choose_project)
        add("&Save file", QKeySequence.StandardKey.Save, self.save_current)
        add("&Reload project", QKeySequence(Qt.Key.Key_F5), self.reload_project)
        file_menu.addSeparator()
        add("Edit unit &power modes\u2026", QKeySequence("Ctrl+M"), self._edit_selected_unit)
        add("&Export reports…", QKeySequence("Ctrl+E"), self._choose_export)
        add("Export power &timeline…", QKeySequence("Ctrl+Shift+E"), self._choose_timeline_export)
        add("Export s&cenario results…", QKeySequence(), self._choose_scenario_export)
        file_menu.addSeparator()
        add("Export &unit table…", QKeySequence(), lambda: export_unit_table(self))
        add("&Import unit table…", QKeySequence(), lambda: import_unit_table(self))
        file_menu.addSeparator()
        add("&Quit", QKeySequence.StandardKey.Quit, self.close)
        self._build_run_menu()
        self._build_view_menu()
        help_menu = self.menuBar().addMenu("&Help")
        guide = QAction("&User guide", self)
        guide.setShortcut(QKeySequence.StandardKey.HelpContents)
        guide.triggered.connect(lambda: self.open_guide())
        help_menu.addAction(guide)

    def _build_run_menu(self) -> None:
        run_menu = self.menuBar().addMenu("&Run")
        self.run_action = QAction("&Run all", self)
        self.run_action.setShortcut(QKeySequence("Ctrl+R"))
        self.run_action.setStatusTip(
            "Work out the scenario, the power timeline and the link passes of the scenario."
        )
        self.run_action.triggered.connect(self.run_all)
        run_menu.addAction(self.run_action)

    def _build_view_menu(self) -> None:
        view_menu = self.menuBar().addMenu("&View")
        for number, title in enumerate(TABS, start=1):
            action = QAction(f"Go to {title}", self)
            action.setShortcut(QKeySequence(f"Ctrl+{number}"))
            action.triggered.connect(lambda _checked=False, n=number - 1: self._go_to_tab(n))
            view_menu.addAction(action)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("&Theme")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.theme_actions: dict[theme.Mode, QAction] = {}
        for mode, text in (
            (theme.Mode.LIGHT, "&Light"),
            (theme.Mode.DARK, "&Dark"),
            (theme.Mode.SYSTEM, "&Same as the system"),
        ):
            action = QAction(text, self)
            action.setCheckable(True)
            action.setChecked(theme.manager().mode is mode)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_theme(m))
            group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[mode] = action
        view_menu.addSeparator()
        styles = QAction("&Cell styles…", self)
        styles.triggered.connect(lambda: self.show_cell_styles())
        view_menu.addAction(styles)

    def _go_to_tab(self, index: int) -> None:
        self.workspace.setCurrentIndex(index)
        page = self.workspace.currentWidget()
        if page is not None:
            page.setFocus()

    def set_theme(self, mode: theme.Mode) -> None:
        """Switch the theme now and keep the choice for the next start."""
        theme.manager().set_mode(mode)
        self.theme_actions[mode].setChecked(True)
        self.layout_settings.set_word("theme/mode", mode.value, tuple(m.value for m in theme.Mode))
        self.layout_settings.sync()

    def show_cell_styles(self) -> LegendDialog:
        """The legend of the cell styles (placeholder, n/a, limit states, margin bars)."""
        dialog = LegendDialog(self)
        dialog.open()
        return dialog

    def open_guided_wizard(self, parent_folder: Path | None = None) -> GuidedWizard:
        """Show the guided new-project wizard; on Finish the project opens and its first power
        timeline is computed."""
        folder = (
            parent_folder if isinstance(parent_folder, Path) else Path.home() / "SystemBudgetStudio"
        )
        wizard = GuidedWizard(folder, self)
        wizard.created.connect(self._guided_created)
        wizard.open()
        return wizard

    def open_guide(self) -> GuideDialog:
        """The user guide; with a project open it also lists that project's numbers and sources."""
        dialog = GuideDialog(self.session.project, self)
        dialog.open()
        return dialog

    def _guided_created(self, folder: Path) -> None:
        if not self.open_project(folder):
            # the new project exists on disk; the user kept their edits in the old one
            self.statusBar().showMessage(
                f"The new project was created in {folder}. Open it with File > Open project."
            )
            return
        self.show_view(self.timeline_view)
        self.timeline_view.compute()

    def _choose_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open project folder")
        if folder:
            self.open_project(Path(folder), background=True)

    def _choose_scenario_export(self) -> None:
        if self.scenario_view.last_run is None:
            QMessageBox.information(
                self, APP_NAME, "Compute the scenario first (Scenario tab, button Compute)."
            )
            return
        if self.scenario_view.is_stale:
            QMessageBox.information(
                self,
                APP_NAME,
                "The scenario results are out of date: the project changed since they were "
                "computed. Press Compute in the Scenario tab, then export.",
            )
            return
        folder = QFileDialog.getExistingDirectory(self, "Export scenario results to folder")
        if not folder:
            return
        try:
            written = self.scenario_view.export_to(Path(folder))
            self.statusBar().showMessage(f"Exported {len(written)} file(s) to {folder}.")
        except (OutputError, OSError) as exc:
            # OutputError texts are plain by construction; an OSError is described, not echoed
            text = (
                str(exc)
                if isinstance(exc, OutputError)
                else "The files could not be written. Check that you may write to the folder."
            )
            QMessageBox.warning(self, APP_NAME, text)

    def _choose_timeline_export(self) -> None:
        if self.timeline_view.result is None:
            QMessageBox.information(
                self, APP_NAME, "Compute the power timeline first (Power timeline tab)."
            )
            return
        if not self.timeline_view.is_valid():
            QMessageBox.information(
                self,
                APP_NAME,
                "The power timeline is out of date: the project or a setting changed since it "
                "was computed. Press Compute in the Power timeline tab, then export.",
            )
            return
        folder = QFileDialog.getExistingDirectory(self, "Export power timeline to folder")
        if folder:
            self.timeline_view.export_to(Path(folder), set(REPORT_KINDS))

    def _edit_selected_unit(self) -> None:
        unit_id = self.tree.current_unit_id()
        if unit_id:
            self.open_unit_editor(unit_id)

    def _choose_export(self) -> None:
        if not self.session.outputs:
            QMessageBox.information(
                self,
                APP_NAME,
                "There is no budget to export yet. Fix the errors in the Problems panel first.",
            )
            return
        folder = QFileDialog.getExistingDirectory(self, "Export reports to folder")
        if folder:
            self.export_to(Path(folder), set(REPORT_KINDS))

    # ---- project -----------------------------------------------------------------------------
    def open_project(self, path: Path, *, background: bool = False) -> bool:
        """Open a project folder. Returns False (and changes nothing) when the user keeps
        unsaved edits instead of discarding them. With `background` the project loads in a
        thread (the window stays usable) and `session.changed` says when it is in; the
        interactive entry points use that, programs and tests wait for the result."""
        if self.editors.has_unsaved_changes():
            if not self.editors.confirm_discard("Some files have unsaved changes."):
                return False
            self.editors.discard_all_changes()
        self.editors.close_all_files()
        if background:
            self.session.open_async(Path(path))
        else:
            self.session.open(Path(path))
        return True

    def reload_project(self) -> None:
        """Load the open project again without freezing the window (F5, after a save)."""
        self.session.reload_async()

    # ---- top bar -----------------------------------------------------------------------------
    def _tree_file(self, rel: str) -> None:
        self.open_file(rel)
        project = self.session.project
        stem = Path(rel).stem
        if rel.startswith("scenarios/") and project is not None and stem in project.scenarios:
            self.select_scenario(stem)

    def select_scenario(self, scenario_id: str) -> None:
        """Choose the scenario every tab shows. The scenario editor may refuse (it has unsaved
        edits that belong to another scenario); then nothing changes."""
        if self.scenario_view.selected_id() != scenario_id:
            self.scenario_view.combo.setCurrentText(scenario_id)  # asks before dropping edits
        chosen = self.scenario_view.selected_id()
        for combo in (self.timeline_view.scenario_combo, self.link_passes_view.scenario_combo):
            if combo.currentText() != chosen:
                combo.setCurrentText(chosen)
        self.top_bar.set_scenario(chosen)
        self._update_run_state()

    def run_all(self) -> bool:
        """Run: the scenario, the power timeline and the link passes of the selected scenario."""
        if not self.run_controller.run():
            self.status_bar.showMessage(
                "Nothing to run: open a project that has a scenario, and wait for a run in "
                "progress to end."
            )
            return False
        self._update_run_state()
        return True

    def _update_run_state(self) -> None:
        controller = self.run_controller
        state = controller.state()
        tips = {
            RunState.NOT_RUN: "The scenario, the power timeline and the link passes have not "
            "been worked out for this scenario. Press Run (Ctrl+R).",
            RunState.RUNNING: "Working out the scenario, the power timeline and the link passes.",
            RunState.OK: "Everything was worked out from the inputs now on screen.",
            RunState.STALE: "The project or a setting changed since the last run. Press Run.",
            RunState.FAILED: controller.failure or "",
        }
        detail = ""
        if state is RunState.OK and self._last_run is not None:
            detail = f"{self._last_run:%H:%M:%S}"
        self.top_bar.set_run_state(state, controller.can_run(), detail, tips[state])
        self.run_action.setEnabled(controller.can_run())

    def _update_dirty(self) -> None:
        dirty = self.editors.has_unsaved_changes()
        self.top_bar.set_dirty(dirty)
        name = self.top_bar.name_label.text()
        has_project = self.session.project is not None or self.session.path is not None
        if has_project and name:
            self.setWindowTitle(f"{'● ' if dirty else ''}{name} — {APP_NAME}")

    def _mark_run(self) -> None:
        """Something was worked out just now: say so in the status bar."""
        self._last_run = datetime.now()
        self.status_bar.set_last_run(self._last_run)
        self._update_run_state()

    def show_not_checked(self) -> None:
        """List the 'not checked' findings (the link in the status bar)."""
        self.problems_panel.set_class_filter(ProblemClass.NOT_CHECKED)
        self.problems_dock.show()
        self.problems_dock.raise_()
        self.problems_panel.setFocus()

    def _loading_changed(self, loading: bool) -> None:
        if loading:
            self.statusBar().showMessage("Loading the project… the window stays usable.")

    def open_file(self, rel: str, line: int | None = None) -> None:
        if self.session.path is None:
            return
        if not (self.session.path / rel).is_file():
            self.statusBar().showMessage(
                f"{rel} does not exist yet. Create it in the project folder, then press F5."
            )
            return
        self.editors.open_file(self.session.path, rel, line)
        self.workspace.show_view(self.editors)

    def _line_of(self, rel: str, path: str) -> int | None:
        lines = self.session.load_result.lines.get(rel) if self.session.load_result else None
        if lines is None:
            return None
        return lines.lookup(_path_tokens(path))

    def jump_to_input(self, rel: str, path: str) -> None:
        """Open the file that governs a finding at the line of the named field."""
        self.open_file(rel, self._line_of(rel, path))

    def open_unit_editor(self, unit_id: str) -> UnitEditor | None:
        """Open (or focus) the power-mode table editor of a unit of the loaded project."""
        project = self.session.project
        if project is None or self.session.path is None or unit_id not in project.units:
            QMessageBox.information(
                self,
                APP_NAME,
                "Fix the errors in the Problems panel first; "
                "the table editor needs a project that loads.",
            )
            return None
        existing = self.editors.unit_editor(unit_id)
        if existing is not None:
            self.show_view(existing)
            return existing
        editor = UnitEditor(self.session.path, unit_id, project.units[unit_id])
        editor.saved.connect(self.reload_project)
        self.editors.add_unit_editor(unit_id, editor)
        self.workspace.show_view(self.editors)
        return editor

    def show_view(self, widget: QWidget) -> bool:
        """Bring any view to the front: its tab, and its page inside the tab."""
        if self.editors.indexOf(widget) >= 0:
            self.editors.setCurrentWidget(widget)
            return self.workspace.show_view(self.editors)
        return self.workspace.show_view(widget)

    def save_current(self) -> bool:
        if self.workspace.currentWidget() is not self.editors:
            return False  # Save belongs to the editors of the Model tab
        if self.editors.currentWidget() is self.scenario_view:
            return self.scenario_view.editor.save()
        unit_editor = self.editors.current_unit_editor()
        if unit_editor is not None:
            return unit_editor.save()
        editor = self.editors.current_editor()
        if editor is None:
            return False
        if not self._write(editor):
            return False
        self.reload_project()
        return True

    def _write(self, editor: YamlEditor) -> bool:
        """Save a text tab; asks before overwriting a file that changed on disk."""
        try:
            try:
                editor.save()
            except FileChangedError:
                answer = QMessageBox.question(
                    self,
                    APP_NAME,
                    f"The file {editor.rel_path} changed on disk after it was opened in this "
                    "tab. Overwrite it with the text in this tab?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return False
                editor.save(overwrite=True)
        except (OSError, OutputError):
            QMessageBox.warning(
                self,
                APP_NAME,
                "The file could not be saved. Check that you may write to the project folder.",
            )
            return False
        return True

    def _refresh(self) -> None:
        session = self.session
        project = session.project
        self.tree.set_project(session.path, project)
        self.power_view.set_document(session.document)
        self.mass_view.set_document(session.mass_document)
        self.thermal_view.set_document(session.thermal_document)
        self.link_view.set_document(session.link_document)
        self.scenario_view.set_project(project)
        load_problems = session.load_result.problems if session.load_result else []
        self.timeline_view.set_project(project, load_problems)
        self.link_passes_view.set_project(project, load_problems)
        self.compare_view.set_project(project)
        self._update_problems()
        self.editors.reload_clean_files(project.units if project else None)
        name = project.meta.name if project else (session.path.name if session.path else "")
        self.top_bar.set_project(name, project.meta.revision if project else "")
        self.setWindowTitle(f"{name} — {APP_NAME}" if name else APP_NAME)
        ids = sorted(project.scenarios) if project else []
        self.top_bar.set_scenarios(ids, self.scenario_view.selected_id())
        self.select_scenario(self.scenario_view.selected_id())
        self.run_controller.reset_failure()
        self._last_run = datetime.now() if project else None
        self.status_bar.set_project_path(session.path)
        self.status_bar.set_last_run(self._last_run)
        self._update_dirty()
        self.statusBar().showMessage(f"{name}: {self.problems_panel.summary.text()}")

    def _update_problems(self) -> None:
        """Project problems plus the findings of the last power timeline (violations, gaps), each
        with the line of its input so the panel can jump to it."""
        known = {(p.code, p.file, p.path, p.message) for p in self.session.problems}
        extra = [
            p
            for p in [*self.timeline_view.problems(), *self.link_passes_view.problems()]
            if (p.code, p.file, p.path, p.message) not in known
        ]
        located = [
            replace(p, line=self._line_of(p.file, p.path))
            if p.line is None and p.file and p.path
            else p
            for p in [*self.session.problems, *extra]
        ]
        shown = sort_problems(located)
        self.problems_panel.set_problems(shown, project_open=self.session.path is not None)
        self.tree.set_problems(shown)
        self.status_bar.set_not_checked(self.problems_panel.counts()[ProblemClass.NOT_CHECKED])
        if self.session.project is not None:
            name = self.session.project.meta.name
            self.statusBar().showMessage(f"{name}: {self.problems_panel.summary.text()}")

    # ---- export ------------------------------------------------------------------------------
    def export_to(self, folder: Path, kinds: Collection[str]) -> None:
        session = self.session
        if self._worker is not None:
            self.export_failed.emit("An export is already running; wait for it to finish.")
            return
        if not session.outputs:
            self.export_failed.emit("There is no budget to export; fix the errors first.")
            return
        worker = ExportWorker(session.outputs, folder, kinds)
        worker.finished_ok.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        self._worker = worker
        self._export_folder = folder
        self.statusBar().showMessage("Exporting…")
        worker.start()

    def _end_export(self) -> None:
        if self._worker is not None:
            self._worker.wait()  # the signal arrives just before the thread ends
            self._worker = None

    def _export_done(self, paths: list[str]) -> None:
        self._end_export()
        self.statusBar().showMessage(f"Exported {len(paths)} file(s) to {self._export_folder}.")
        self.export_finished.emit(paths)

    def _export_failed(self, message: str) -> None:
        self._end_export()
        self.statusBar().showMessage(message)
        self.export_failed.emit(message)

    def _view_export_done(self, paths: list[str]) -> None:
        """An export started from a tab (or from the File menu for a tab) finished."""
        where = f" to {Path(paths[0]).parent}" if paths else ""
        self.statusBar().showMessage(f"Exported {len(paths)} file(s){where}.")

    def _view_export_failed(self, message: str) -> None:
        self.statusBar().showMessage(message)

    # ---- closing -----------------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        if self.editors.has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "Some files have unsaved changes. Close without saving?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
            self.editors.discard_all_changes()  # chosen once; a close that waits does not ask again
        if self.busy():
            # a running thread cannot be stopped safely: close when it is done, do not freeze
            self._closing = True
            self.statusBar().showMessage(
                "A computation or an export is still running. The window closes when it is done."
            )
            event.ignore()
            QTimer.singleShot(200, self._close_when_idle)
            return
        event.accept()

    def busy(self) -> bool:
        """A computation or an export is running in a background thread."""
        views = (self.scenario_view, self.timeline_view, self.link_passes_view, self.compare_view)
        return self._worker is not None or self.session.loading or any(v.is_busy() for v in views)

    def wait_for_jobs(self, timeout_s: float = 120.0) -> bool:
        """Let the running jobs finish (their results are delivered); False on timeout."""
        deadline = time.monotonic() + timeout_s
        while self.busy() and time.monotonic() < deadline:
            QApplication.processEvents()
            QThread.msleep(10)
        return not self.busy()

    def _close_when_idle(self) -> None:
        if not self._closing:
            return
        if self.busy():
            QTimer.singleShot(200, self._close_when_idle)
            return
        self._closing = False
        self.close()
