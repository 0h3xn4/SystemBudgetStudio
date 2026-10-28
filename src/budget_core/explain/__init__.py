"""Explain: how one displayed number was obtained (D-206). Used by `budget explain` and the
window's Explain view; see docs/models/explain.md."""

from __future__ import annotations

from collections.abc import Sequence

from budget_core.explain.power import ExplainError, explain_power, power_table_ids
from budget_core.explain.trace import Explanation, Quantity, Step
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult, static_power_budget
from budget_core.provenance import Provenance
from budget_core.reports.document import Table
from budget_core.reports.power_report import build_power_report

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
    return [*power_table_ids(project)]


class Explainer:
    """Explains the cells of one project. It computes each budget once and keeps it, so that
    explaining many cells (a test, a window that explains as the cursor moves) stays cheap."""

    def __init__(self, project: Project) -> None:
        self.project = project
        self._power: StaticPowerResult | None = None

    def _family(self, table_id: str) -> str:
        family = table_id.split(":", 1)[0]
        if family != "power":
            raise ExplainError("This table cannot be explained.")
        return family

    def power_result(self) -> StaticPowerResult:
        if self._power is None:
            self._power = static_power_budget(self.project)
        return self._power

    def table(self, table_id: str) -> Table:
        """The report table named `table_id`, built as the reports build it: its column headers and
        the values of its key columns are what a cell is addressed by."""
        self._family(table_id)
        bare = Provenance(
            "", "", "", (), self.project.meta.name, self.project.meta.revision, "", "", ""
        )
        document = build_power_report(self.project, self.power_result(), bare)
        for section in document.sections:
            for table in section.tables:
                if table.explain_id == table_id:
                    return table
        raise ExplainError("There is no such table.")

    def explain(self, table_id: str, key: Sequence[str], column: str) -> Explanation:
        """Explain the cell at row `key` (the values of the table's key columns) and `column`
        (the header text) of the table `table_id`."""
        self._family(table_id)
        return explain_power(self.project, table_id, key, column, self.power_result())


def explain_cell(project: Project, table_id: str, key: Sequence[str], column: str) -> Explanation:
    return Explainer(project).explain(table_id, key, column)
