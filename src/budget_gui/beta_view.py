"""The Beta sweep page of the Thermal area: node temperatures against the beta angle (D-250).

The steady-state thermal model of the project is solved for a range of beta angles in a worker
thread; the solar view of every surface that gives its direction (`normal_lvlh`) comes from the
angle, the rest of the case is the project's own. The page shows the temperatures and the sunlit
part of the orbit as a plot and every angle as a row of a table, and writes the same CSV, JSON and
plot as `budget thermal-beta`. Nothing here computes physics: it asks `thermal_beta_sweep`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budget_core.control import Cancelled, RunControl
from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.model import Project
from budget_core.plots.thermal_beta import thermal_beta_plot
from budget_core.problems import Problem
from budget_core.provenance import make_provenance
from budget_core.reports.files import write_files
from budget_core.reports.thermal_beta_export import beta_files
from budget_core.scenario.run import ScenarioRun, ScenarioRunError, run_scenario
from budget_core.thermal.beta_sweep import (
    BetaSweep,
    BetaSweepError,
    Mode,
    beta_range,
    node_temperatures,
    orbit_of_run,
    thermal_beta_sweep,
)
from budget_gui import theme
from budget_gui.cancel_support import (
    CANCEL_TEXT,
    CANCEL_TIP,
    CANCELLING_TEXT,
    COMPUTE_TEXT,
    cancelled_text,
    computing_text,
)
from budget_gui.components import Button, EmptyState
from budget_gui.plot_prepare import PreparedPlot, prepare
from budget_gui.plot_widget import PlotWidget
from budget_gui.scenario_view import fill_table
from budget_gui.theme import Status
from budget_gui.time_axis import ValueAxis
from budget_gui.validity import (
    CHANGED_WHILE_RUNNING_TEXT,
    NOT_COMPUTED_TEXT,
    STALE_TEXT,
    ResultKey,
)

NO_THERMAL_TEXT = (
    "The project has no thermal model or no thermal environment, so there is nothing to sweep. "
    "Add config/thermal_model.yaml and config/thermal_environment.yaml (see the thermal budget)."
)
NO_NORMALS_TEXT = (
    "No surface gives its direction yet. Add normal_lvlh to the surfaces of "
    "config/thermal_model.yaml (a unit vector, or a face name: +x, -x, +y, -y, +z, -z) and the "
    "beta angle has something to act on."
)
COMPUTE_TIP = "Solve the thermal model for every beta angle of the range"
MODES: tuple[tuple[str, Mode], ...] = (
    ("Orbit average", "average"),
    ("Worst instant", "peak"),
)
FROM_SCENARIO = "Orbit of the scenario"
FROM_ALTITUDE = "Circular orbit at an altitude"
DEFAULT_ALTITUDE_KM = 500.0
ALTITUDE_RANGE_KM = (100.0, 40000.0)
TABLE_HEADROOM = "Smallest margin to a limit (K)"


@dataclass(frozen=True)
class SweepRequest:
    case: str
    mode: Mode
    betas: tuple[float, ...]
    scenario: str | None  # None: a circular orbit at `altitude_km`
    altitude_km: float
    earth_model: str


class BetaWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    stage = Signal(str)
    cancelled = Signal()

    def __init__(self, project: Project, request: SweepRequest, run: ScenarioRun | None) -> None:
        super().__init__()
        self._args = (project, request, run)
        self.plot: PreparedPlot | None = None  # ready to draw (D-182)

    def run(self) -> None:
        project, request, scenario_run = self._args
        control = RunControl(self.isInterruptionRequested, self.stage.emit)
        try:
            if request.scenario is None:
                earth = EARTH_MODELS[request.earth_model].radius_m
                orbit = earth + request.altitude_km * 1000.0
            else:
                control.stage("Orbit of the scenario")
                if scenario_run is None:
                    scenario_run = run_scenario(project, request.scenario, control)
                earth, orbit = orbit_of_run(scenario_run)
            control.stage("Node temperatures")
            sweep = thermal_beta_sweep(
                project,
                request.case,
                request.betas,
                mode=request.mode,
                earth_radius_m=earth,
                orbit_radius_m=orbit,
                control=control,
            )
        except Cancelled:
            self.cancelled.emit()
            return
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
            return
        except BetaSweepError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The sweep could not be computed ({type(exc).__name__}).")
            return
        try:  # the plot is work for this thread, not the window thread
            self.plot = prepare(thermal_beta_plot(sweep))
        except Exception:  # the view makes the plot itself
            self.plot = None
        self.finished_ok.emit(sweep)


class BetaExportWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, build: Callable[[], list[tuple[str, bytes | str]]], folder: Path) -> None:
        super().__init__()
        self._build = build
        self._folder = folder

    def run(self) -> None:
        try:
            paths = write_files(self._folder, self._build())
        except Exception as exc:  # plain message only
            self.failed.emit(f"The sweep could not be exported ({type(exc).__name__}).")
            return
        self.finished_ok.emit([str(p) for p in paths])


def _spin(low: float, high: float, value: float, step: float, name: str) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, high)
    box.setDecimals(1)
    box.setSingleStep(step)
    box.setValue(value)
    box.setAccessibleName(name)
    return box


class BetaView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)
    stage_changed = Signal(str)
    cancelled = Signal()
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.load_problems: list[Problem] = []
        self.result: BetaSweep | None = None
        self.reason: str | None = None  # why there is nothing to show (a project with errors)
        self.run_provider: Callable[[str], ScenarioRun | None] | None = None
        self._revision = 0
        self._result_key: ResultKey | None = None
        self._computing_key: ResultKey | None = None
        self._scenario = ""  # the scenario of the top bar (shared)
        self._worker: BetaWorker | None = None
        self._export_worker: BetaExportWorker | None = None
        self._prepared: PreparedPlot | None = None
        self._prepared_for: BetaSweep | None = None

        self.case_combo = QComboBox()
        self.case_combo.setAccessibleName("Thermal case")
        self.mode_combo = QComboBox()
        self.mode_combo.setAccessibleName("Heat loads")
        for title, mode in MODES:
            self.mode_combo.addItem(title, mode)
        self.beta_min = _spin(-90.0, 90.0, -90.0, 5.0, "Lowest beta angle (deg)")
        self.beta_max = _spin(-90.0, 90.0, 90.0, 5.0, "Highest beta angle (deg)")
        self.beta_step = _spin(0.5, 90.0, 15.0, 5.0, "Beta angle step (deg)")
        self.orbit_combo = QComboBox()
        self.orbit_combo.setAccessibleName("Orbit")
        self.orbit_combo.addItems([FROM_SCENARIO, FROM_ALTITUDE])
        self.altitude = _spin(*ALTITUDE_RANGE_KM, DEFAULT_ALTITUDE_KM, 50.0, "Altitude (km)")
        self.compute_button = Button(
            "Compute", "primary", icon="refresh-cw", compact=True, tip=COMPUTE_TIP
        )
        self.export_button = Button(
            "Export…", icon="file-output", compact=True, tip="Write the results to files"
        )
        self.export_button.setEnabled(False)
        self.status = QLabel("")
        self.status.setWordWrap(True)

        row = QHBoxLayout()
        row.setSpacing(theme.gap(1))
        for label, widget in (
            ("Case", self.case_combo),
            ("Heat loads", self.mode_combo),
            ("Beta from", self.beta_min),
            ("to", self.beta_max),
            ("step", self.beta_step),
            ("Orbit", self.orbit_combo),
        ):
            row.addWidget(QLabel(label))
            row.addWidget(widget)
        self.altitude_label = QLabel("at")
        row.addWidget(self.altitude_label)
        row.addWidget(self.altitude)
        row.addWidget(self.compute_button)
        row.addWidget(self.export_button)
        row.addStretch(1)

        self.plot = PlotWidget()
        self.plot.setAccessibleName("Beta sweep plot")
        self.plot.set_time_axis(ValueAxis("Beta angle", "deg"))
        self.table = QTableWidget()
        self.table.setAccessibleName("Beta sweep table")
        self.table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        self.body = QSplitter(Qt.Orientation.Vertical)
        self.body.addWidget(self.plot)
        self.body.addWidget(self.table)
        self.body.setStretchFactor(0, 5)
        self.body.setStretchFactor(1, 3)
        self.empty = EmptyState(NO_THERMAL_TEXT, icon="thermometer")

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.status)
        layout.addWidget(self.body, 1)
        layout.addWidget(self.empty, 1)

        self.compute_button.clicked.connect(self._compute_or_cancel)
        self.export_button.clicked.connect(lambda: self._choose_export())
        self.orbit_combo.currentTextChanged.connect(lambda _t: self._orbit_changed())
        for combo in (self.case_combo, self.mode_combo):
            combo.currentTextChanged.connect(lambda _t: self._inputs_changed())
        for box in (self.beta_min, self.beta_max, self.beta_step, self.altitude):
            box.valueChanged.connect(lambda _v: self._inputs_changed())
        self.set_project(None, [])

    # ---- project -----------------------------------------------------------------------------
    def set_empty_text(self, text: str | None) -> None:
        """Say why there is nothing to show (None: what the project itself lacks)."""
        self.reason = text
        self._show_state()

    def use_scenario(self, scenario_id: str) -> None:
        """The scenario of the top bar, whose orbit the sweep uses."""
        if scenario_id != self._scenario:
            self._scenario = scenario_id
            self._inputs_changed()

    def _thermal_ready(self) -> tuple[bool, bool]:
        """(a thermal model and environment exist, a surface gives its direction)."""
        project = self.project
        model = project.config.thermal_model if project else None
        env = project.config.thermal_environment if project else None
        if model is None or env is None or not env.cases:
            return False, False
        return True, any(s.normal_lvlh is not None for s in model.surfaces)

    def set_project(self, project: Project | None, load_problems: list[Problem]) -> None:
        had_scenario = bool(self.project and self.project.scenarios)
        self.project = project
        self._revision += 1
        self.load_problems = list(load_problems)
        previous = self.case_combo.currentText()
        env = project.config.thermal_environment if project else None
        cases = sorted(env.cases) if env else []
        self.case_combo.blockSignals(True)
        self.case_combo.clear()
        self.case_combo.addItems(cases)
        if previous in cases:
            self.case_combo.setCurrentText(previous)
        elif "hot" in cases:
            self.case_combo.setCurrentText("hot")
        self.case_combo.blockSignals(False)
        has_scenario = bool(project and project.scenarios)
        self.orbit_combo.blockSignals(True)
        if not has_scenario and self.orbit_combo.currentText() == FROM_SCENARIO:
            self.orbit_combo.setCurrentText(FROM_ALTITUDE)  # nothing else to choose
        elif has_scenario and not had_scenario:
            self.orbit_combo.setCurrentText(FROM_SCENARIO)  # the usual choice, once there is one
        self.orbit_combo.blockSignals(False)
        self._orbit_changed()
        self._show_state()
        if self.result is not None:
            self._update_validity()

    def _show_state(self) -> None:
        ready, normals = self._thermal_ready()
        shown = ready and normals and self.reason is None
        self.body.setVisible(shown)
        self.status.setVisible(shown)
        self.empty.setVisible(not shown)
        if not shown:
            self.empty.message.setText(
                self.reason or (NO_NORMALS_TEXT if ready else NO_THERMAL_TEXT)
            )
        controls: tuple[QWidget, ...] = (
            self.case_combo,
            self.mode_combo,
            self.beta_min,
            self.beta_max,
            self.beta_step,
            self.orbit_combo,
            self.altitude,
        )
        for control in controls:
            control.setEnabled(shown)
        self.compute_button.setEnabled(shown and self._worker is None)
        if not shown:
            self.result = None
            self._show()
            self.status.setText("")
        elif self.result is None:
            self.status.setText(NOT_COMPUTED_TEXT)

    def _orbit_changed(self) -> None:
        custom = self.orbit_combo.currentText() == FROM_ALTITUDE
        self.altitude.setVisible(custom)
        self.altitude_label.setVisible(custom)
        has_scenario = bool(self.project and self.project.scenarios)
        model = self.orbit_combo.model()
        item = model.item(0) if hasattr(model, "item") else None
        if item is not None:
            item.setEnabled(has_scenario)  # a project with no scenario has only the altitude
        self._inputs_changed()

    # ---- what the result belongs to ------------------------------------------------------------
    def _mode(self) -> Mode:
        return self.mode_combo.currentData()  # type: ignore[no-any-return]

    def current_key(self) -> ResultKey:
        orbit = (
            f"{self.altitude.value():.1f}"
            if self.orbit_combo.currentText() == FROM_ALTITUDE
            else self._scenario
        )
        return ResultKey(
            self._revision,
            self._scenario,
            (
                self.case_combo.currentText(),
                self._mode(),
                f"{self.beta_min.value():.1f}",
                f"{self.beta_max.value():.1f}",
                f"{self.beta_step.value():.1f}",
                self.orbit_combo.currentText(),
                orbit,
            ),
        )

    def is_valid(self) -> bool:
        return self.result is not None and self._result_key == self.current_key()

    @property
    def is_stale(self) -> bool:
        return self.result is not None and not self.is_valid()

    def _update_validity(self) -> None:
        if self.result is None:
            return
        self.export_button.setEnabled(self.is_valid() and self._export_worker is None)
        if self.is_stale:
            self.status.setText(STALE_TEXT)
        elif self._worker is None:
            self.status.setText(self._summary(self.result))

    def _inputs_changed(self) -> None:
        self._update_validity()

    def request(self) -> SweepRequest | None:
        """What a computation started now would solve; None when the range is not a range."""
        try:
            betas = beta_range(self.beta_min.value(), self.beta_max.value(), self.beta_step.value())
        except BetaSweepError as exc:
            self.status.setText(str(exc))
            return None
        from_scenario = self.orbit_combo.currentText() == FROM_SCENARIO
        if from_scenario and not self._scenario:
            self.status.setText("The project has no scenario: choose a circular orbit.")
            return None
        return SweepRequest(
            self.case_combo.currentText(),
            self._mode(),
            tuple(betas),
            self._scenario if from_scenario else None,
            self.altitude.value(),
            self._earth_model(),
        )

    def _earth_model(self) -> str:
        return DEFAULT_EARTH_MODEL

    # ---- compute -----------------------------------------------------------------------------
    def _compute_or_cancel(self) -> None:
        if self._worker is not None:
            self.cancel()
        else:
            self.compute()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self.compute_button.setEnabled(False)
            self.status.setText(CANCELLING_TEXT)

    def _stage(self, text: str) -> None:
        self.status.setText(computing_text(text))
        self.stage_changed.emit(text)

    def compute(self) -> None:
        if self.project is None or self._worker is not None:
            return
        request = self.request()
        if request is None:
            return
        reused = (
            self.run_provider(request.scenario)
            if self.run_provider and request.scenario is not None
            else None
        )
        self.compute_button.setText(CANCEL_TEXT)
        self.compute_button.setToolTip(CANCEL_TIP)
        self.status.setText("Computing…")
        self._computing_key = self.current_key()
        worker = BetaWorker(self.project, request, reused)
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        worker.stage.connect(self._stage)
        worker.cancelled.connect(self._cancelled)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)
            self._worker = None
        self.compute_button.setText(COMPUTE_TEXT)
        self.compute_button.setToolTip(COMPUTE_TIP)
        ready, normals = self._thermal_ready()
        self.compute_button.setEnabled(ready and normals and self.reason is None)

    def _cancelled(self) -> None:
        self._finish_worker()
        self._computing_key = None
        self.status.setText(cancelled_text(self.result is not None))
        self.cancelled.emit()

    def _failed(self, message: str) -> None:
        self._finish_worker()
        self._computing_key = None
        self.result = None
        self._show()
        self.status.setText(message)
        self.compute_failed.emit(message)

    def _done(self, sweep: BetaSweep) -> None:
        prepared = self._worker.plot if self._worker is not None else None
        self._finish_worker()
        key, self._computing_key = self._computing_key, None
        self.result, self._result_key = sweep, key
        self._prepared, self._prepared_for = prepared, sweep
        self._show()
        self.export_button.setEnabled(self.is_valid())
        self.status.setText(CHANGED_WHILE_RUNNING_TEXT if self.is_stale else self._summary(sweep))
        self.computed.emit(sweep)

    def _summary(self, sweep: BetaSweep) -> str:
        mode = "orbit average" if sweep.mode == "average" else "worst instant"
        text = (
            f"Case {sweep.case}, {mode}: circular orbit at {sweep.altitude_m / 1000.0:.0f} km, "
            f"{len(sweep.surfaces_from_beta)} surface(s) from the beta angle, "
            f"{len(sweep.surfaces_typed)} with typed view ratios."
        )
        if any(not p.case.complete for p in sweep.points):
            text += " Some inputs are placeholders: angles marked n/a are not computed."
        return text

    def problems(self) -> list[Problem]:
        """Findings of the last sweep for the Problems panel; none for a stale one."""
        return [] if self.result is None or not self.is_valid() else list(self.result.problems)

    # ---- display -----------------------------------------------------------------------------
    def _show(self) -> None:
        sweep = self.result
        if sweep is None:
            self.plot.set_spec(None)
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.export_button.setEnabled(False)
            return
        if self._prepared is not None and self._prepared_for is sweep:
            self.plot.set_spec(self._prepared.spec, self._prepared)
        else:
            self.plot.set_spec(thermal_beta_plot(sweep))
        nodes = sorted({n.node for p in sweep.points for n in p.case.nodes})
        headers = [
            "Beta (deg)",
            "Sunlit (%)",
            "Orbit angle (deg)",
            *(f"{n} (K)" for n in nodes),
            "Units beyond a limit",
            TABLE_HEADROOM,
        ]
        rows: list[list[str]] = []
        states: dict[tuple[int, int], Status] = {}
        for r, p in enumerate(sweep.points):
            temps = node_temperatures(p)
            headroom = [
                v
                for c in p.case.checks
                for v in (c.lower_headroom_k, c.upper_headroom_k)
                if v is not None
            ]
            exceeded = sum(1 for c in p.case.checks if c.status == "exceeded")
            done = p.case.complete
            rows.append(
                [
                    f"{p.beta_deg:+.1f}",
                    f"{p.sunlit_fraction * 100.0:.1f}",
                    "" if p.u_deg is None else f"{p.u_deg:.0f}",
                    *(f"{temps[n]:.1f}" if n in temps and done else "n/a" for n in nodes),
                    str(exceeded) if done else "n/a",
                    f"{min(headroom):.1f}" if done and headroom else "n/a",
                ]
            )
            last = len(headers) - 2
            if done and exceeded:
                states[(r, last)] = Status.FAIL  # a number and a count, never a colour alone
        fill_table(self.table, headers, rows, numeric=range(len(headers)), states=states)

    # ---- export ------------------------------------------------------------------------------
    def _choose_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export the beta sweep to folder")
        if folder:
            self.export_to(Path(folder))

    def export_to(self, folder: Path) -> None:
        if self._export_worker is not None:
            self.export_failed.emit("An export is already running; wait for it to finish.")
            return
        sweep, project = self.result, self.project
        if sweep is None or project is None or not self.is_valid():
            self.export_failed.emit(
                "The project or a setting changed since this result was computed. "
                "Press Compute again."
                if self.is_stale
                else "Compute the beta sweep first."
            )
            return
        load_problems = list(self.load_problems)
        scenario = self._result_key.scenario if self._result_key else ""
        from_scenario = self.orbit_combo.currentText() == FROM_SCENARIO

        def build() -> list[tuple[str, bytes | str]]:
            provenance = make_provenance(
                project, scenario=scenario if from_scenario else "static (no scenario)"
            )
            return beta_files(sweep, provenance, load_problems)

        worker = BetaExportWorker(build, folder)
        worker.finished_ok.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        self._export_worker = worker
        self.status.setText("Exporting…")
        self.export_button.setEnabled(False)
        worker.start()

    def _end_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.wait()
            self._export_worker = None
        self.export_button.setEnabled(self.is_valid())

    def _export_done(self, paths: list[str]) -> None:
        self._end_export()
        self.status.setText(f"Exported {len(paths)} file(s).")
        self.export_finished.emit(paths)

    def _export_failed(self, message: str) -> None:
        self._end_export()
        self.status.setText(message)
        self.export_failed.emit(message)

    def wait_for_worker(self) -> None:
        for worker in (self._worker, self._export_worker):
            if worker is not None:
                worker.wait(30000)

    def is_busy(self) -> bool:
        return self._worker is not None or self._export_worker is not None
