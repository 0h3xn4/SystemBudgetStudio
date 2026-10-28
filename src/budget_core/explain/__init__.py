"""Explain: how one displayed number was obtained (D-206). Used by `budget explain` and the
window's Explain view; see docs/models/explain.md."""

from __future__ import annotations

from collections.abc import Sequence

from budget_core.explain.mass import explain_mass, mass_table_ids
from budget_core.explain.power import ExplainError, explain_power, power_table_ids
from budget_core.explain.thermal import explain_thermal, thermal_table_ids
from budget_core.explain.trace import Explanation, Quantity, Step
from budget_core.mass.static_mass import StaticMassResult, static_mass_budget
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult, static_power_budget
from budget_core.provenance import Provenance
from budget_core.reports.document import Table
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.power_report import build_power_report
from budget_core.reports.thermal_report import build_thermal_report
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
    return [*power_table_ids(project), *mass_table_ids(project), *thermal_table_ids(project)]


class Explainer:
    """Explains the cells of one project. It computes each budget once and keeps it, so that
    explaining many cells (a test, a window that explains as the cursor moves) stays cheap."""

    def __init__(
        self,
        project: Project,
        power: StaticPowerResult | None = None,
        mass: StaticMassResult | None = None,
        thermal: StaticThermalResult | None = None,
    ) -> None:
        """`power`, `mass` and `thermal` are the static budgets of `project` when the caller has
        them."""
        self.project = project
        self._power = power
        self._mass = mass
        self._thermal = thermal

    def _family(self, table_id: str) -> str:
        family = table_id.split(":", 1)[0]
        if family not in ("power", "mass", "thermal"):
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
        else:
            document = build_thermal_report(self.project, self.thermal_result(), bare)
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
        return explain_thermal(self.project, table_id, key, column, self.thermal_result())


def explain_cell(project: Project, table_id: str, key: Sequence[str], column: str) -> Explanation:
    return Explainer(project).explain(table_id, key, column)
