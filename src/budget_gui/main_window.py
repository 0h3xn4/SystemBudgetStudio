"""Main window: project tree, budget view and file editors, Problems panel, export."""

from __future__ import annotations

import time
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from functools import partial
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from budget_core import APP_NAME
from budget_core.model import Orbit, Scenario
from budget_core.new_scenario import ScenarioAnswers, scenario_data
from budget_core.problems import sort_problems
from budget_core.reports.files import OutputError
from budget_core.reports.run import REPORT_KINDS
from budget_gui import problem_class as pc
from budget_gui import theme
from budget_gui.add_scenario_dialog import AddScenarioDialog
from budget_gui.banner import Banner
from budget_gui.command_palette import Command, CommandPalette
from budget_gui.compare_view import CompareView
from budget_gui.components import PanelTitle, Toast
from budget_gui.editor import EditorTabs, FileChangedError, YamlEditor
from budget_gui.grid_view import GridPage
from budget_gui.guided import GuidedWizard
from budget_gui.help_view import GuideDialog
from budget_gui.inspector import CellInfo, InspectorPanel
from budget_gui.layout_settings import (
    MOTION,
    OPEN_STATES,
    RAIL_STATES,
    START_STATES,
    VIEW_STATES,
    LayoutSettings,
)
from budget_gui.legend import LegendDialog
from budget_gui.link_view import LinkPassesView
from budget_gui.model_document import ModelDocument
from budget_gui.model_pages import InputsPage, PowerModesPage, SpacecraftModesPage, UnitsPage
from budget_gui.privacy import disable_settings_files
from budget_gui.problem_class import ProblemClass
from budget_gui.problems_panel import ProblemsPanel
from budget_gui.project_tree import ProjectTree
from budget_gui.provenance_panel import ProvenancePanel
from budget_gui.rail import NavRail
from budget_gui.reports_view import ReportItem, ReportsView
from budget_gui.run_controller import RunController, RunState
from budget_gui.scenario_view import ScenarioView
from budget_gui.session import ProjectSession
from budget_gui.settings_popover import SettingsPopover
from budget_gui.start_here import MODE, RUN, SCENARIO, UNIT, Progress, StartHerePanel, progress
from budget_gui.status_bar import AppStatusBar
from budget_gui.theme import Status
from budget_gui.timeline_view import PowerTimelineView
from budget_gui.top_bar import TopBar
from budget_gui.unit_table import export_unit_table, import_unit_table
from budget_gui.welcome import WelcomePage
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


DEFAULT_VIEW = "focused"  # what a window with no saved layout starts in (D-191)
LAYOUT_VERSION = 2  # the arrangement of the docks: a saved layout of another version is ignored


class MainWindow(QMainWindow):
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self, layout: LayoutSettings | None = None) -> None:
        super().__init__()
        disable_settings_files()  # also when the window is made without create_app
        self.setWindowTitle(APP_NAME)
        self.resize(*theme.scaled(theme.WINDOW_DEFAULT))
        self.session = ProjectSession()
        self._start_hidden = False  # the person hid the Start here panel (kept in layout.ini)
        self._start_forced = False  # Help > Start here: shown even when every step is done
        self._run_after_load = False  # Save and run: the run waits for the project to load again
        self._opened_path: Path | None = None  # the project the area was chosen for
        self._show_first_run = False  # the run of the Start here card: its result is shown
        self._first_run_going = False  # ... and that run has started
        self.toast = Toast(self)
        self._focused = True  # the focused view (D-191); the full view shows every panel and column
        self._problems_height = 0  # the height of the Problems panel while its list was open
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
        self.spacecraft_modes_page = SpacecraftModesPage(self.document)
        self.inputs_page = InputsPage(self.document)
        for title, page in (
            ("Units", self.units_page),
            ("Power modes", self.modes_page),
            ("Spacecraft modes", self.spacecraft_modes_page),
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
        self.power_pages = SubTabs([("Budget", self.power_view), ("Timeline", self.timeline_view)])
        self.link_pages = SubTabs([("Budget", self.link_view), ("Passes", self.link_passes_view)])
        self.workspace.add_page("Power", self.power_pages)
        self.workspace.add_page("Mass", self.mass_view)
        self.workspace.add_page("Thermal", self.thermal_view)
        self.workspace.add_page("Link", self.link_pages)
        self.workspace.add_page("Compare", self.compare_view)
        self.workspace.add_page("Reports", self.reports_view)
        self.top_bar = TopBar()
        self.rail = NavRail()
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
        self.start_here = StartHerePanel()
        self.start_here.hide()
        stack.addWidget(self.start_here)
        stack.addWidget(self.workspace, 1)
        self.welcome = WelcomePage()
        self.welcome.open_requested.connect(self._choose_project)
        self.welcome.new_requested.connect(self.open_guided_wizard)
        stack.addWidget(self.welcome, 1)
        self.setCentralWidget(central)
        self.setAcceptDrops(True)  # a project folder dropped on the window opens
        self.workspace.setCurrentIndex(1)  # Power: a project opens on its budgets
        self._worker: ExportWorker | None = None

        self.project_dock = self._dock("Project", "dock-project", self.tree)
        self.inspector_dock = self._dock("Inspector", "dock-inspector", self.inspector)
        self.problems_dock = self._dock("Problems", "dock-problems", self.problems_panel)
        self.provenance_dock = self._dock("Provenance", "dock-provenance", self.provenance_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        for dock in (self.inspector_dock, self.provenance_dock):
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self.inspector_dock, self.provenance_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_dock)
        # the Problems panel runs under the project panel and the inspector, the full width
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.inspector_dock.raise_()
        self.rail_bar = QToolBar("Navigation", self)
        self.rail_bar.setObjectName("rail")
        self.rail_bar.setMovable(False)
        self.rail_bar.setFloatable(False)
        self.rail_bar.addWidget(self.rail)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.rail_bar)
        self.project_dock.toggleViewAction().setShortcut(QKeySequence("Ctrl+B"))
        self._welcome_hid: dict[QDockWidget, bool] | None = None  # docks hidden by the first screen
        self._narrow_hid: set[QDockWidget] = set()  # docks hidden because the window is narrow
        self._regime = "wide"
        self._folded_by_user = False
        self._auto_fold = False
        self._sized = False  # the dock widths are set when the window is first shown
        self.status_bar = AppStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "Offline. File > Open project, or File > New project (guided), starts a budget."
        )
        self.status_bar.not_checked_requested.connect(self.show_not_checked)
        self.rail.destination_chosen.connect(self._go_to_tab)
        self.rail.find_requested.connect(self.open_command_palette)
        self.rail.help_requested.connect(self.open_guide)
        self.rail.settings_requested.connect(self.show_settings)
        self.rail.project_toggled.connect(self.project_dock.setVisible)
        self.rail.folded_changed.connect(self._rail_folded)
        self.project_dock.visibilityChanged.connect(self._project_dock_shown)
        self.workspace.currentChanged.connect(self._area_changed)
        self.rail.set_current(self.workspace.currentIndex())  # the area the window starts on
        self._default_state = self.saveState(LAYOUT_VERSION)  # what Reset layout goes back to
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
        self.top_bar.cancel_requested.connect(self.run_controller.cancel)
        self.problems_panel.expanded_changed.connect(self._problems_expanded)
        self.start_here.step_requested.connect(self._start_step)
        self.start_here.hide_requested.connect(self.hide_start_here)
        self.document.undo_stack.indexChanged.connect(lambda _i: self._update_start_here())
        self.stale_banner.action_requested.connect(self.show_first_error)
        self.failed_banner.action_requested.connect(self.run_all)
        self.run_controller.changed.connect(self._update_run_state)
        self.editors.dirty_changed.connect(self._update_dirty)
        self.reports_view.export_requested.connect(self._export_selected)
        self.workspace.currentChanged.connect(lambda _i: self.update_reports_page())
        for source in (self.scenario_view, self.timeline_view):
            source.computed.connect(lambda _result: self.update_reports_page())
            source.compute_failed.connect(lambda _message: self.update_reports_page())
        self.scenario_view.add_scenario_requested.connect(self.add_scenario)
        self.tree.file_requested.connect(self._tree_file)
        self.tree.field_requested.connect(self.jump_to_input)
        self.tree.currentItemChanged.connect(lambda _current, _previous: self._inspect())
        for grid_page in self.grid_pages():
            grid_page.table.selection_changed.connect(self._inspect_cell)
        self.inspector.open_file_requested.connect(lambda rel: self.open_file(rel))
        self.inspector.open_requested.connect(self.tree.activate_current)
        self.inspector.modes_requested.connect(lambda unit_id: self.show_unit(unit_id))
        self.inspector.jump_requested.connect(lambda rel, line: self.open_file(rel, line))
        self.tree.unit_requested.connect(lambda unit_id: self.show_unit(unit_id))
        self.problems_panel.jump_requested.connect(lambda rel, line: self.open_file(rel, line))
        self._export_folder = Path()
        self._queue: list[str] = []  # what the Reports page asked for and is still to be written
        self._queue_paths: list[str] = []
        self._queue_formats: set[str] = set()
        self._queue_folder = Path()
        self._queue_active = False
        self.timeline_view.computed.connect(lambda _result: self._update_problems())
        self.link_passes_view.computed.connect(lambda _result: self._update_problems())
        for computing in (self.scenario_view, self.timeline_view, self.link_passes_view):
            computing.computed.connect(lambda _result: self._mark_run())
        self.timeline_view.jump_requested.connect(self.jump_to_input)
        for view in (self.timeline_view, self.link_passes_view, self.compare_view):
            view.export_finished.connect(self._view_export_done)
            view.export_failed.connect(self._view_export_failed)
        # after the slots above, so the message of a queued export is the last one shown
        self.export_finished.connect(self._queue_step_done)
        self.export_failed.connect(self._queue_step_failed)
        self.timeline_view.export_finished.connect(self._queue_step_done)
        self.timeline_view.export_failed.connect(self._queue_step_failed)
        self._closing = False  # a close was asked for while a job runs
        self._last_run: datetime | None = None
        self.set_view_mode(self._focused)  # before the first screen notes which docks to give back
        self._show_welcome()

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
        self.start_here_action = QAction("&Start here", self)
        self.start_here_action.setEnabled(False)  # until a project is open
        self.start_here_action.triggered.connect(self.show_start_here)
        help_menu.addAction(self.start_here_action)
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
        edit_menu.addSeparator()
        # Add unit and Remove unit work from any area: they bring the Units grid to the front
        self.add_unit_action = QAction("&Add unit…", self)
        self.add_unit_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self.add_unit_action.triggered.connect(self.add_unit)
        self.remove_unit_action = QAction("Re&move unit", self)
        self.remove_unit_action.setShortcut(QKeySequence("Ctrl+Shift+Delete"))
        self.remove_unit_action.triggered.connect(self.remove_unit)
        edit_menu.addAction(self.add_unit_action)
        edit_menu.addAction(self.remove_unit_action)
        edit_menu.addSeparator()
        self.add_mode_action = QAction("Add spacecraft mo&de…", self)
        self.add_mode_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.add_mode_action.triggered.connect(self.add_spacecraft_mode)
        self.remove_mode_action = QAction("Remove spacecraft m&ode", self)
        self.remove_mode_action.setShortcut(QKeySequence("Ctrl+Shift+Backspace"))
        self.remove_mode_action.triggered.connect(self.remove_spacecraft_mode)
        edit_menu.addAction(self.add_mode_action)
        edit_menu.addAction(self.remove_mode_action)
        edit_menu.addSeparator()
        self.add_scenario_action = QAction("Add &scenario…", self)
        self.add_scenario_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.add_scenario_action.triggered.connect(self.add_scenario)
        edit_menu.addAction(self.add_scenario_action)
        for action in self.model_edit_actions():
            action.setEnabled(False)  # until a project is open that loads

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
        palette = QAction("&Find a command…", self)
        palette.setShortcut(QKeySequence("Ctrl+K"))
        palette.triggered.connect(self.open_command_palette)
        view_menu.addAction(palette)
        view_menu.addSeparator()
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
        scale_menu = view_menu.addMenu("UI si&ze")
        scale_group = QActionGroup(self)
        scale_group.setExclusive(True)
        self.scale_actions: dict[int, QAction] = {}
        for percent in theme.SCALES:
            action = QAction(f"{percent} %", self)
            action.setCheckable(True)
            action.setChecked(theme.scale_percent() == percent)
            action.triggered.connect(lambda _checked=False, p=percent: self.set_scale(p))
            scale_group.addAction(action)
            scale_menu.addAction(action)
            self.scale_actions[percent] = action
        self.motion_action = QAction("Reduce &motion", self)
        self.motion_action.setCheckable(True)
        self.motion_action.setChecked(theme.manager().reduce_motion_setting)
        self.motion_action.triggered.connect(self.set_reduce_motion)
        view_menu.addAction(self.motion_action)
        self.single_click_action = QAction("Open with a &single click", self)
        self.single_click_action.setCheckable(True)
        self.single_click_action.setChecked(self.single_click)
        self.single_click_action.setToolTip(
            "A click on a node of the project tree opens it and a click on a selected cell of a "
            "grid edits it. Off: a double-click, Enter or F2."
        )
        self.single_click_action.triggered.connect(self.set_single_click)
        view_menu.addAction(self.single_click_action)
        self._apply_single_click()
        view_menu.addSeparator()
        self.view_action = QAction("Focused &view", self)
        self.view_action.setCheckable(True)
        self.view_action.setChecked(self._focused)
        self.view_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.view_action.setToolTip(
            "Focused: the problems as one line of counts, no Inspector or Provenance panel, only "
            "the main columns. Off: every panel and column."
        )
        self.view_action.toggled.connect(self.set_view_mode)
        view_menu.addAction(self.view_action)
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

    def _area_changed(self, index: int) -> None:
        """The rail and the title follow the area on show, whoever changed it."""
        self.rail.set_current(index)

    def _project_dock_shown(self, shown: bool) -> None:
        if self._welcome_hid is None:  # the first screen hides it without the user asking
            self.rail.set_project_checked(shown)

    def set_theme(self, mode: theme.Mode) -> None:
        """Switch the theme now and keep the choice for the next start."""
        theme.manager().set_mode(mode)
        self.theme_actions[mode].setChecked(True)
        self.layout_settings.set_word("theme/mode", mode.value, tuple(m.value for m in theme.Mode))
        self.layout_settings.sync()

    def show_settings(self) -> SettingsPopover:
        """The settings card beside the rail: theme, UI size and motion."""
        popover = SettingsPopover(self)
        popover.show_current(
            theme.manager().mode,
            theme.scale_percent(),
            theme.manager().reduce_motion_setting,
            self.single_click,
        )
        popover.theme_chosen.connect(lambda value: self.set_theme(theme.Mode(value)))
        popover.scale_chosen.connect(self.set_scale)
        popover.motion_reduced.connect(self.set_reduce_motion)
        popover.single_click_chosen.connect(self.set_single_click)
        popover.open_beside(self.rail.settings_button)
        return popover

    def set_scale(self, percent: int) -> None:
        """Make the window larger or smaller now (90 to 125 %) and keep the choice."""
        theme.manager().set_scale(percent)
        self.scale_actions[theme.scale_percent()].setChecked(True)
        self.layout_settings.set_word(
            "theme/scale", str(theme.scale_percent()), tuple(str(s) for s in theme.SCALES)
        )
        self.layout_settings.sync()

    def set_single_click(self, on: bool) -> None:
        """Open nodes of the project tree and edit selected cells with one click (or not), and
        keep the choice."""
        self.single_click = bool(on)
        self.single_click_action.setChecked(self.single_click)
        self._apply_single_click()
        self.layout_settings.set_word(
            "window/open_with", "single" if self.single_click else "double", OPEN_STATES
        )
        self.layout_settings.sync()

    def _apply_single_click(self) -> None:
        self.tree.set_single_click(self.single_click)
        for page in self.grid_pages():
            page.table.set_single_click(self.single_click)

    def set_reduce_motion(self, reduced: bool) -> None:
        """Turn animations off (or on again) and keep the choice."""
        theme.manager().set_reduce_motion(reduced)
        self.motion_action.setChecked(reduced)
        self.layout_settings.set_word("theme/motion", "reduced" if reduced else "full", MOTION)
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
        project = self.session.project
        if project is not None and not project.scenarios:
            # a blank project: nothing to simulate yet; start where the spacecraft is described
            self.show_view(self.units_page)
            self.statusBar().showMessage(
                "The blank project is open. The Problems panel lists what is still to fill in."
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

    def model_edit_actions(self) -> tuple[QAction, ...]:
        return (
            self.add_unit_action,
            self.remove_unit_action,
            self.add_mode_action,
            self.remove_mode_action,
            self.add_scenario_action,
        )

    def _ask_scenario(
        self, scenarios: list[str], orbits: list[str], modes: list[str]
    ) -> ScenarioAnswers | None:
        """The form; the tests put their own answers here."""
        dialog = AddScenarioDialog(scenarios, orbits, modes, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.answers()

    def add_scenario(self) -> bool:
        """Edit > Add scenario: an orbit and a scenario from a form, from any area. The orbit file
        and the scenario file are added in one undo step; Save writes them."""
        project = self.session.project
        if project is None:
            return False
        document = self.document

        def ids(prefix: str) -> list[str]:
            return [r.removeprefix(prefix).removesuffix(".yaml") for r in document.rels(prefix)]

        modes = ids("modes/")
        self.show_view(self.scenario_view)
        if not modes:
            self.statusBar().showMessage(
                "A scenario says which spacecraft mode is active: add a spacecraft mode first "
                "(Edit > Add spacecraft mode)."
            )
            return False
        answers = self._ask_scenario(ids("scenarios/"), sorted(project.orbits), modes)
        if answers is None:
            return False
        try:
            orbit_data, scenario_data_ = scenario_data(answers)
        except ValueError:
            self.statusBar().showMessage("The answers do not make a valid scenario.")
            return False
        name = answers.scenario_id
        orbit_rel, scenario_rel = f"orbits/{name}.yaml", f"scenarios/{name}.yaml"
        document.undo_stack.beginMacro(f"Add orbit and scenario {name}")
        try:
            added = document.add_file(
                orbit_rel, Orbit, orbit_data, f"Add orbit {name}"
            ) and document.add_file(scenario_rel, Scenario, scenario_data_, f"Add scenario {name}")
        finally:
            document.undo_stack.endMacro()
        if not added:
            self.statusBar().showMessage(
                f"There is already a file for {name} (removed in this session? Undo it, or Save "
                "first)."
            )
            return False
        self.statusBar().showMessage(
            f"Added the scenario {name} and its orbit. Save (Ctrl+S) writes {scenario_rel} and "
            f"{orbit_rel}; then press Run. Undo with Ctrl+Z."
        )
        return True

    def add_spacecraft_mode(self) -> bool:
        """Edit > Add spacecraft mode: the form of the Spacecraft modes grid, from any area."""
        if self.session.project is None:
            return False
        self.show_view(self.spacecraft_modes_page)
        return self.spacecraft_modes_page.add_mode()

    def remove_spacecraft_mode(self) -> bool:
        """Edit > Remove spacecraft mode: the mode of the row with the cursor."""
        if self.session.project is None:
            return False
        self.show_view(self.spacecraft_modes_page)
        return self.spacecraft_modes_page.remove_mode()

    def add_unit(self) -> bool:
        """Edit > Add unit: the form of the Units grid, from whichever area is in front."""
        if self.session.project is None:
            return False
        self.show_view(self.units_page)
        return self.units_page.add_unit()

    def remove_unit(self) -> bool:
        """Edit > Remove unit: the unit with the cursor in the Units grid, or else the unit selected
        in the project tree."""
        if self.session.project is None:
            return False
        tree_unit = self.tree.current_unit_id()
        in_front = self.workspace.currentWidget() is self.editors and (
            self.editors.currentWidget() is self.units_page
        )
        self.show_view(self.units_page)
        if tree_unit and not (in_front and self.units_page.table.current_cell() is not None):
            self.units_page.select_unit(tree_unit)
        return self.units_page.remove_unit()

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
        panel_title = PanelTitle(title)
        panel_title.close_button.clicked.connect(dock.close)
        dock.setTitleBarWidget(panel_title)
        return dock

    def grid_pages(self) -> tuple[GridPage, ...]:
        """The grids of the Model tab, in the order of their tabs."""
        return (self.units_page, self.modes_page, self.spacecraft_modes_page, self.inputs_page)

    def _inspect_cell(self) -> None:
        """The Inspector follows the cell that has the cursor in a grid of the Model tab."""
        page = self.editors.currentWidget()
        if page not in self.grid_pages():
            return
        grid = page.table
        current = grid.current_cell()
        if current is None:
            return
        row, column = current
        model = grid.model
        found = model.cell(row, column)
        if found is None:
            return
        state = model.state_of(row, column)
        self.inspector.show_cell(
            CellInfo(
                title=model.label_of(model.row_keys()[row]),
                column=model.columns[column].title,
                rel=found[0],
                path=".".join(str(part) for part in found[1]),
                value=model.display(row, column),
                state=theme.STATUS_LABELS[state] if state is not None else "",
                message=model.message_at(found, hint=True) or "",
                help=model.column_tip(model.columns[column]),
            )
        )

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
            self.restoreState(state, LAYOUT_VERSION)  # a layout of another version is ignored
        self.rail.set_folded(settings.word("window/rail", RAIL_STATES, "open") == "folded")
        self._start_hidden = settings.word("window/start_here", START_STATES, "shown") == "hidden"
        self._focused = settings.word("window/view", VIEW_STATES, DEFAULT_VIEW) == "focused"
        self.single_click = settings.word("window/open_with", OPEN_STATES, "double") == "single"
        self.problems_panel.set_column_widths(settings.int_list("columns/problems"))

    def save_layout(self) -> None:
        """Keep the window geometry, the dock arrangement and the widths of the Problems columns."""
        settings = self.layout_settings
        settings.set_bytes("window/geometry", self.saveGeometry())
        with self._docks_as_the_user_left_them():
            settings.set_bytes("dock/state", self.saveState(LAYOUT_VERSION))
        settings.set_word("window/rail", "folded" if self.rail.folded else "open", RAIL_STATES)
        settings.set_word(
            "window/start_here", "hidden" if self._start_hidden else "shown", START_STATES
        )
        settings.set_word("window/view", "focused" if self._focused else "full", VIEW_STATES)
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
        self.restoreState(self._default_state, LAYOUT_VERSION)
        self.rail.set_folded(False)
        self.problems_panel.set_column_widths([])
        self.resize(*theme.scaled(theme.WINDOW_DEFAULT))
        self.view_action.setChecked(True)  # the first arrangement is the focused view
        self.set_view_mode(True)
        self._apply_default_sizes()

    def _apply_default_sizes(self) -> None:
        self.resizeDocks(
            [self.project_dock, self.inspector_dock],
            [theme.px(w) for w in theme.DOCK_WIDTHS],
            Qt.Orientation.Horizontal,
        )
        self._size_problems_dock()

    # ---- the focused view (D-191) ------------------------------------------------------------
    def set_view_mode(self, focused: bool) -> None:
        """The focused view shows the counts of the problems as one line, no Inspector and no
        Provenance panel, and only the main columns of the grids. The full view shows everything.
        Panels and columns can still be opened one by one (View menu, the buttons)."""
        self._focused = focused
        if self.view_action.isChecked() != focused:
            self.view_action.setChecked(focused)
            return  # the toggle calls this again
        for page in self.grid_pages():
            page.set_optional_columns(not focused)
        side = (self.inspector_dock, self.provenance_dock)
        if self._welcome_hid is not None:
            for dock in side:
                self._welcome_hid[dock] = not focused  # what the first screen gives back
        else:
            for dock in side:
                self._narrow_hid.discard(dock)
                dock.setVisible(not focused and self._regime == "wide")
        self.problems_panel.set_expanded(not focused)
        self.problems_dock.show()

    def reveal_problems(self) -> None:
        """Bring the Problems panel to the front with its list open (a jump to a problem, the
        'not checked' link of the status bar, F8)."""
        self.problems_dock.show()
        self.problems_dock.raise_()
        self.problems_panel.set_expanded(True)

    def _problems_expanded(self, expanded: bool) -> None:
        height = self.problems_dock.height()
        if not expanded and self.isVisible() and height >= theme.px(theme.PROBLEMS_HEIGHT) // 2:
            self._problems_height = height  # what the list had, to give back when it is opened
        self._size_problems_dock()

    def _size_problems_dock(self) -> None:
        """The height of the Problems dock: one line of counts, or what it had with the list. The
        layout has not seen the widgets show or hide yet, so it is done again once it has."""
        self._set_problems_height()
        QTimer.singleShot(0, self, self._set_problems_height)

    def _set_problems_height(self) -> None:
        if self.problems_panel.is_expanded():
            height = self._problems_height or theme.px(theme.PROBLEMS_HEIGHT)
        else:
            title = self.problems_dock.titleBarWidget()
            height = self.problems_panel.sizeHint().height() + (
                title.sizeHint().height() if title is not None else 0
            )
        self.resizeDocks([self.problems_dock], [height], Qt.Orientation.Vertical)

    @contextmanager
    def _docks_as_the_user_left_them(self) -> Iterator[None]:
        """The docks hidden by the first screen or by a narrow window are shown for a moment, so a
        saved layout holds what the user chose, not what the size of the window did."""
        hidden = {
            dock for dock in (*self._narrow_hid, *(self._welcome_hid or {})) if dock.isHidden()
        }
        for dock in hidden:
            dock.show()
        try:
            yield
        finally:
            for dock in hidden:
                dock.hide()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._fit_to_width()
        if event.size().width() > event.oldSize().width() > 0:  # it grew: room for the panels
            QTimer.singleShot(0, self, self._restore_squeezed_docks)
            QTimer.singleShot(60, self, self._restore_squeezed_docks)  # after the docks settle

    def _fit_to_width(self) -> None:
        """Make room on a narrow window: below 1520 px the inspector waits, below 1280 px the rail
        shows icons only, below 1100 px the project panel waits, too. The docks come back when
        there is room again; a dock the user hid stays hidden."""
        if self._welcome_hid is not None:
            return
        width = self.width()
        if width < theme.px(theme.RESPONSIVE_PROJECT):
            regime = "tiny"
        elif width < theme.px(theme.RESPONSIVE_LABELS):
            regime = "narrow"
        elif width < theme.px(theme.RESPONSIVE_INSPECTOR):
            regime = "medium"
        else:
            regime = "wide"
        if regime == self._regime:
            return
        order = ("tiny", "narrow", "medium", "wide")
        grew = self._regime in order and order.index(regime) > order.index(self._regime)
        self._regime = regime
        waiting: tuple[QDockWidget, ...] = ()
        if regime != "wide":
            waiting = (self.inspector_dock, self.provenance_dock)
        if regime == "tiny":
            waiting = (*waiting, self.project_dock)
        for dock in list(self._narrow_hid):
            if dock not in waiting:
                self._narrow_hid.discard(dock)
                dock.show()
        for dock in waiting:
            if not dock.isHidden():
                self._narrow_hid.add(dock)
                dock.hide()
        self._auto_fold = True
        try:
            self.rail.set_folded(regime in ("narrow", "tiny") or self._folded_by_user)
        finally:
            self._auto_fold = False
        if grew:
            self._restore_squeezed_docks()  # now, and again once the shown docks are laid out
            QTimer.singleShot(0, self, self._restore_squeezed_docks)
            QTimer.singleShot(60, self, self._restore_squeezed_docks)

    def _restore_squeezed_docks(self) -> None:
        """A narrow window squeezes the side panels to a sliver (Qt gives the centre what it needs)
        and they stay so when the window grows again: give a panel that is far below its usual
        width that width back. A width the user chose is not touched unless it is that narrow."""
        squeezed = [
            (dock, theme.px(width))
            for dock, width in zip(
                (self.project_dock, self.inspector_dock), theme.DOCK_WIDTHS, strict=True
            )
            if not dock.isHidden() and dock.width() < theme.px(width) * 3 // 4
        ]
        if squeezed:
            self.resizeDocks(
                [dock for dock, _w in squeezed],
                [w for _d, w in squeezed],
                Qt.Orientation.Horizontal,
            )

    def _rail_folded(self, folded: bool) -> None:
        if not self._auto_fold:
            self._folded_by_user = folded

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if not self._sized:
            self._sized = True
            if self.layout_settings.bytes_value("dock/state") is None:
                QTimer.singleShot(0, self._apply_default_sizes)  # after the first layout

    def next_problem(self, step: int = 1) -> None:
        """Select the next (or previous) problem and open its file at the line."""
        problem = self.problems_panel.select_next(step)
        self.reveal_problems()
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
                self.reveal_problems()
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
        elif state is RunState.RUNNING:
            detail = "cancelling" if controller.cancelling else controller.stage
        self.top_bar.set_run_state(
            state, controller.can_run(), detail, tips[state], cancelling=controller.cancelling
        )
        if state is RunState.FAILED:
            self.failed_banner.show_message(
                f"The last run did not finish: {controller.failure}", "Run again"
            )
        else:
            self.failed_banner.clear()
        self.run_action.setEnabled(controller.can_run())
        self._update_start_here()
        if self._show_first_run and state is RunState.RUNNING:
            self._first_run_going = True  # the save and the reload before it show Not run
        elif self._show_first_run and self._first_run_going:
            self._show_first_run = self._first_run_going = False
            if state is RunState.OK:
                self._go_to_first_result()

    def _go_to_first_result(self) -> None:
        """The run of the Start here card is the goal of its four steps: show its result, the
        power timeline with the eclipses, and say where the other results are."""
        self.workspace.setCurrentIndex(1)
        self.power_pages.setCurrentIndex(1)
        self.toast.show_message(
            "First run done: this is the power timeline. Mass, Thermal and Link have their own "
            "areas; press Run (Ctrl+R) again after every change."
        )

    def _update_dirty(self) -> None:
        dirty = self.editors.has_unsaved_changes()
        self.top_bar.set_dirty(dirty)
        name = self.top_bar.name_label.text()
        has_project = self.session.project is not None or self.session.path is not None
        if has_project and name:
            self.setWindowTitle(f"{'● ' if dirty else ''}{name} — {APP_NAME}")
        self._update_start_here()

    # ---- the Start here panel ----------------------------------------------------------------
    def start_progress(self) -> Progress:
        """Which of the four steps are done, from the files on screen (edits included)."""
        document = self.document
        return progress(
            units=len(document.rels("units/")),
            modes=len(document.rels("modes/")),
            scenarios=len(document.rels("scenarios/")),
            saved=not self.editors.has_unsaved_changes(),
            ran=self.run_controller.state() is RunState.OK,
        )

    def _update_start_here(self) -> None:
        state = self.start_progress()
        self.start_here.set_progress(state)
        shown = self.session.project is not None and (
            self._start_forced or (not self._start_hidden and not state.finished)
        )
        self.start_here.setVisible(shown)
        self.start_here_action.setEnabled(self.session.project is not None)

    def show_start_here(self) -> None:
        """Help > Start here: show the panel again (also when every step is done)."""
        if self.session.project is None:
            return
        self._start_hidden = False
        self._start_forced = True
        self._update_start_here()
        self.save_layout()

    def hide_start_here(self) -> None:
        self._start_hidden = True
        self._start_forced = False
        self._update_start_here()
        self.status_bar.showMessage("Start here is hidden. Help > Start here shows it again.")
        self.save_layout()

    def _start_step(self, key: str) -> None:
        """A button of the panel: the same action as the menu entry of that step."""
        if key == UNIT:
            self.add_unit()
        elif key == MODE:
            self.add_spacecraft_mode()
        elif key == SCENARIO:
            self.add_scenario()
        elif key == RUN:
            self._show_first_run = True
            self._first_run_going = False
            if not self.save_and_run():
                self._show_first_run = False

    def save_and_run(self) -> bool:
        """Save what was edited, then run. The project loads again after a save, so the run waits
        for that (`_refresh`) and works on the files that were just written."""
        if self.session.project is None:
            return False
        if self.document.is_modified():
            self._run_after_load = True
            if not self.save_model():
                self._run_after_load = False
                return False
            return True
        if self.editors.has_unsaved_changes():
            self.status_bar.showMessage("Save the open file tabs first (Ctrl+S), then run.")
            return False
        return self.run_all()

    def _mark_run(self) -> None:
        """Something was worked out just now: say so in the status bar."""
        self._last_run = datetime.now()
        self.status_bar.set_last_run(self._last_run)
        self._update_run_state()

    def show_not_checked(self) -> None:
        """List the 'not checked' findings (the link in the status bar)."""
        self.problems_panel.set_class_filter(ProblemClass.NOT_CHECKED)
        self.reveal_problems()
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
            *self.grid_pages(),
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

    def _confirm_deletion(self, files: list[str]) -> bool:
        """Saving deletes the files of the units that were removed: ask first (a deleted file is
        not in the undo history any more)."""
        answer = QMessageBox.question(
            self,
            APP_NAME,
            f"Saving deletes {len(files)} file{'s' if len(files) != 1 else ''} from the project "
            f"folder:\n\n{chr(10).join(files)}\n\nDelete {'them' if len(files) != 1 else 'it'}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def save_model(self) -> bool:
        """Write the files the grids and the scenario editor changed (nothing while a cell is
        wrong or a file moved on disk)."""
        deleted = self.document.deleted_files()
        if deleted and not self._confirm_deletion(deleted):
            return False
        report = self.document.save()
        page = self.editors.currentWidget()
        grid = page if page in self.grid_pages() else None
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
            for candidate in self.grid_pages():
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
        for action in self.model_edit_actions():
            action.setEnabled(project is not None)
        self.update_reports_page()
        self._show_welcome()
        self._update_banners()
        self._inspect()
        self._update_dirty()
        self.statusBar().showMessage(f"{name}: {self.problems_panel.summary.text()}")
        self._update_start_here()
        self._choose_first_area(project is not None and not project.units)
        if self._run_after_load:
            self._run_after_load = False
            if project is not None:
                self.run_all()

    def _choose_first_area(self, nothing_to_budget: bool) -> None:
        """A project opens on its budgets (Power); one with no unit yet opens on the Model area,
        where its first step is, instead of an empty table. Only for a project that was not open
        before: a reload after Save keeps the area the person is in."""
        path = self.session.path
        if path == self._opened_path:
            return
        self._opened_path = path
        if path is not None:
            self.workspace.setCurrentIndex(0 if nothing_to_budget else 1)

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

    # ---- the command palette -----------------------------------------------------------------
    def palette_commands(self) -> list[Command]:
        """Everything the palette offers now: the commands of the menus that are available, the
        units, files and scenarios of the open project and its errors and warnings."""
        commands: list[Command] = []

        def walk(menu: QMenu, trail: str) -> None:
            for action in menu.actions():
                submenu = action.menu()
                if isinstance(submenu, QMenu):
                    walk(submenu, f"{trail} > {action.text().replace('&', '')}")
                elif action.text() and action.isEnabled() and not action.isSeparator():
                    name = f"{trail} > {action.text().replace('&', '')}"
                    shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
                    commands.append(
                        Command(name.removesuffix("…"), action.trigger, shortcut or "menu")
                    )

        for top in self.menuBar().actions():
            menu = top.menu()
            if isinstance(menu, QMenu):
                walk(menu, top.text().replace("&", ""))
        project = self.session.project
        if project is not None:
            for unit_id, unit in sorted(project.units.items()):
                commands.append(
                    Command(
                        f"Open unit {unit.name} ({unit_id})",
                        partial(self.show_unit, unit_id),
                        "unit",
                    )
                )
            for scenario_id in sorted(project.scenarios):
                commands.append(
                    Command(
                        f"Select scenario {scenario_id}",
                        partial(self.select_scenario, scenario_id),
                        "scenario",
                    )
                )
        root = self.session.path
        if root is not None:
            for path in sorted(root.rglob("*.yaml"))[:400]:
                rel = path.relative_to(root).as_posix()
                if not rel.startswith("."):
                    commands.append(
                        Command(f"Open file {rel}", partial(self.open_file, rel), "file")
                    )
        for problem in self.session.problems:
            if pc.classify(problem) in (ProblemClass.ERROR, ProblemClass.WARNING) and problem.file:
                commands.append(
                    Command(
                        f"Go to problem: {problem.message[:90]}",
                        partial(self.open_file, problem.file, problem.line or 1),
                        "problem",
                    )
                )
        return commands

    def open_command_palette(self) -> None:
        CommandPalette(self.palette_commands(), self).exec()

    # ---- the first screen --------------------------------------------------------------------
    def _show_welcome(self) -> None:
        """The welcome page while no project is open; the tabs once one is."""
        empty = self.session.path is None
        self.welcome.setVisible(empty)
        for part in (self.top_bar, self.workspace):
            part.setVisible(not empty)
        self.rail.set_enabled_destinations(not empty)
        docks = (self.project_dock, self.inspector_dock, self.problems_dock, self.provenance_dock)
        if empty and self._welcome_hid is None:
            self._welcome_hid = {dock: not dock.isHidden() for dock in docks}
            for dock in docks:
                dock.hide()
        elif not empty and self._welcome_hid is not None:
            hidden, self._welcome_hid = self._welcome_hid, None
            for dock, was_shown in hidden.items():
                if was_shown and dock not in self._narrow_hid:
                    dock.show()
            self._regime = ""  # the width may have changed while the first screen was up
            self._fit_to_width()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (Qt naming)
        if self._dropped_folder(event.mimeData()) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (Qt naming)
        folder = self._dropped_folder(event.mimeData())
        if folder is not None:
            event.acceptProposedAction()
            self.open_project(folder, background=True)

    @staticmethod
    def _dropped_folder(mime: QMimeData) -> Path | None:
        """The one local folder in a drop (a file or several items are not a project)."""
        urls = mime.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        return path if path.is_dir() else None

    # ---- the Reports page --------------------------------------------------------------------
    def update_reports_page(self) -> None:
        """What can be exported now and where each part stands."""
        session = self.session
        items: list[ReportItem] = []
        outputs = session.outputs
        if outputs:
            incomplete = any(o.incomplete for o in outputs)
            items.append(
                ReportItem(
                    "budgets",
                    "Budgets: power, mass, thermal, link",
                    ", ".join(o.prefix for o in outputs),
                    Status.NEAR if incomplete else Status.PASS,
                    "Ready, with n/a where inputs are placeholders" if incomplete else "Ready",
                    True,
                )
            )
        else:
            text = "Fix the errors first" if session.path is not None else "Open a project"
            items.append(
                ReportItem(
                    "budgets", "Budgets: power, mass, thermal, link", "", Status.FAIL, text, False
                )
            )
        timeline, scenario = self.timeline_view, self.scenario_view
        items.append(
            self._time_item(
                "timeline",
                "Power timeline",
                "power_time_<scenario> (series per case, orbits, violations)",
                timeline.result is not None,
                timeline.is_valid(),
            )
        )
        items.append(
            self._time_item(
                "scenario",
                "Scenario results",
                "environment, eclipses, passes, timeline (CSV, JSON)",
                scenario.last_run is not None,
                scenario.last_run is not None
                and not scenario.is_stale
                and scenario.last_run.scenario_id == scenario.selected_id(),
                formats=False,
            )
        )
        self.reports_view.set_items(items)
        self.reports_view.set_provenance(session.provenance)

    @staticmethod
    def _time_item(
        key: str, title: str, detail: str, computed: bool, valid: bool, formats: bool = True
    ) -> ReportItem:
        if valid:
            return ReportItem(key, title, detail, Status.PASS, "Ready", True, formats)
        if computed:
            return ReportItem(
                key, title, detail, Status.NEAR, "Out of date: press Run", False, formats
            )
        return ReportItem(
            key, title, detail, Status.NOT_CHECKED, "Not worked out: press Run", False, formats
        )

    def _export_selected(self, keys: set[str], formats: set[str], folder: str) -> None:
        """Write what the Reports page asked for, one part after the other."""
        if self._queue_active:
            return
        order: list[str] = [k for k in ("budgets", "timeline", "scenario") if k in keys]
        if not order:
            return
        self._queue, self._queue_paths = order, []
        self._queue_formats, self._queue_folder = set(formats), Path(folder).expanduser()
        self._queue_active = True
        self.reports_view.set_busy(True)
        self._queue_next()

    def _queue_next(self) -> None:
        if not self._queue:
            paths, self._queue_active = self._queue_paths, False
            self.reports_view.set_busy(False)
            self.reports_view.show_results(paths)
            where = f" to {self._queue_folder}" if paths else ""
            self.statusBar().showMessage(f"Exported {len(paths)} file(s){where}.")
            return
        key = self._queue.pop(0)
        folder, formats = self._queue_folder, self._queue_formats
        if key == "budgets":
            self.export_to(folder, formats)
        elif key == "timeline":
            self.timeline_view.export_to(folder, formats)
        else:
            try:
                written = self.scenario_view.export_to(folder)
            except (OutputError, OSError) as exc:
                # OutputError texts are plain by construction; an OSError is described, not echoed
                self._queue_step_failed(
                    str(exc)
                    if isinstance(exc, OutputError)
                    else "The files could not be written. Check that you may write to the folder."
                )
                return
            self._queue_step_done([str(p) for p in written])

    def _queue_step_done(self, paths: list[str]) -> None:
        if self._queue_active:
            self._queue_paths.extend(paths)
            self._queue_next()

    def _queue_step_failed(self, message: str) -> None:
        if not self._queue_active:
            return
        paths, self._queue, self._queue_active = self._queue_paths, [], False
        self.reports_view.set_busy(False)
        self.reports_view.show_results(paths)
        self.reports_view.show_failure(message)

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
