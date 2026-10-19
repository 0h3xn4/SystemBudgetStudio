"""The Provenance dock: where the numbers on screen come from (tool, versions, project, time).

Every report and export carries the same rows, so the file can be traced to the run that made it.
The dock shows the provenance of the budgets that were worked out when the project was loaded.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.provenance import Provenance
from budget_gui import theme


class ProvenancePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setProperty("role", "muted")
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Item", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True)
        self.table.setAccessibleName("Provenance")
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)  # a value wraps, it is not cut
        self.table.horizontalHeader().sectionResized.connect(self._fit_rows)
        self.table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(2, 1))
        layout.addWidget(self.note)
        layout.addWidget(self.table, 1)
        self.set_provenance(None)

    def _fit_rows(self, *_args: object) -> None:
        """A narrow panel wraps the values onto more lines: the rows follow the width."""
        self.table.resizeRowsToContents()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._fit_rows()

    def set_provenance(self, provenance: Provenance | None) -> None:
        rows = provenance.rows() if provenance else []
        self.table.setRowCount(len(rows))
        for row, (name, value) in enumerate(rows):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)
            cell = QTableWidgetItem(value)
            cell.setFont(theme.mono_font())
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, cell)
        self.table.resizeRowsToContents()
        self.table.setVisible(bool(rows))
        self.note.setText(
            "Every report and export carries these rows, so a file can be traced to its run."
            if rows
            else "No budget is shown: open a project that loads without errors."
        )
