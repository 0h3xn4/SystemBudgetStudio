"""Scenario view: timeline, rule and segment editors, results tables, background computation.

The environment (orbit, eclipses, passes) is computed in a worker thread. Editing rules, segments
or the default mode only rebuilds the timeline from the existing environment (it is reused while
`environment_key` is unchanged); changing orbit, sites, times or step marks the results stale.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from budget_core.control import Cancelled, RunControl
from budget_core.model import Project
from budget_core.provenance import make_provenance
from budget_core.reports.document import NA
from budget_core.reports.files import OutputError
from budget_core.scenario.export import write_scenario_outputs
from budget_core.scenario.run import (
    ScenarioRun,
    ScenarioRunError,
    environment_key,
    rebuild_timeline,
    run_scenario,
)
from budget_core.timeutil import format_utc
from budget_gui.cancel_support import (
    CANCEL_TEXT,
    CANCEL_TIP,
    CANCELLING_TEXT,
    COMPUTE_TEXT,
    cancelled_text,
    computing_text,
)
from budget_gui.delegates import NUMERIC_ROLE, STATE_ROLE
from budget_gui.model_document import ModelDocument
from budget_gui.scenario_editor import ScenarioEditor
from budget_gui.theme import Status
from budget_gui.timeline import TimelineWidget
from budget_gui.validity import CHANGED_WHILE_RUNNING_TEXT, NOT_COMPUTED_TEXT

EMPTY_TEXT = (
    "This project has no scenario. Add a file in scenarios/ to work out the power timeline "
    "and the link passes."
)


class ScenarioWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    stage = Signal(str)
    cancelled = Signal()

    def __init__(self, project: Project, scenario_id: str) -> None:
        super().__init__()
        self._project = project
        self._scenario_id = scenario_id

    def run(self) -> None:
        control = RunControl(self.isInterruptionRequested, self.stage.emit)
        try:
            self.finished_ok.emit(run_scenario(self._project, self._scenario_id, control))
        except Cancelled:
            self.cancelled.emit()
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The scenario could not be computed ({type(exc).__name__}).")


def fill_table(
    table: QTableWidget,
    headers: list[str],
    rows: list[list[str]],
    numeric: Collection[int] = (),
    states: Mapping[tuple[int, int], Status] | None = None,
) -> None:
    """Fill a read-only table. With `numeric` columns (right-aligned figures) and `states` (a cell
    that is broken, or not computed) a table whose delegate is a `CellDelegate` shows them as the
    budget tables do; a cell that reads `n/a` is always *not checked*."""
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    given = states or {}
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status = given.get((r, c), Status.NOT_CHECKED if text == NA else None)
            item.setData(STATE_ROLE, status.value if status else None)
            item.setData(NUMERIC_ROLE, c in numeric or text == NA)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


class ScenarioView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)
    stage_changed = Signal(str)  # what a computation in progress is working on
    cancelled = Signal()  # a computation was stopped at the user's request

    def __init__(self, document: ModelDocument | None = None) -> None:
        super().__init__()
        self._owns_document = document is None  # a view on its own keeps its own document
        self.document = document if document is not None else ModelDocument()
        self.project: Project | None = None
        self.last_run: ScenarioRun | None = None
        self.is_stale = False
        self._key = ""
        self._summary = ""  # the status text of the last computation
        self._computing_for: Project | None = None
        self._worker: ScenarioWorker | None = None

        self.combo = QComboBox()
        self.compute_button = QPushButton("Compute")
        self.compute_button.setProperty("kind", "secondary")  # Run is the primary action
        self.compute_button.clicked.connect(self._compute_or_cancel)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.empty_label = QLabel(EMPTY_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scenario_label = QLabel("Scenario")
        top = QHBoxLayout()
        top.addWidget(self.scenario_label)
        top.addWidget(self.combo)
        top.addWidget(self.compute_button)
        top.addWidget(self.status, 1)

        self.timeline = TimelineWidget()
        self.editor = ScenarioEditor(self.document)
        self.eclipse_table = QTableWidget()
        self.passes_table = QTableWidget()
        self.timeline_table = QTableWidget()
        self.eclipse_table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        self.passes_table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        self.timeline_table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        tabs = QTabWidget()
        scroll = (
            QScrollArea()
        )  # the editor scrolls on a small screen instead of forcing a tall window
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.editor)
        tabs.addTab(scroll, "Rules and segments")
        tabs.addTab(self.eclipse_table, "Eclipses")
        tabs.addTab(self.passes_table, "Passes")
        tabs.addTab(self.timeline_table, "Mode timeline")

        self.body = QSplitter(Qt.Orientation.Vertical)
        self.body.addWidget(self.timeline)
        self.body.addWidget(tabs)
        self.body.setChildrenCollapsible(False)
        self.timeline.setMinimumHeight(180)
        self.body.setStretchFactor(0, 2)
        self.body.setStretchFactor(1, 3)  # the editor and the tables get more room than the strip
        self.body.setSizes([300, 520])

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.body)

        self.combo.currentTextChanged.connect(self._selected)
        self.timeline.range_selected.connect(self._range_selected)
        self.set_project(None)

    def use_shared_selector(self) -> None:
        """The scenario is chosen in the top bar: this view keeps its selector hidden."""
        self.scenario_label.hide()
        self.combo.hide()

    # ---- project -----------------------------------------------------------------------------
    def set_empty_text(self, text: str | None) -> None:
        """Say why there is nothing to show (None: the usual sentence)."""
        self.empty_label.setText(text or EMPTY_TEXT)

    def selected_id(self) -> str:
        return self.combo.currentText()

    def set_project(self, project: Project | None) -> None:
        previous = self.selected_id()
        self.project = project
        if self._owns_document and (project is not None or not self.document.is_modified()):
            self.document.reload(project.root if project else None, project)
        ids = sorted(project.scenarios) if project else []
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(ids)
        if previous in ids:
            self.combo.setCurrentText(previous)
        self.combo.blockSignals(False)

        shown = bool(ids)
        keep_edits = not shown and self.editor.is_modified()  # never drop edits silently (D-060)
        self.empty_label.setVisible(not shown and not keep_edits)
        self.body.setVisible(shown or keep_edits)
        self.compute_button.setEnabled(shown)  # while it computes the button cancels
        self.combo.setEnabled(shown)
        if not shown or project is None:
            if keep_edits:
                self.status.setText(
                    "The project has no scenario to show right now. Your unsaved edits are kept; "
                    "save or discard them, or fix the errors in the Problems panel."
                )
            else:
                self.editor.clear()
                self.status.setText("")
            self._show_run(None)
            return

        scenario_id = self.selected_id()
        scenario = project.scenarios[scenario_id]
        modes, sites = (
            sorted(project.modes),
            sorted(set(project.ground_stations) | set(project.targets)),
        )
        self.editor.show_scenario(project.root, scenario_id, modes, sites)

        run = self.last_run
        if run is None or run.scenario_id != scenario_id:
            self._show_run(None)
            self.is_stale = False
            self.status.setText(NOT_COMPUTED_TEXT)
        elif environment_key(project, scenario) != self._key:
            # orbit, a site, the times or the step changed (also in another file): the environment
            # of the run is out of date, whatever else changed
            self.is_stale = True
            self.status.setText(
                "The scenario parameters changed since the last computation. Press Compute."
            )
        else:
            was_stale, self.is_stale = self.is_stale, False
            if run.scenario != scenario:
                self.last_run = rebuild_timeline(run, scenario)
                self._show_run(self.last_run)
                self.status.setText("Timeline updated from the unchanged environment.")
            elif was_stale:
                self.status.setText(self._summary)

    def _selected(self, text: str) -> None:
        if self.project is None or text == self.editor.scenario_id:
            return
        # unsaved edits of this scenario stay in the document: choosing another does not drop them
        self.last_run = None
        self.set_project(self.project)

    # ---- compute -----------------------------------------------------------------------------
    def _compute_or_cancel(self) -> None:
        if self._worker is not None:
            self.cancel()
        else:
            self.compute()

    def cancel(self) -> None:
        """Ask the computation in progress to stop; it stops at its next step."""
        if self._worker is not None:
            self._worker.requestInterruption()
            self.compute_button.setEnabled(False)
            self.status.setText(CANCELLING_TEXT)

    def _stage(self, text: str) -> None:
        self.status.setText(computing_text(text))
        self.stage_changed.emit(text)

    def _cancelled(self) -> None:
        self._finish_worker()
        self._computing_for = None
        self.status.setText(cancelled_text(self.last_run is not None))
        self.cancelled.emit()

    def compute(self) -> None:
        if self.project is None or not self.selected_id() or self._worker is not None:
            return
        self.compute_button.setText(CANCEL_TEXT)
        self.compute_button.setToolTip(CANCEL_TIP)
        self.status.setText("Computing…")
        self._computing_for = self.project
        worker = ScenarioWorker(self.project, self.selected_id())
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        worker.stage.connect(self._stage)
        worker.cancelled.connect(self._cancelled)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(10000)
            self._worker = None
        self.compute_button.setText(COMPUTE_TEXT)
        self.compute_button.setToolTip("")
        self.compute_button.setEnabled(self.project is not None and bool(self.selected_id()))

    def _done(self, run: ScenarioRun) -> None:
        self._finish_worker()
        computed_for = self._computing_for
        if self.project is None or computed_for is None:
            return
        if run.scenario_id != self.selected_id():
            return  # another scenario was selected while it ran: the result is not shown
        self.last_run = run
        # the key describes the project the run was computed for; if it was reloaded meanwhile
        # the run is stale and must not be reused by the other views
        self.is_stale = self.project is not computed_for
        self._key = environment_key(computed_for, run.scenario)
        self._show_run(run)
        env = run.env
        passes = ", ".join(f"{sid} {len(v.passes)}" for sid, v in sorted(env.sites.items()))
        text = f"{len(env.eclipses)} eclipse(s)" + (f"; passes: {passes}" if passes else "")
        if run.notes:
            text += " — " + "; ".join(run.notes)
        if run.problems:
            text += " — " + "; ".join(p.message for p in run.problems)
        self._summary = text
        self.status.setText(CHANGED_WHILE_RUNNING_TEXT if self.is_stale else text)
        self.computed.emit(run)

    def _failed(self, message: str) -> None:
        self._finish_worker()
        self.last_run = None
        self._show_run(None)
        self.status.setText(message)
        self.compute_failed.emit(message)

    def wait_for_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)

    def is_busy(self) -> bool:
        """A computation is running."""
        return self._worker is not None

    def reusable_run(self, scenario_id: str) -> ScenarioRun | None:
        """The computed environment of this scenario with its current timeline, or None when the
        environment is missing or out of date (the power timeline then computes its own)."""
        run, project = self.last_run, self.project
        if run is None or project is None or run.scenario_id != scenario_id or self.is_stale:
            return None
        scenario = project.scenarios.get(scenario_id)
        if scenario is None or environment_key(project, scenario) != self._key:
            return None
        return run if run.scenario == scenario else rebuild_timeline(run, scenario)

    # ---- display -----------------------------------------------------------------------------
    def _show_run(self, run: ScenarioRun | None) -> None:
        modes = sorted(self.project.modes) if self.project else []
        self.timeline.set_run(run, modes)
        if run is None:
            for table in (self.eclipse_table, self.passes_table, self.timeline_table):
                table.setRowCount(0)
            return
        start = run.env.grid.start

        def utc(seconds: float) -> str:
            return format_utc(start + timedelta(seconds=seconds))

        fill_table(
            self.eclipse_table,
            ["Start (s)", "End (s)", "Duration (s)", "Start (UTC)"],
            [
                [f"{e.start_s:.1f}", f"{e.end_s:.1f}", f"{e.duration_s:.1f}", utc(e.start_s)]
                for e in run.env.eclipses
            ],
        )
        fill_table(
            self.passes_table,
            ["Site", "Kind", "AOS (s)", "LOS (s)", "Duration (s)", "Max elevation (deg)"],
            [
                [
                    sid,
                    vis.site.kind,
                    f"{p.aos_s:.1f}",
                    f"{p.los_s:.1f}",
                    f"{p.duration_s:.1f}",
                    f"{p.max_elevation_deg:.1f}",
                ]
                for sid, vis in sorted(run.env.sites.items())
                for p in vis.passes
            ],
        )
        fill_table(
            self.timeline_table,
            ["Start (s)", "End (s)", "Duration (s)", "Mode"],
            [
                [f"{s.start_s:.1f}", f"{s.end_s:.1f}", f"{s.duration_s:.1f}", s.mode]
                for s in run.timeline
            ],
        )

    def _range_selected(self, start: float, end: float) -> None:
        if self.project is not None and self.selected_id():
            self.editor.add_segment(round(start, 1), round(end - start, 1))

    # ---- export ------------------------------------------------------------------------------
    def export_to(self, folder: Path) -> list[Path]:
        """Write the computed scenario. Raises `OutputError` (plain message) when there is no
        result, or it was computed for inputs that have changed since."""
        if self.last_run is None or self.project is None:
            return []
        if self.is_stale or self.last_run.scenario_id != self.selected_id():
            raise OutputError(
                "The scenario results are out of date: the project changed since they were "
                "computed. Press Compute in the Scenario tab, then export."
            )
        provenance = make_provenance(self.project, scenario=self.last_run.scenario_id)
        return write_scenario_outputs(self.last_run, provenance, folder)
