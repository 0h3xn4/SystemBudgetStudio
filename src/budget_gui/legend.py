"""The legend of the cell styles: placeholder, `n/a`, limit states and margin bars.

It is drawn with the same delegate as the tables, so it can never disagree with them (D-150). A
table's *Legend* button opens it.
"""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from budget_gui import theme
from budget_gui.components import Button
from budget_gui.delegates import (
    MARGIN_ROLE,
    NUMERIC_ROLE,
    STATE_ROLE,
    CellDelegate,
)
from budget_gui.theme import Status


class LegendRow(NamedTuple):
    name: str
    example: str
    status: Status | None
    numeric: bool
    share: float | None  # share of the limit used, for the margin bar
    meaning: str


ROWS = (
    LegendRow(
        "Number", "1.250", None, True, None,
        "A value. Right-aligned, fixed decimals; the unit is in the column header.",
    ),
    LegendRow(
        "Within the limit", "0.250", Status.PASS, True, 0.35,
        "The margin is positive. The bar shows how much of the limit is used.",
    ),
    LegendRow(
        "Near the limit", "0.020", Status.NEAR, True, 0.88,
        "Inside the required margin, but not broken.",
    ),
    LegendRow(
        "Limit broken", "-0.320", Status.FAIL, True, 1.2,
        "The limit is broken. Always an icon and bold text, never colour alone.",
    ),
    LegendRow(
        "Not checked (n/a)", "n/a", Status.NOT_CHECKED, False, None,
        "The result needs an input that is a placeholder or missing, so it is not computed. "
        "Different from 0 and from an empty cell.",
    ),
    LegendRow(
        "Placeholder", "12.0", Status.PLACEHOLDER, True, None,
        "An input without a source (source TBD): italic with a dashed border. "
        "Results that depend on it show n/a.",
    ),
    LegendRow("Empty", "", None, False, None, "Nothing is here: no value is needed."),
)  # fmt: skip


class CellStyleLegend(QTableView):
    """A small read-only table: style, example, meaning."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        model = QStandardItemModel(len(ROWS), 3, self)
        model.setHorizontalHeaderLabels(["Style", "Example", "Meaning"])
        for row, entry in enumerate(ROWS):
            name_item = QStandardItem(entry.name)
            sample = QStandardItem(entry.example)
            sample.setData(entry.status.value if entry.status else None, STATE_ROLE)
            sample.setData(entry.numeric, NUMERIC_ROLE)
            sample.setData(entry.share, MARGIN_ROLE)
            note = QStandardItem(entry.meaning)
            for item in (name_item, sample, note):
                item.setEditable(False)
            model.setItem(row, 0, name_item)
            model.setItem(row, 1, sample)
            model.setItem(row, 2, note)
        self.setModel(model)
        self.setItemDelegateForColumn(1, CellDelegate(self))
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # a legend: Close is what the keyboard reaches
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(True)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._fit_rows()

    def _fit_rows(self) -> None:
        """A row is as high as its wrapped meaning (and at least a control)."""
        self.resizeRowsToContents()
        for row in range(len(ROWS)):
            self.setRowHeight(row, max(self.rowHeight(row), theme.px(theme.CONTROL_DEFAULT)))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._fit_rows()  # the meaning wraps at the width the table has now


class LegendDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cell styles")
        self.setMinimumSize(*theme.scaled(theme.LEGEND_MIN))
        intro = QLabel(
            "Every table uses the same styles. A style always has an icon or text "
            "as well as a colour."
        )
        intro.setProperty("role", "muted")
        intro.setWordWrap(True)
        self.legend = CellStyleLegend()
        close = Button("Close", "primary")  # the one action of a dialog that only informs
        close.setDefault(True)
        close.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(intro)
        layout.addWidget(self.legend, 1)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
