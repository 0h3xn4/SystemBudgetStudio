"""Project tree and the budget view (the Problems panel is in `problems_panel`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QMenu,
    QScrollArea,
    QTableView,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.model import Project
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


class ProjectTree(QTreeWidget):
    """Files of the project folder, grouped like the project layout."""

    file_requested = Signal(str)
    unit_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self.itemDoubleClicked.connect(self._activated)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _activated(self, item: QTreeWidgetItem, _column: int) -> None:
        rel = item.data(0, Qt.ItemDataRole.UserRole)
        if rel:
            self.file_requested.emit(str(rel))

    def current_unit_id(self) -> str | None:
        item = self.currentItem()
        unit = item.data(0, UNIT_ROLE) if item else None
        return str(unit) if unit else None

    def _context_menu(self, pos: Any) -> None:
        item = self.itemAt(pos)
        unit = item.data(0, UNIT_ROLE) if item else None
        if not unit:
            return
        menu = QMenu(self)
        action = menu.addAction("Edit power modes…")
        if menu.exec(self.viewport().mapToGlobal(pos)) is action:
            self.unit_requested.emit(str(unit))

    def request_file(self, rel: str) -> None:
        self.file_requested.emit(rel)

    def file_item_count(self) -> int:
        count = 0
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                count += 1 if child.data(0, Qt.ItemDataRole.UserRole) else 0
                stack.append(child)
        return count

    def current_file(self) -> str | None:
        item = self.currentItem()
        rel = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        return str(rel) if rel else None

    def set_project(self, root: Path | None, project: Project | None) -> None:
        selected = self.current_file()
        self.clear()
        if root is None:
            return
        top = QTreeWidgetItem([project.meta.name if project else root.name])
        self.addTopLevelItem(top)

        def add(parent: QTreeWidgetItem, label: str, rel: str, unit_id: str | None = None) -> None:
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, rel)
            if unit_id:
                item.setData(0, UNIT_ROLE, unit_id)
            parent.addChild(item)

        for name in ("project.yaml", "spacecraft.yaml"):
            if (root / name).is_file():
                add(top, name, name)
        for folder, title in (
            ("units", "Units"),
            ("expendables", "Expendables"),
            ("modes", "Spacecraft modes"),
            ("orbits", "Orbits"),
            ("ground_stations", "Ground stations"),
            ("targets", "Imaging targets"),
            ("links", "Links"),
            ("scenarios", "Scenarios"),
            ("config", "Configuration"),
        ):
            files = sorted((root / folder).glob("*.yaml")) if (root / folder).is_dir() else []
            if not files:
                continue
            group = QTreeWidgetItem([f"{title} ({len(files)})"])
            top.addChild(group)
            for path in files:
                label = path.stem
                if project and folder == "units" and path.stem in project.units:
                    label = f"{path.stem}: {project.units[path.stem].name}"
                add(
                    group,
                    label,
                    f"{folder}/{path.name}",
                    path.stem
                    if folder == "units" and project and path.stem in project.units
                    else None,
                )
            group.setExpanded(folder != "config")
        top.setExpanded(True)
        if selected is not None:  # keep the selection across a reload
            stack = [top]
            while stack:
                node = stack.pop()
                for i in range(node.childCount()):
                    child = node.child(i)
                    if child.data(0, Qt.ItemDataRole.UserRole) == selected:
                        self.setCurrentItem(child)
                        return
                    stack.append(child)


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
