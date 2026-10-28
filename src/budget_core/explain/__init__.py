"""Explain: how one displayed number was obtained (D-206). Used by `budget explain` and the
window's Explain view; see docs/models/explain.md."""

from __future__ import annotations

from collections.abc import Sequence

from budget_core.explain.link import explain_link, link_table_ids
from budget_core.explain.linkpass import explain_linkpass, linkpass_table_ids
from budget_core.explain.mass import explain_mass, mass_table_ids
from budget_core.explain.power import ExplainError, explain_power, power_table_ids
from budget_core.explain.thermal import explain_thermal, thermal_table_ids
from budget_core.explain.timeline import explain_timeline, timeline_table_ids
from budget_core.explain.trace import Explanation, Quantity, Step
from budget_core.link.evaluate import (
    LinkSeriesResult,
    StaticLinkResult,
    link_pass_series,
    link_static_budget,
)
from budget_core.mass.static_mass import StaticMassResult, static_mass_budget
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult, static_power_budget
from budget_core.power.time_domain import LoadBasis, TimeDomainResult, time_domain_budget
from budget_core.provenance import Provenance
from budget_core.reports.document import Table
from budget_core.reports.link_report import build_link_report
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.power_report import build_power_report
from budget_core.reports.thermal_report import build_thermal_report
from budget_core.reports.timeline_report import build_timeline_report
from budget_core.scenario.run import ScenarioRunError, run_scenario
from budget_core.thermal.static_thermal import StaticThermalResult, static_thermal_budget

__all__ = [
    "ExplainError",
    "Explainer",
    "Explanation",
    "Quantity",
    "Step",
    "explain_cell",
    "explainable_tables",
]


def explainable_tables(project: Project) -> list[tuple[str, str]]:
    """(table id, title) of every table whose cells can be explained."""
    return [
        *power_table_ids(project),
        *mass_table_ids(project),
        *thermal_table_ids(project),
        *link_table_ids(project),
        *(linkpass_table_ids(project) if project.scenarios else []),
        *(timeline_table_ids() if project.scenarios else []),
    ]


class Explainer:
    """Explains the cells of one project. It computes each budget once and keeps it, so that
    explaining many cells (a test, a window that explains as the cursor moves) stays cheap."""

    def __init__(
        self,
        project: Project,
        power: StaticPowerResult | None = None,
        mass: StaticMassResult | None = None,
        thermal: StaticThermalResult | None = None,
        link: StaticLinkResult | None = None,
        timeline: TimeDomainResult | None = None,
        link_series: LinkSeriesResult | None = None,
        *,
        scenario: str | None = None,
        load_basis: LoadBasis = "nominal",
        mission_phase: str | None = None,
    ) -> None:
        """`power`, `mass`, `thermal` and `link` are the static budgets of `project` when the
        caller has them. The timeline tables need a scenario: `timeline`, the result the caller
        has (solved again with its detail when it has none), or `scenario` (an id; optional when
        the project has one) with the basis and mission phase to solve it with."""
        self.project = project
        self._power = power
        self._mass = mass
        self._thermal = thermal
        self._link = link
        self._timeline = timeline
        self._link_series = link_series
        self._scenario = scenario
        self._load_basis: LoadBasis = load_basis
        self._mission_phase = mission_phase

    def _family(self, table_id: str) -> str:
        family = table_id.split(":", 1)[0]
        if family not in ("power", "mass", "thermal", "link", "timeline", "linkpass"):
            raise ExplainError("This table cannot be explained.")
        return family

    def power_result(self) -> StaticPowerResult:
        if self._power is None:
            self._power = static_power_budget(self.project)
        return self._power

    def mass_result(self) -> StaticMassResult:
        if self._mass is None:
            self._mass = static_mass_budget(self.project)
        return self._mass

    def thermal_result(self) -> StaticThermalResult:
        if self._thermal is None:
            self._thermal = static_thermal_budget(self.project)
        return self._thermal

    def link_result(self) -> StaticLinkResult:
        if self._link is None:
            self._link = link_static_budget(self.project)
        return self._link

    @property
    def timeline(self) -> TimeDomainResult | None:
        """The timeline result this explainer was given or has solved (None before either)."""
        return self._timeline

    @property
    def timeline_ready(self) -> bool:
        """The timeline is solved with the solver's detail (explaining a cell is then quick)."""
        return self._timeline is not None and self._timeline.detail is not None

    def timeline_result(self) -> TimeDomainResult:
        """The power timeline with the solver's detail kept: solved here, or solved again from the
        caller's result (the same inputs give the same numbers)."""
        current = self._timeline
        if current is not None and current.detail is not None:
            return current
        try:
            if current is not None:
                run = current.run
                basis: LoadBasis = "margined" if current.load_basis == "margined" else "nominal"
                phase = current.mission_phase
                cases = tuple(c.case for c in current.cases)
            else:
                ids = sorted(self.project.scenarios)
                chosen = self._scenario or (ids[0] if len(ids) == 1 else None)
                if chosen is None:
                    raise ExplainError(
                        "The project has several scenarios; say which one to explain."
                        if ids
                        else "The project has no scenario."
                    )
                run = run_scenario(self.project, chosen)
                basis, phase, cases = self._load_basis, self._mission_phase, ("bol", "eol")
            self._timeline = time_domain_budget(
                self.project,
                run,
                load_basis=basis,
                cases=cases,
                mission_phase=phase,
                keep_detail=True,
            )
        except ScenarioRunError as exc:
            raise ExplainError(exc.problem.message) from exc
        return self._timeline

    def link_series_result(self) -> LinkSeriesResult:
        """The pass series of the scenario: the caller's, or worked out here."""
        if self._link_series is None:
            try:
                ids = sorted(self.project.scenarios)
                chosen = self._scenario or (ids[0] if len(ids) == 1 else None)
                if chosen is None:
                    raise ExplainError(
                        "The project has several scenarios; say which one to explain."
                        if ids
                        else "The project has no scenario."
                    )
                self._link_series = link_pass_series(
                    self.project, run_scenario(self.project, chosen)
                )
            except ScenarioRunError as exc:
                raise ExplainError(exc.problem.message) from exc
        return self._link_series

    def table(self, table_id: str) -> Table:
        """The report table named `table_id`, built as the reports build it: its column headers and
        the values of its key columns are what a cell is addressed by."""
        family = self._family(table_id)
        bare = Provenance(
            "", "", "", (), self.project.meta.name, self.project.meta.revision, "", "", ""
        )
        if family == "power":
            document = build_power_report(self.project, self.power_result(), bare)
        elif family == "mass":
            document = build_mass_report(self.project, self.mass_result(), bare)
        elif family == "thermal":
            document = build_thermal_report(self.project, self.thermal_result(), bare)
        elif family == "link":
            document = build_link_report(self.project, self.link_result(), bare, plots=False)
        elif family == "linkpass":
            document = build_link_report(
                self.project,
                self.link_result(),
                bare,
                passes=self.link_series_result(),
                plots=False,
            )
        else:
            document = build_timeline_report(
                self.project, self.timeline_result(), bare, plots=False
            )
        for section in document.sections:
            for table in section.tables:
                if table.explain_id == table_id:
                    return table
        raise ExplainError("There is no such table.")

    def explain(self, table_id: str, key: Sequence[str], column: str) -> Explanation:
        """Explain the cell at row `key` (the values of the table's key columns) and `column`
        (the header text) of the table `table_id`."""
        family = self._family(table_id)
        if family == "power":
            return explain_power(self.project, table_id, key, column, self.power_result())
        if family == "mass":
            return explain_mass(self.project, table_id, key, column, self.mass_result())
        if family == "thermal":
            return explain_thermal(self.project, table_id, key, column, self.thermal_result())
        if family == "link":
            return explain_link(self.project, table_id, key, column, self.link_result())
        if family == "linkpass":
            return explain_linkpass(self.project, table_id, key, column, self.link_series_result())
        return explain_timeline(
            self.project, table_id, key, column, self.timeline_result(), self.power_result()
        )


def explain_cell(project: Project, table_id: str, key: Sequence[str], column: str) -> Explanation:
    return Explainer(project).explain(table_id, key, column)
