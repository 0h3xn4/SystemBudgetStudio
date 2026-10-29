"""The Assumptions page of the Model area: everything that is active for the project (D-218).

One read-only list built by `budget_core.assumptions_view`: the sourced numbers with their status,
the settings, tolerances and constants of the catalogue, the model choices, and the defaults the
forms write. It shows the project as it was last loaded or saved (a run reads the saved files too).
A row that names a file opens it.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from budget_core.assumptions_view import (
    CHOICES,
    CONFIGURATION,
    CREATION,
    SETTINGS,
    Row,
    assumptions,
)
from budget_core.model import Project
from budget_gui import theme
from budget_gui.components import EmptyState, SegmentedControl

COLUMNS = ("Name", "Value", "Unit", "Status", "Source or reason", "Where")
ALL = "all"
_FILTERS = (
    (ALL, "All"),
    (CONFIGURATION, "Numbers"),
    (SETTINGS, "Settings"),
    (CHOICES, "Choices"),
    (CREATION, "Forms"),
)
_ROW_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_SECTION_ROLE = int(Qt.ItemDataRole.UserRole) + 2


class AssumptionsModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[Row] = []

    def set_rows(self, rows: list[Row]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, row: int) -> Row:
        return self._rows[row]

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        text = (row.name, row.value, row.unit, row.status, row.source, row.where)[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return text
        if role == Qt.ItemDataRole.ToolTipRole:
            return text or None
        if role == Qt.ItemDataRole.FontRole and index.column() in (1, 2, 5):
            return theme.mono_font()  # numbers, units and paths are in the monospace face
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 1:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == _ROW_ROLE:
            return row
        if role == _SECTION_ROLE:
            return row.section
        return None


class _Proxy(QSortFilterProxyModel):
    """Rows of one section that contain every word typed in the filter."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.section = ALL
        self.words: list[str] = []

    def set_section(self, section: str) -> None:
        self.beginFilterChange()
        self.section = section
        self.endFilterChange()

    def set_text(self, text: str) -> None:
        self.beginFilterChange()
        self.words = text.lower().split()
        self.endFilterChange()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        assert isinstance(model, AssumptionsModel)
        row = model.row_at(source_row)
        if self.section != ALL and row.section != self.section:
            return False
        haystack = " ".join((row.name, row.value, row.unit, row.status, row.source, row.where))
        haystack = haystack.lower()
        return all(word in haystack for word in self.words)


class AssumptionsPage(QWidget):
    open_requested = Signal(str, str)  # the file a row names and the field in it

    def __init__(self) -> None:
        super().__init__()
        self.model = AssumptionsModel(self)
        self.proxy = _Proxy(self)
        self.proxy.setSourceModel(self.model)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter (name, value, status, source…)")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setAccessibleName("Filter the assumptions")
        self.sections = SegmentedControl(list(_FILTERS), current=ALL)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "muted")
        self.note = QLabel(
            "Everything that is active for this project, as last loaded or saved. Settings, "
            "tolerances and constants are fixed in this version; double-click a row that names "
            "a file to open it."
        )
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAccessibleName("Assumptions")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(theme.px(theme.ROW_HEIGHT))
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)
        for column, width in enumerate(theme.ASSUMPTIONS_WIDTHS):
            self.table.setColumnWidth(column, theme.px(width))
        self.table.setTabKeyNavigation(False)  # Tab leaves a read-only table
        self.empty = EmptyState(
            "Open a project to see everything that is active for it: its sourced numbers, the "
            "settings and constants the tool applies, and the model choices.",
            icon="info",
        )

        top = QHBoxLayout()
        top.setSpacing(theme.gap(1))
        top.addWidget(self.filter_edit, 1)
        top.addWidget(self.sections)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(2, 1))
        layout.setSpacing(theme.gap(1))
        layout.addWidget(self.note)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty, 1)
        layout.addWidget(self.count_label)

        self.filter_edit.textChanged.connect(self._filter_changed)
        self.sections.changed.connect(self._section_changed)
        self.table.doubleClicked.connect(self._open_row)
        self.table.activated.connect(self._open_row)
        self.set_project(None)

    # ---- content -----------------------------------------------------------------------------
    def set_project(self, project: Project | None) -> None:
        rows = assumptions(project) if project is not None else []
        self.model.set_rows(rows)
        shown = bool(rows)
        self.table.setVisible(shown)
        self.empty.setVisible(not shown)
        self.filter_edit.setEnabled(shown)
        self.sections.setEnabled(shown)
        self._update_count()

    def _filter_changed(self, text: str) -> None:
        self.proxy.set_text(text)
        self._update_count()

    def _section_changed(self, key: str) -> None:
        self.proxy.set_section(key)
        self._update_count()

    def _update_count(self) -> None:
        total, shown = self.model.rowCount(), self.proxy.rowCount()
        self.count_label.setText(f"{shown} of {total} rows" if total else "")

    def visible_rows(self) -> list[Row]:
        return [
            self.model.row_at(self.proxy.mapToSource(self.proxy.index(i, 0)).row())
            for i in range(self.proxy.rowCount())
        ]

    # ---- opening the file a row names --------------------------------------------------------
    def _open_row(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        row = self.model.row_at(self.proxy.mapToSource(index).row())
        rel, path = file_of(row)
        if rel:
            self.open_requested.emit(rel, path)


def file_of(row: Row) -> tuple[str, str]:
    """The project file a row points to and the field in it (its `where` is `file field`), or
    two empty texts."""
    first, _, path = row.where.partition(" ")
    return (first, path) if first.endswith(".yaml") else ("", "")
