"""Project session: loads a project folder and computes the budgets. No widgets here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

from budget_core.io.project_loader import LoadResult, load_project
from budget_core.link.evaluate import StaticLinkResult, link_static_budget
from budget_core.mass.static_mass import StaticMassResult, static_mass_budget
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult, static_power_budget
from budget_core.problems import Problem, Severity, sort_problems
from budget_core.provenance import Provenance, make_provenance
from budget_core.reports.document import ReportDocument
from budget_core.reports.run import (
    BudgetOutput,
    link_output,
    mass_output,
    power_output,
    thermal_output,
)
from budget_core.thermal.static_thermal import StaticThermalResult, static_thermal_budget

# True: the interactive entry points (open, reload) compute in a background thread so the window
# stays usable while a large project loads. The tests of the window switch it off where they
# check the logic and not the threading.
BACKGROUND_LOADING = True


@dataclass
class _Computed:
    """Everything a (re)load produces. Built by `_compute` without touching any widget or the
    session, so it can run in a thread."""

    load_result: LoadResult | None = None
    power: StaticPowerResult | None = None
    mass: StaticMassResult | None = None
    thermal: StaticThermalResult | None = None
    link: StaticLinkResult | None = None
    provenance: Provenance | None = None
    document: ReportDocument | None = None
    mass_document: ReportDocument | None = None
    thermal_document: ReportDocument | None = None
    link_document: ReportDocument | None = None
    outputs: list[BudgetOutput] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)


def _compute(path: Path) -> _Computed:
    out = _Computed()
    try:
        load_result = load_project(path)
        out.load_result = load_result
        out.problems = list(load_result.problems)
        project = load_result.project
        if project is not None:
            out.power = static_power_budget(project)
            out.mass = static_mass_budget(project)
            out.thermal = static_thermal_budget(project)
            out.provenance = make_provenance(project)
            load_problems = load_result.problems
            power_out = power_output(project, out.power, out.provenance, load_problems)
            mass_out = mass_output(project, out.mass, out.provenance, load_problems)
            thermal_out = thermal_output(project, out.thermal, out.provenance, load_problems)
            out.outputs = [power_out, mass_out, thermal_out]
            out.document, out.mass_document = power_out.document, mass_out.document
            out.thermal_document = thermal_out.document
            if project.links:
                out.link = link_static_budget(project)
                link_out = link_output(project, out.link, out.provenance, load_problems)
                out.outputs.append(link_out)
                out.link_document = link_out.document
            out.problems = sort_problems(
                [
                    *out.problems,
                    *out.power.problems,
                    *out.mass.problems,
                    *out.thermal.problems,
                    *(out.link.problems if out.link else ()),
                ]
            )
    except Exception as exc:  # never show a traceback; say what happened in plain words
        out = _Computed(
            problems=[
                Problem(
                    Severity.ERROR,
                    "INTERNAL_ERROR",
                    f"The project could not be processed ({type(exc).__name__}).",
                    hint="Run 'budget validate' on the folder to see the details, then report it.",
                )
            ]
        )
    return out


class _LoadWorker(QThread):
    """Computes a project in a thread; `done` carries the result to the window thread."""

    done = Signal(object)

    def __init__(self, path: Path, generation: int) -> None:
        super().__init__()
        self.path = path
        self.generation = generation

    def run(self) -> None:
        self.done.emit(_compute(self.path))


class ProjectSession(QObject):
    """Holds the open project and its results; emits `changed` after every (re)load."""

    changed = Signal()
    loading_changed = Signal(bool)  # a background load started (True) or ended (False)

    def __init__(self) -> None:
        super().__init__()
        self._worker: _LoadWorker | None = None
        self._generation = 0  # grows with every request; an older result is dropped
        self._pending = False  # one more load is wanted when the running one ends
        self.path: Path | None = None
        self.load_result: LoadResult | None = None
        self.power: StaticPowerResult | None = None
        self.mass: StaticMassResult | None = None
        self.thermal: StaticThermalResult | None = None
        self.link: StaticLinkResult | None = None
        self.provenance: Provenance | None = None
        self.document: ReportDocument | None = None  # power budget report
        self.mass_document: ReportDocument | None = None
        self.thermal_document: ReportDocument | None = None
        self.link_document: ReportDocument | None = None
        self.outputs: list[BudgetOutput] = []
        self.problems: list[Problem] = []

    @property
    def project(self) -> Project | None:
        return self.load_result.project if self.load_result else None

    # ---- loading -----------------------------------------------------------------------------
    def open(self, path: Path) -> None:
        """Open a project and wait for it (programs and tests). The window uses `open_async`."""
        self.path = Path(path)
        self.reload()

    def reload(self) -> None:
        """Load again and wait for the result. A load that runs in the background is dropped."""
        if self.path is None:
            return
        self._generation += 1
        self._pending = False
        self._apply(_compute(self.path))

    def open_async(self, path: Path) -> None:
        self.path = Path(path)
        self.reload_async()

    def reload_async(self) -> None:
        """Load in a background thread; `changed` is emitted when the result is in. A request
        that arrives while a load runs is answered by one more load after it (the running one
        started before the files changed, so its result is dropped)."""
        if self.path is None:
            return
        if not BACKGROUND_LOADING:
            self.reload()
            return
        self._generation += 1
        if self._worker is not None:
            self._pending = True
            return
        self._start_worker()

    @property
    def loading(self) -> bool:
        return self._worker is not None

    def _start_worker(self) -> None:
        assert self.path is not None
        worker = _LoadWorker(self.path, self._generation)
        worker.done.connect(self._worker_done)
        self._worker = worker
        self.loading_changed.emit(True)
        worker.start()

    def _worker_done(self, computed: _Computed) -> None:
        worker = self._worker
        if worker is None:
            return
        worker.wait(10000)
        self._worker = None
        worker.deleteLater()
        if worker.generation != self._generation or self._pending:
            if self._pending:  # asked again meanwhile: load once more, drop this result
                self._pending = False
                self._start_worker()
                return
            self.loading_changed.emit(False)  # a synchronous reload has already shown a newer one
            return
        self.loading_changed.emit(False)
        self._apply(computed)

    def wait_for_loading(self) -> None:
        """Block until a background load has ended (closing the window, tests)."""
        while self._worker is not None:
            self._worker.wait(50)
            QCoreApplication.processEvents()

    def _apply(self, computed: _Computed) -> None:
        self.load_result = computed.load_result
        self.power, self.mass = computed.power, computed.mass
        self.thermal, self.link = computed.thermal, computed.link
        self.provenance = computed.provenance
        self.document, self.mass_document = computed.document, computed.mass_document
        self.thermal_document, self.link_document = (
            computed.thermal_document,
            computed.link_document,
        )
        self.outputs = list(computed.outputs)
        self.problems = list(computed.problems)
        self.changed.emit()
