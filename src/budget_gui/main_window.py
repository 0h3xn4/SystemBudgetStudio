"""Main window: project tree, budget view and file editors, Problems panel, export."""

from __future__ import annotations

import time
from collections.abc import Collection
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence, QShowEvent
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
from budget_gui import problem_class as pc
from budget_gui import theme
from budget_gui.banner import Banner
from budget_gui.compare_view import CompareView
from budget_gui.editor import EditorTabs, FileChangedError, YamlEditor
from budget_gui.guided import GuidedWizard
from budget_gui.help_view import GuideDialog
from budget_gui.inspector import InspectorPanel
from budget_gui.layout_settings import LayoutSettings
from budget_gui.legend import LegendDialog
from budget_gui.link_view import LinkPassesView
from budget_gui.model_document import ModelDocument
from budget_gui.model_pages import InputsPage, PowerModesPage, UnitsPage
from budget_gui.privacy import disable_settings_files
from budget_gui.problem_class import ProblemClass
from budget_gui.problems_panel import ProblemsPanel
from budget_gui.project_tree import ProjectTree
from budget_gui.provenance_panel import ProvenancePanel
from budget_gui.reports_view import ReportsView
from budget_gui.run_controller import RunController, RunState
from budget_gui.scenario_view import ScenarioView
from budget_gui.session import ProjectSession
from budget_gui.status_bar import AppStatusBar
from budget_gui.timeline_view import PowerTimelineView
from budget_gui.top_bar import TopBar
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

    def __init__(self, layout: LayoutSettings | None = None) -> None:
        super().__init__()
        disable_settings_files()  # also when the window is made without create_app
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        self.session = ProjectSession()
        self.layout_settings = layout if layout is not None else LayoutSettings.default()
        self.tree = ProjectTree()
        self.problems_panel = ProblemsPanel()
        self.inspector = InspectorPanel()
        self.provenance_panel = ProvenancePanel()
        self.power_view = PowerView()
        self.mass_view = PowerView()
        self.thermal_view = PowerView()
        self.link_view = PowerView()
        self.editors = EditorTabs()  # the Model tab: the grids, the scenario and the open files
        self.document = ModelDocument()  # what the grids and the scenario edit: one undo stack
        self.units_page = UnitsPage(self.document)
        self.modes_page = PowerModesPage(self.document)
        self.inputs_page = InputsPage(self.document)
        for title, page in (
            ("Units", self.units_page),
            ("Power modes", self.modes_page),
            ("Inputs", self.inputs_page),
        ):
            self.editors.add_fixed(page, title)
            page.save_requested.connect(self.save_model)
            page.legend_requested.connect(self.show_cell_styles)
        self.editors.register_modifiable(self.document)
        self.scenario_view = ScenarioView(self.document)
        self.editors.add_fixed(self.scenario_view, "Scenario")
        self.scenario_view.editor.save_requested.connect(self.save_model)
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
        self.stale_banner = Banner("stale")
        self.failed_banner = Banner("failed")
        stack.addWidget(self.top_bar)
        stack.addWidget(self.stale_banner)
        stack.addWidget(self.failed_banner)
        stack.addWidget(self.workspace, 1)
        self.setCentralWidget(central)
        self.workspace.setCurrentIndex(1)  # Power: a project opens on its budgets
        self._worker: ExportWorker | None = None

        self.project_dock = self._dock("Project", "dock-project", self.tree)
        self.inspector_dock = self._dock("Inspector", "dock-inspector", self.inspector)
        self.problems_dock = self._dock("Problems", "dock-problems", self.problems_panel)
        self.provenance_dock = self._dock("Provenance", "dock-provenance", self.provenance_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        for dock in (self.inspector_dock, self.problems_dock, self.provenance_dock):
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self.inspector_dock, self.problems_dock)
        self.tabifyDockWidget(self.problems_dock, self.provenance_dock)
        self.problems_dock.raise_()
        self._sized = False  # the dock widths are set when the window is first shown
        self.status_bar = AppStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "Offline. File > Open project, or File > New project (guided), starts a budget."
        )
        self.status_bar.not_checked_requested.connect(self.show_not_checked)
        self._default_state = self.saveState()  # what View > Reset layout goes back to
        self._restore_layout()

        self._build_menu()
        self.session.changed.connect(self._refresh)
        self.session.loading_changed.connect(self._loading_changed)
        self.document.saved.connect(self.reload_project)
        self.document.dirty_changed.connect(lambda _d: self._update_dirty())
        self.top_bar.scenario_chosen.connect(self.select_scenario)
        self.top_bar.case_chosen.connect(self.timeline_view.case_combo.setCurrentText)
        self.timeline_view.case_combo.currentTextChanged.connect(self.top_bar.set_case)
        self.top_bar.run_requested.connect(self.run_all)
        self.stale_banner.action_requested.connect(self.show_first_error)
        self.failed_banner.action_requested.connect(self.run_all)
        self.run_controller.changed.connect(self._update_run_state)
        self.editors.dirty_changed.connect(self._update_dirty)
        self.reports_view.reports_requested.connect(self._choose_export)
        self.reports_view.timeline_requested.connect(self._choose_timeline_export)
        self.reports_view.scenario_requested.connect(self._choose_scenario_export)
        self.tree.file_requested.connect(self._tree_file)
        self.tree.field_requested.connect(self.jump_to_input)
        self.tree.currentItemChanged.connect(lambda _current, _previous: self._inspect())
        self.inspector.open_requested.connect(self.tree.activate_current)
        self.inspector.modes_requested.connect(lambda unit_id: self.show_unit(unit_id))
        self.inspector.jump_requested.connect(lambda rel, line: self.open_file(rel, line))
        self.tree.unit_requested.connect(lambda unit_id: self.show_unit(unit_id))
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
        add("&Save", QKeySequence.StandardKey.Save, self.save_current)
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
        self._build_edit_menu()
        self._build_run_menu()
        self._build_view_menu()
        help_menu = self.menuBar().addMenu("&Help")
        guide = QAction("&User guide", self)
        guide.setShortcut(QKeySequence.StandardKey.HelpContents)
        guide.triggered.connect(lambda: self.open_guide())
        help_menu.addAction(guide)

    def _build_edit_menu(self) -> None:
        """Undo and redo of the grids; a text field or the text editor keeps its own undo while
        it has the keyboard (Qt gives it the keys first)."""
        edit_menu = self.menuBar().addMenu("&Edit")
        stack = self.document.undo_stack
        self.undo_action = stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

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
        view_menu = self.view_menu = self.menuBar().addMenu("&View")
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
        for dock in (
            self.project_dock,
            self.inspector_dock,
            self.problems_dock,
            self.provenance_dock,
        ):
            view_menu.addAction(dock.toggleViewAction())
        reset = QAction("Re&set layout", self)
        reset.triggered.connect(self.reset_layout)
        view_menu.addAction(reset)
        view_menu.addSeparator()
        for text, key, step in (
            ("&Next problem", "F8", 1),
            ("&Previous problem", "Shift+F8", -1),
        ):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(lambda _checked=False, s=step: self.next_problem(s))
            view_menu.addAction(action)
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
            self.show_unit(unit_id)

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

    # ---- docks and layout --------------------------------------------------------------------
    def _dock(self, title: str, name: str, widget: QWidget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(name)  # the name is the key of the saved layout
        dock.setWidget(widget)
        return dock

    def _inspect(self) -> None:
        """The Inspector follows the selected node of the tree."""
        self.inspector.show_node(self.tree.current_node(), self.tree.problems_of_current())

    def _restore_layout(self) -> None:
        settings = self.layout_settings
        geometry = settings.bytes_value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = settings.bytes_value("dock/state")
        if state is not None:
            self.restoreState(state)
        self.problems_panel.set_column_widths(settings.int_list("columns/problems"))

    def save_layout(self) -> None:
        """Keep the window geometry, the dock arrangement and the widths of the Problems columns."""
        settings = self.layout_settings
        settings.set_bytes("window/geometry", self.saveGeometry())
        settings.set_bytes("dock/state", self.saveState())
        settings.set_int_list("columns/problems", self.problems_panel.column_widths())
        settings.sync()

    def reset_layout(self) -> None:
        """View > Reset layout: the arrangement the window starts with, and forget the saved one."""
        for group in ("window", "dock", "columns"):
            self.layout_settings.clear_group(group)
        self.layout_settings.sync()
        for dock in (
            self.project_dock,
            self.inspector_dock,
            self.problems_dock,
            self.provenance_dock,
        ):
            dock.setFloating(False)
            dock.show()
        self.restoreState(self._default_state)
        self._apply_default_sizes()
        self.problems_panel.set_column_widths([])
        self.resize(1400, 860)

    def _apply_default_sizes(self) -> None:
        self.resizeDocks(
            [self.project_dock, self.problems_dock], [280, 420], Qt.Orientation.Horizontal
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if not self._sized:
            self._sized = True
            if self.layout_settings.bytes_value("dock/state") is None:
                QTimer.singleShot(0, self._apply_default_sizes)  # after the first layout

    def next_problem(self, step: int = 1) -> None:
        """Select the next (or previous) problem and open its file at the line."""
        problem = self.problems_panel.select_next(step)
        self.problems_dock.show()
        self.problems_dock.raise_()
        if problem is not None and problem.file:
            self.open_file(problem.file, problem.line or 1)

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

    def _update_banners(self) -> None:
        """Say it when the tables are old (an error since) and say why a view is empty."""
        session = self.session
        errors = self.problems_panel.counts()[ProblemClass.ERROR]
        plural = "s" if errors != 1 else ""
        if session.showing_last_good:
            self.stale_banner.show_message(
                f"The project has {errors} error{plural}. The tables show the last results that "
                "worked, from before the error: they may not match the files.",
                "Show the first error",
            )
        else:
            self.stale_banner.clear()
        reason: str | None = None
        if session.path is not None and session.project is None and not session.showing_last_good:
            reason = (
                f"The project has {errors} error{plural}, so there is nothing to show yet. "
                "Fix them (the Problems panel lists them) and the budgets appear."
            )
        for view in (
            self.power_view,
            self.mass_view,
            self.thermal_view,
            self.link_view,
            self.scenario_view,
            self.timeline_view,
            self.link_passes_view,
        ):
            view.set_empty_text(reason)

    def show_first_error(self) -> None:
        """Select the first error in the Problems panel and open its file at the line."""
        panel = self.problems_panel
        for position, problem in enumerate(panel.visible_problems):
            if pc.classify(problem) is ProblemClass.ERROR:
                panel.select_row(position)
                self.problems_dock.show()
                self.problems_dock.raise_()
                if problem.file:
                    self.open_file(problem.file, problem.line or 1)
                return

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
        if state is RunState.FAILED:
            self.failed_banner.show_message(
                f"The last run did not finish: {controller.failure}", "Run again"
            )
        else:
            self.failed_banner.clear()
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

    def show_unit(self, unit_id: str) -> PowerModesPage | None:
        """Show a unit's power modes in the grid of the Model tab, its first row current."""
        project = self.session.project
        if project is None or self.session.path is None or unit_id not in project.units:
            self.status_bar.showMessage(
                "Fix the errors in the Problems panel first; the grids need a project that loads."
            )
            return None
        self.show_view(self.modes_page)
        self.modes_page.select_unit(unit_id)
        self.modes_page.table.view.setFocus()
        return self.modes_page

    def show_view(self, widget: QWidget) -> bool:
        """Bring any view to the front: its tab, and its page inside the tab."""
        if self.editors.indexOf(widget) >= 0:
            self.editors.setCurrentWidget(widget)
            return self.workspace.show_view(self.editors)
        return self.workspace.show_view(widget)

    def save_current(self) -> bool:
        if self.workspace.currentWidget() is not self.editors:
            return False  # Save belongs to the editors of the Model tab
        if self.editors.currentWidget() in (
            self.units_page,
            self.modes_page,
            self.inputs_page,
            self.scenario_view,
        ):
            return self.save_model()
        editor = self.editors.current_editor()
        if editor is None:
            return False
        if not self._write(editor):
            return False
        self.reload_project()
        return True

    def save_model(self) -> bool:
        """Write the files the grids and the scenario editor changed (nothing while a cell is
        wrong or a file moved on disk)."""
        report = self.document.save()
        page = self.editors.currentWidget()
        grid = page if page in (self.units_page, self.modes_page, self.inputs_page) else None
        if report.ok:
            n = len(report.written)
            text = (
                f"Saved {n} file{'s' if n != 1 else ''}." if n else "Nothing to save: no changes."
            )
            self.status_bar.showMessage(text)
            if grid is not None:
                grid.show_message(text)
        else:
            self.status_bar.showMessage(report.message)
            for candidate in (self.units_page, self.modes_page, self.inputs_page):
                candidate.show_message(report.message)
            self.scenario_view.editor.note_label.setText(report.message)
        return report.ok

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
        self.tree.set_project(session.path, session.display_project)
        self.power_view.set_document(session.document)
        self.mass_view.set_document(session.mass_document)
        self.thermal_view.set_document(session.thermal_document)
        self.link_view.set_document(session.link_document)
        self.document.reload(session.path, project)
        self.scenario_view.set_project(project)
        load_problems = session.load_result.problems if session.load_result else []
        self.timeline_view.set_project(project, load_problems)
        self.link_passes_view.set_project(project, load_problems)
        self.compare_view.set_project(project)
        self._update_problems()
        self.editors.reload_clean_files()
        shown = session.display_project  # the name and revision stay while the project has an error
        name = shown.meta.name if shown else (session.path.name if session.path else "")
        self.top_bar.set_project(name, shown.meta.revision if shown else "")
        self.setWindowTitle(f"{name} — {APP_NAME}" if name else APP_NAME)
        ids = sorted(project.scenarios) if project else []
        self.top_bar.set_scenarios(ids, self.scenario_view.selected_id())
        self.select_scenario(self.scenario_view.selected_id())
        self.run_controller.reset_failure()
        self._last_run = datetime.now() if project else None
        self.status_bar.set_project_path(session.path)
        self.status_bar.set_last_run(self._last_run)
        self.provenance_panel.set_provenance(session.provenance)
        self._update_banners()
        self._inspect()
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
        self._inspect()
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
        self.save_layout()
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
