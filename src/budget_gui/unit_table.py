"""File menu actions for the unit power table: export a template, import a filled-in one.

An import is shown before it is applied (every changed value, old and new), and nothing is
written when the table has a problem or when files of the project have unsaved edits.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from budget_core.io.unit_table import (
    ImportPlan,
    apply_plan,
    plan_import,
    read_table,
    table_csv,
    table_xlsx,
)
from budget_core.reports.files import OutputError, write_file

if TYPE_CHECKING:
    from budget_gui.main_window import MainWindow

TITLE = "System Budget Studio"
PREVIEW_LINES = 20


def _number(value: float | None) -> str:
    return "(new)" if value is None else f"{value:g}"


def preview_text(plan: ImportPlan) -> str:
    lines = [
        f"{c.unit_id} / {c.power_mode}: {c.field} {_number(c.old)} -> {c.new:g}"
        for c in plan.changes[:PREVIEW_LINES]
    ]
    if len(plan.changes) > PREVIEW_LINES:
        lines.append(f"... and {len(plan.changes) - PREVIEW_LINES} more")
    modes = {(c.unit_id, c.power_mode) for c in plan.changes}
    head = f"{len(plan.changes)} value(s) in {len(modes)} power mode(s) would change:"
    return head + "\n\n" + "\n".join(lines) + "\n\nWrite these changes into the unit files?"


def export_unit_table(window: MainWindow) -> None:
    project = window.session.project
    if project is None:
        QMessageBox.information(window, TITLE, "Open a project without errors first.")
        return
    name, _ = QFileDialog.getSaveFileName(
        window, "Export unit table", "unit_power_modes.csv", "Tables (*.csv *.xlsx)"
    )
    if not name:
        return
    path = Path(name)
    if path.suffix.lower() not in (".csv", ".xlsx"):
        QMessageBox.warning(window, TITLE, "The file name must end in .csv or .xlsx.")
        return
    data = (
        b"\xef\xbb\xbf" + table_csv(project).encode("utf-8")
        if path.suffix.lower() == ".csv"
        else table_xlsx(project)
    )
    try:
        write_file(path.parent, path.name, data, sanitise=False)
    except OutputError as exc:
        QMessageBox.warning(window, TITLE, str(exc))


def import_unit_table(window: MainWindow) -> None:
    project = window.session.project
    root = window.session.path
    if project is None or root is None:
        QMessageBox.information(window, TITLE, "Open a project without errors first.")
        return
    if window.editors.has_unsaved_changes():
        QMessageBox.information(
            window,
            TITLE,
            "Some files have unsaved changes. Save or discard them first, then import.",
        )
        return
    name, _ = QFileDialog.getOpenFileName(window, "Import unit table", "", "Tables (*.csv *.xlsx)")
    if not name:
        return
    path = Path(name)
    plan = plan_import(project, read_table(path), path.name)
    if not plan.ok:
        text = "\n".join(p.format() for p in plan.problems)
        QMessageBox.warning(
            window, TITLE, f"The table cannot be imported; nothing was changed.\n\n{text}"
        )
        return
    if not plan.changes:
        QMessageBox.information(
            window, TITLE, f"No change: {plan.unchanged} power mode(s) already as in the table."
        )
        return
    answer = QMessageBox.question(
        window,
        TITLE,
        preview_text(plan),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    try:
        apply_plan(root, plan)
    except OutputError as exc:
        QMessageBox.warning(window, TITLE, str(exc))
        return
    window.reload_project()
