"""The budget view and its table model (the tree and the Problems panel have their own modules)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QShowEvent
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
from budget_core.reports.document import NA, ReportDocument, Section, Table, format_cell
from budget_gui.delegates import (
    NUMERIC_ROLE,
    STATE_ROLE,
    TOTAL_ROLE,
    CellDelegate,
    tooltip_for,
)
from budget_gui.theme import Status

SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
Index = QModelIndex | QPersistentModelIndex
_NO_PARENT = QModelIndex()
UNIT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
COLUMN_WIDTH_ROWS = 60  # rows looked at to size a column


EMPTY_TEXT = "No budget to show. Open a project without errors."
HEADER_LINE = 14  # a header longer than this is broken into two lines at a space


def wrap_header(text: str) -> str:
    """A long column header on two lines, broken at the space nearest the middle, so a table of
    many columns fits the window (the report keeps the one-line header)."""
    if len(text) <= HEADER_LINE:
        return text
    spaces = [i for i, c in enumerate(text) if c == " "]
    if not spaces:
        return text
    cut = min(spaces, key=lambda i: abs(i - len(text) / 2))
    return text[:cut] + "\n" + text[cut + 1 :]


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
        if orientation == Qt.Orientation.Horizontal:
            header = self.table.columns[section].header
            if role == Qt.ItemDataRole.DisplayRole:
                return wrap_header(header)
            if role == Qt.ItemDataRole.ToolTipRole:
                return header
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
        if role == TOTAL_ROLE:
            return self.table.emphasise_last_row and index.row() == len(self.table.rows) - 1
        if role == Qt.ItemDataRole.ToolTipRole and text == NA:
            return tooltip_for(Status.NOT_CHECKED)
        return None


class _SectionPage(QScrollArea):
    """One sheet of a budget. Its tables are made the first time the page is shown: a project with
    200 units has tables of 200 rows in every sheet, and making all of them when the project loads
    (most are never looked at) kept the window busy for a second."""

    def __init__(self, section: Section) -> None:
        super().__init__()
        self.section = section
        self.models: list[DocTableModel] = []
        self._built = False
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.ensure_built()

    def ensure_built(self) -> None:
        if self._built:
            return
        self._built = True
        page = QWidget()
        layout = QVBoxLayout(page)
        for text in self.section.paragraphs:
            layout.addWidget(QLabel(text))
        for table in self.section.tables:
            title = QLabel(table.title)
            title.setProperty("role", "section-title")
            layout.addWidget(title)
            model = DocTableModel(table)
            self.models.append(model)
            view = QTableView()
            view.setModel(model)
            view.setItemDelegate(CellDelegate(view))
            view.verticalHeader().setVisible(False)
            view.setAlternatingRowColors(True)
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            view.setTabKeyNavigation(False)  # Tab leaves a read-only table (it is not a form)
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
        self.setWidget(page)


class PowerView(QWidget):
    """Tabs with the same tables the reports contain (Summary, one tab per mode, Assumptions)."""

    def __init__(self) -> None:
        super().__init__()
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setProperty("role", "banner")
        self.empty_label = QLabel(EMPTY_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.banner)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.tabs)
        self._pages: dict[str, _SectionPage] = {}
        self.set_document(None)

    def set_empty_text(self, text: str | None) -> None:
        """Say why there is nothing to show (None: the usual sentence)."""
        self.empty_label.setText(text or EMPTY_TEXT)

    def count(self) -> int:
        return self.tabs.count()

    def tabText(self, index: int) -> str:  # noqa: N802 (Qt naming)
        return self.tabs.tabText(index)

    def build_pages(self) -> None:
        """Make the tables of every sheet now (they are made when a sheet is first shown)."""
        for page in self._pages.values():
            page.ensure_built()

    def table_model(self, tab: str, index: int) -> DocTableModel:
        page = self._pages[tab]
        page.ensure_built()
        return page.models[index]

    def set_document(self, document: ReportDocument | None) -> None:
        self.tabs.setVisible(False)  # a hidden tab bar does not build the pages it uncovers
        while self.tabs.count():  # QTabWidget.clear() keeps the pages alive: delete them
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            page.setParent(None)
            page.deleteLater()
        self._pages = {}
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
            page = _SectionPage(section)
            self.tabs.addTab(page, section.sheet_name)
            self._pages[section.sheet_name] = page
