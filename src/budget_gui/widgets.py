"""The budget view and its table model (the tree and the Problems panel have their own modules)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QScrollArea,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from budget_core.problems import Severity
from budget_core.reports.document import NA, ReportDocument, Table, format_cell
from budget_gui.delegates import NUMERIC_ROLE, STATE_ROLE, CellDelegate, tooltip_for
from budget_gui.theme import Status

SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
Index = QModelIndex | QPersistentModelIndex
_NO_PARENT = QModelIndex()
UNIT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
COLUMN_WIDTH_ROWS = 60  # rows looked at to size a column


class DocTableModel(QAbstractTableModel):
    """Read-only model over a report `Table`, so the screen shows exactly what reports contain."""

    def __init__(self, table: Table) -> None:
        super().__init__()
        self.table = table
        self._text: dict[tuple[int, int], str] = {}  # formatted cells, made when first asked for

    def rowCount(self, parent: Index = _NO_PARENT) -> int:
        return 0 if parent.isValid() else len(self.table.rows)

    def columnCount(self, parent: Index = _NO_PARENT) -> int:
        return 0 if parent.isValid() else len(self.table.columns)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.table.columns[section].header
        return None

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        column = self.table.columns[index.column()]
        value = self.table.rows[index.row()][index.column()]
        key = (index.row(), index.column())
        text = self._text.get(key)
        if text is None:  # Qt asks for each cell several times (text, alignment, colour)
            text = self._text[key] = format_cell(value, column)
        if role == Qt.ItemDataRole.DisplayRole:
            return text
        if role == Qt.ItemDataRole.TextAlignmentRole:
            numeric = column.kind != "text" or value is None
            horizontal = Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft
            return int(horizontal | Qt.AlignmentFlag.AlignVCenter)
        if role == STATE_ROLE:
            return Status.NOT_CHECKED.value if text == NA else None
        if role == NUMERIC_ROLE:
            return column.kind != "text" or value is None
        if role == Qt.ItemDataRole.ToolTipRole and text == NA:
            return tooltip_for(Status.NOT_CHECKED)
        return None


class PowerView(QWidget):
    """Tabs with the same tables the reports contain (Summary, one tab per mode, Assumptions)."""

    def __init__(self) -> None:
        super().__init__()
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setProperty("role", "banner")
        self.empty_label = QLabel("No budget to show. Open a project without errors.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.banner)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.tabs)
        self._models: dict[str, list[DocTableModel]] = {}
        self.set_document(None)

    def count(self) -> int:
        return self.tabs.count()

    def tabText(self, index: int) -> str:  # noqa: N802 (Qt naming)
        return self.tabs.tabText(index)

    def table_model(self, tab: str, index: int) -> DocTableModel:
        return self._models[tab][index]

    def set_document(self, document: ReportDocument | None) -> None:
        while self.tabs.count():  # QTabWidget.clear() keeps the pages alive: delete them
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            page.setParent(None)
            page.deleteLater()
        self._models = {}
        shown = document is not None
        self.empty_label.setVisible(not shown)
        self.tabs.setVisible(shown)
        self.banner.setVisible(bool(document and document.banner))
        self.banner.setText(document.banner if document else "")
        if document is None:
            return
        for section in document.sections:
            if section.sheet_name == "Problems":  # shown in the Problems panel instead
                continue
            page = QWidget()
            layout = QVBoxLayout(page)
            models: list[DocTableModel] = []
            for text in section.paragraphs:
                layout.addWidget(QLabel(text))
            for table in section.tables:
                title = QLabel(table.title)
                title.setProperty("role", "section-title")
                layout.addWidget(title)
                model = DocTableModel(table)
                models.append(model)
                view = QTableView()
                view.setModel(model)
                view.setItemDelegate(CellDelegate(view))
                view.verticalHeader().setVisible(False)
                view.setAlternatingRowColors(True)
                view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                # the widths come from the first rows only: a table of thousands of rows would
                # otherwise be measured cell by cell every time the project is loaded
                view.horizontalHeader().setResizeContentsPrecision(COLUMN_WIDTH_ROWS)
                view.resizeColumnsToContents()
                view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                height = view.horizontalHeader().height() + 2 * view.frameWidth() + 18
                height += sum(view.rowHeight(r) for r in range(len(table.rows)))
                view.setFixedHeight(max(height, 60))
                layout.addWidget(view)
                if table.note:
                    note = QLabel(table.note)
                    note.setWordWrap(True)
                    layout.addWidget(note)
            layout.addStretch(1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self.tabs.addTab(
                scroll, section.sheet_name if section.sheet_name != "Summary" else "Summary"
            )
            self._models[section.sheet_name] = models
