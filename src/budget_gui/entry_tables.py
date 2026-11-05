"""File menu actions for the spreadsheet tables of the project: the Eb/N0 table, the attenuation
table and the margin policy (decisions D-231, D-249).

Export writes the table as a .csv or .xlsx to fill in outside the tool; an import is read and
planned first, every change is shown (old and new value) and nothing is written until the person
says yes, when the table has a problem, or while files of the project have unsaved edits. The
rules are those of `budget tables-import`: an empty cell is unchanged, a number needs its source in
the same row, nothing is deleted, the comments of the file are kept.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from budget_core.io.entry_tables import (
    TABLES,
    EntryChange,
    EntryPlan,
    apply_entry_plan,
    plan_entry_import,
    read_entry_table,
    table_csv,
    table_xlsx,
)
from budget_core.reports.files import OutputError, write_file

if TYPE_CHECKING:
    from budget_gui.main_window import MainWindow

TITLE = "System Budget Studio"
PREVIEW_LINES = 20
# the names the menu shows, in the order of the menu
TABLE_TITLES: dict[str, str] = {
    "ebn0": "Eb/N0 table",
    "attenuation": "Attenuation table",
    "margins": "Margin policy",
    "links": "Links",
}
assert set(TABLE_TITLES) == set(TABLES)


def _shown(value: str | float | None) -> str:
    if value is None:
        return "(new)"
    return f"{value:g}" if isinstance(value, float) else str(value)


def _change_line(change: EntryChange) -> str:
    return f"{change.key}: {change.field} {_shown(change.old)} -> {_shown(change.new)}"


def preview_text(plan: EntryPlan, name: str) -> str:
    lines = [_change_line(c) for c in plan.changes[:PREVIEW_LINES]]
    if len(plan.changes) > PREVIEW_LINES:
        lines.append(f"... and {len(plan.changes) - PREVIEW_LINES} more")
    rows = {c.key for c in plan.changes}
    head = (
        f"{len(plan.changes)} value(s) in {len(rows)} row(s) of the "
        f"{TABLE_TITLES[name].lower()} would change:"
    )
    file = TABLES[name].file
    return head + "\n\n" + "\n".join(lines) + f"\n\nWrite these changes into {file}?"


def export_entry_table(window: MainWindow, name: str) -> None:
    project = window.session.project
    if project is None:
        QMessageBox.information(window, TITLE, "Open a project without errors first.")
        return
    chosen, _ = QFileDialog.getSaveFileName(
        window,
        f"Export the {TABLE_TITLES[name].lower()}",
        f"{name}_table.csv",
        "Tables (*.csv *.xlsx)",
    )
    if not chosen:
        return
    path = Path(chosen)
    if path.suffix.lower() not in (".csv", ".xlsx"):
        QMessageBox.warning(window, TITLE, "The file name must end in .csv or .xlsx.")
        return
    data = (
        b"\xef\xbb\xbf" + table_csv(project, name).encode("utf-8")
        if path.suffix.lower() == ".csv"
        else table_xlsx(project, name)
    )
    try:
        written = write_file(path.parent, path.name, data, sanitise=False)
    except OutputError as exc:
        QMessageBox.warning(window, TITLE, str(exc))
        return
    window.toast.show_message(f"Wrote {written.name}")


def import_entry_table(window: MainWindow, name: str) -> None:
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
    chosen, _ = QFileDialog.getOpenFileName(
        window, f"Import the {TABLE_TITLES[name].lower()}", "", "Tables (*.csv *.xlsx)"
    )
    if not chosen:
        return
    path = Path(chosen)
    plan = plan_entry_import(project, name, read_entry_table(path, name), path.name)
    if not plan.ok:
        text = "\n".join(p.format() for p in plan.problems)
        QMessageBox.warning(
            window, TITLE, f"The table cannot be imported; nothing was changed.\n\n{text}"
        )
        return
    if not plan.changes:
        QMessageBox.information(
            window, TITLE, f"No change: {plan.unchanged} row(s) already as in the table."
        )
        return
    answer = QMessageBox.question(
        window,
        TITLE,
        preview_text(plan, name),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    try:
        apply_entry_plan(root, name, plan)
    except OutputError as exc:
        QMessageBox.warning(window, TITLE, str(exc))
        return
    window.reload_project()
    window.toast.show_message(f"Updated {TABLES[name].file}")
