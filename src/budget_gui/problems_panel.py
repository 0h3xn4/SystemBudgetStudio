"""The Problems panel: every finding of the open project, by class, with a filter and grouping.

Columns: class (icon and word) · message · file · field · code. Double-click or Enter jumps to the
file and line. Errors come first, then warnings, then *not checked* findings (placeholders), then
information. The panel only shows what the core reported; it never adds text read from a file.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QResizeEvent,
    QShowEvent,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QStackedLayout,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from budget_core.problems import Problem
from budget_gui import icons, theme
from budget_gui import problem_class as pc
from budget_gui.problem_class import ProblemClass

PROBLEM_ROLE = int(Qt.ItemDataRole.UserRole) + 10  # index into the list of shown problems
COLUMNS = ("Class", "Problem", "Field", "Code")
CLASS, MESSAGE, FIELD, CODE = 0, 1, 2, 3


class Grouping(StrEnum):
    NONE = "none"
    CLASS = "class"
    FILE = "file"


GROUPING_TEXT = {
    Grouping.NONE: "No grouping",
    Grouping.CLASS: "Group by class",
    Grouping.FILE: "Group by file",
}


def _where(problem: Problem) -> str:
    where = problem.file or "<project>"
    return f"{where}:{problem.line}" if problem.line is not None else where


def _key(problem: Problem) -> tuple[str, str, str, str]:
    return (problem.code, problem.file or "", problem.path, problem.message)


class _WrapDelegate(QStyledItemDelegate):
    """Measures the wrapped text of the problem column from the width the column has now (a tree
    view does not do that by itself)."""

    def __init__(self, view: QTreeView) -> None:
        super().__init__(view)
        self._view = view

    def sizeHint(  # noqa: N802 (Qt naming)
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        size = super().sizeHint(option, index)
        if index.column() != MESSAGE:
            return size
        opt: Any = option
        width = max(self._view.columnWidth(MESSAGE) - 12, 40)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        rect = opt.fontMetrics.boundingRect(
            QRect(0, 0, width, 100000),
            int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft),
            text,
        )
        return QSize(size.width(), max(size.height(), rect.height() + 8))


class _WrapTree(QTreeView):
    """A tree whose rows are measured again when its width changes: wrapped text needs the final
    width of its column, which is only known after the first layout."""

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self.doItemsLayout()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.doItemsLayout()


class ProblemsPanel(QWidget):
    """All problems of the open project; double-click or Enter jumps to the offending line."""

    jump_requested = Signal(str, int)
    changed = Signal()  # the list, the filter or the grouping changed

    def __init__(self) -> None:
        super().__init__()
        self.summary = QLabel("No project open")
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter by message, file, field or code")
        self.filter_box.setClearButtonEnabled(True)
        self.filter_box.setToolTip("Show only the problems that contain this text.")
        self.class_box = QComboBox()
        self.class_box.addItem("All classes", None)
        for cls in pc.ORDER:
            self.class_box.addItem(icons.icon(pc.ICONS[cls]), pc.LABELS[cls], cls.value)
        self.class_box.setToolTip("Show one class of problems only.")
        self.group_box = QComboBox()
        for grouping, text in GROUPING_TEXT.items():
            self.group_box.addItem(text, grouping.value)
        self.group_box.setToolTip("Group the list by class or by file.")

        self.list_model = QStandardItemModel(0, len(COLUMNS))
        self.list_model.setHorizontalHeaderLabels(list(COLUMNS))
        self.view = _WrapTree()
        self.view.setModel(self.list_model)
        self.view.setItemDelegate(_WrapDelegate(self.view))
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setUniformRowHeights(False)
        self.view.setWordWrap(True)
        self.view.setAllColumnsShowFocus(True)
        self.view.setMinimumHeight(theme.px(theme.LIST_MIN_HEIGHT))
        self.view.setTextElideMode(Qt.TextElideMode.ElideNone)  # long messages wrap
        header = self.view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(MESSAGE, QHeaderView.ResizeMode.Stretch)
        for column in (CLASS, FIELD, CODE):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        self.list_model.setHeaderData(
            CLASS,
            Qt.Orientation.Horizontal,
            "Class: error, warning, not checked or info",
            Qt.ItemDataRole.ToolTipRole,
        )
        header.setMinimumSectionSize(theme.px(theme.COLUMN_MIN))
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._header_menu)
        self.set_column_widths([])
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setProperty("role", "muted")
        self._stack_host = QWidget()
        self._stack = QStackedLayout(self._stack_host)
        self._stack.addWidget(self.view)
        self._stack.addWidget(self.empty)

        controls = QHBoxLayout()
        controls.setSpacing(theme.gap(1))
        controls.addWidget(self.summary)
        controls.addWidget(self.filter_box, 1)
        controls.addWidget(self.class_box)
        controls.addWidget(self.group_box)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(1, 0))
        layout.addLayout(controls)
        layout.addWidget(self._stack_host, 1)
        self.setFocusProxy(self.view)

        self._problems: list[Problem] = []  # everything the project reported, in the given order
        self._visible: list[Problem] = []  # what the list shows, in the order it shows it
        self._project_open = False
        self.filter_box.textChanged.connect(lambda _text: self._rebuild())
        self.class_box.currentIndexChanged.connect(lambda _i: self._rebuild())
        self.group_box.currentIndexChanged.connect(lambda _i: self._rebuild())
        self.view.activated.connect(self._activated)
        theme.manager().changed.connect(self._theme_changed)

    # ---- columns (widths and visibility are kept in the layout file) ---------------------------
    DEFAULT_WIDTHS = (56, 0, 180, 170)  # the problem column stretches
    DEFAULT_HIDDEN = ()  # the panel at the bottom is wide: every column is shown

    def column_widths(self) -> list[int]:
        """Width of each column; 0 for a hidden one (the message column is never hidden)."""
        return [
            0 if self.view.isColumnHidden(c) else self.view.columnWidth(c)
            for c in range(len(COLUMNS))
        ]

    def set_column_widths(self, widths: list[int]) -> None:
        """Apply saved widths (0 hides a column); an unusable list gives the defaults."""
        usable = len(widths) == len(COLUMNS) and all(w >= 0 for w in widths)
        for column in range(len(COLUMNS)):
            if column == MESSAGE:
                continue
            if usable:
                hidden, width = widths[column] == 0, widths[column]
            else:
                hidden = column in self.DEFAULT_HIDDEN
                width = theme.px(self.DEFAULT_WIDTHS[column])  # follows the UI size
            self.view.setColumnHidden(column, hidden)
            if not hidden:
                self.view.setColumnWidth(column, max(int(width), theme.px(theme.COLUMN_MIN)))

    def _header_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        for column in (FIELD, CODE):
            action = menu.addAction(COLUMNS[column])
            action.setCheckable(True)
            action.setChecked(not self.view.isColumnHidden(column))
            action.toggled.connect(lambda shown, c=column: self.view.setColumnHidden(c, not shown))
        menu.exec(self.view.header().mapToGlobal(pos))

    # ---- data --------------------------------------------------------------------------------
    def set_problems(self, problems: list[Problem], *, project_open: bool = True) -> None:
        self._problems = list(problems)
        self._project_open = project_open
        self._rebuild()

    @property
    def problems(self) -> list[Problem]:
        """Everything reported, shown or not."""
        return list(self._problems)

    @property
    def visible_problems(self) -> list[Problem]:
        """What the list shows, top to bottom (the filter applied, groups flattened)."""
        return list(self._visible)

    def counts(self) -> dict[ProblemClass, int]:
        return pc.counts(self._problems)

    def codes(self) -> list[str]:
        """The codes of the shown problems, top to bottom."""
        return [p.code for p in self._visible]

    # ---- filter and grouping -----------------------------------------------------------------
    def set_filter_text(self, text: str) -> None:
        self.filter_box.setText(text)

    def set_class_filter(self, cls: ProblemClass | None) -> None:
        """Show one class only (None: all). The status bar uses this for 'not checked'."""
        self.class_box.setCurrentIndex(0 if cls is None else 1 + pc.ORDER.index(cls))

    def class_filter(self) -> ProblemClass | None:
        value = self.class_box.currentData()
        return ProblemClass(value) if value else None

    def set_grouping(self, grouping: Grouping) -> None:
        self.group_box.setCurrentIndex(list(GROUPING_TEXT).index(grouping))

    def grouping(self) -> Grouping:
        return Grouping(self.group_box.currentData())

    def _matches(self, problem: Problem) -> bool:
        wanted = self.class_filter()
        if wanted is not None and pc.classify(problem) is not wanted:
            return False
        text = self.filter_box.text().strip().lower()
        if not text:
            return True
        haystack = " ".join(
            (problem.message, problem.file or "", problem.path, problem.code, problem.hint)
        ).lower()
        return all(word in haystack for word in text.split())

    # ---- view --------------------------------------------------------------------------------
    def _rebuild(self) -> None:
        selected = self.current_problem()
        by_class = pc.counts(self._problems)
        text = pc.summary(by_class) if self._project_open else "No project open"
        shown = [p for p in self._problems if self._matches(p)]
        if self._project_open and len(shown) != len(self._problems):
            text += f" — showing {len(shown)} of {len(self._problems)}"
        self.summary.setText(text)

        grouping = self.grouping()
        indexed = list(enumerate(shown))
        if grouping is Grouping.FILE:
            indexed.sort(key=lambda t: (t[1].file or "", pc.RANK[pc.classify(t[1])], t[0]))
        else:
            indexed.sort(key=lambda t: (pc.RANK[pc.classify(t[1])], t[0]))
        self._visible = [p for _i, p in indexed]

        self.list_model.removeRows(0, self.list_model.rowCount())
        self.view.setRootIsDecorated(grouping is not Grouping.NONE)
        groups: dict[str, QStandardItem] = {}
        for position, problem in enumerate(self._visible):
            parent = self.list_model.invisibleRootItem()
            if grouping is not Grouping.NONE:
                name = (
                    pc.LABELS[pc.classify(problem)]
                    if grouping is Grouping.CLASS
                    else (problem.file or "<project>")
                )
                group = groups.get(name)
                if group is None:
                    group = groups[name] = self._group_item(name, problem, grouping)
                    parent.appendRow(group)
                parent = group
            parent.appendRow(self._row_items(problem, position))
        for name, group in groups.items():
            members = group.rowCount()
            group.setText(f"{name} ({members})")
        self.view.expandAll()

        if not shown:
            if not self._project_open:
                self.empty.setText("Open a project to see its problems.")
            elif not self._problems:
                self.empty.setText("No problems: every input loads and every check could run.")
            else:
                self.empty.setText("No problem matches the filter.")
            self._stack.setCurrentWidget(self.empty)
        else:
            self._stack.setCurrentWidget(self.view)
            self._restore(selected)
        self.changed.emit()

    def _group_item(self, name: str, problem: Problem, grouping: Grouping) -> QStandardItem:
        item = QStandardItem(name)
        item.setEditable(False)
        item.setSelectable(False)
        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)
        if grouping is Grouping.CLASS:
            cls = pc.classify(problem)
            item.setIcon(icons.icon(pc.ICONS[cls], pc.colour(cls)))
        else:
            item.setData(theme.mono_font(), Qt.ItemDataRole.FontRole)
        return item

    def _row_items(self, problem: Problem, position: int) -> list[QStandardItem]:
        cls = pc.classify(problem)
        colour = QBrush(QColor(pc.colour(cls)))
        tip = pc.EXPLANATIONS[cls]
        if problem.hint:
            tip += f"\n{problem.hint}"
        where = _where(problem)
        text = problem.message + (f"  {problem.hint}" if problem.hint else "")
        items = [
            QStandardItem(icons.icon(pc.ICONS[cls], pc.colour(cls)), ""),
            QStandardItem(f"{text}\n{where}"),
            QStandardItem(problem.path),
            QStandardItem(problem.code),
        ]
        items[0].setData(pc.LABELS[cls], Qt.ItemDataRole.AccessibleTextRole)
        items[0].setForeground(colour)
        for column, item in enumerate(items):
            item.setEditable(False)
            item.setToolTip(tip if column == CLASS else problem.format())
            if column in (FIELD, CODE):
                item.setData(theme.mono_font(), Qt.ItemDataRole.FontRole)
        items[0].setData(position, PROBLEM_ROLE)
        return items

    def _theme_changed(self) -> None:
        self._rebuild()

    # ---- selection and jumping ---------------------------------------------------------------
    def current_problem(self) -> Problem | None:
        index = self.view.currentIndex()
        if not index.isValid():
            return None
        first = index.siblingAtColumn(0)
        position = first.data(PROBLEM_ROLE)
        if position is None or not 0 <= int(position) < len(self._visible):
            return None
        return self._visible[int(position)]

    def _restore(self, problem: Problem | None) -> None:
        if problem is None:
            return
        wanted = _key(problem)
        for position, candidate in enumerate(self._visible):
            if _key(candidate) == wanted:
                self.select_row(position)
                return

    def _index_of(self, position: int) -> QModelIndex:
        stack = [self.list_model.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for row in range(node.rowCount()):
                child = node.child(row, 0)
                if child is None:
                    continue
                value = child.data(PROBLEM_ROLE)
                if value is not None and int(value) == position:
                    return child.index()
                stack.append(child)
        return QModelIndex()

    def select_row(self, position: int) -> None:
        """Select the problem at `position` of the shown list (top to bottom)."""
        index = self._index_of(position)
        if index.isValid():
            self.view.setCurrentIndex(index)
            self.view.scrollTo(index)

    def select_next(self, step: int = 1) -> Problem | None:
        """Select the next (or, with -1, the previous) shown problem; wraps around."""
        if not self._visible:
            return None
        current = self.current_problem()
        if current is None:
            position = 0 if step > 0 else len(self._visible) - 1
        else:
            position = (self._visible.index(current) + step) % len(self._visible)
        self.select_row(position)
        return self._visible[position]

    def _activated(self, index: QModelIndex) -> None:
        position = index.siblingAtColumn(0).data(PROBLEM_ROLE)
        if position is not None:
            self.activate_row(int(position))

    def activate_row(self, row: int) -> None:
        """Jump to the file and line of the problem at `row` of the shown list."""
        if 0 <= row < len(self._visible):
            problem = self._visible[row]
            if problem.file:
                self.jump_requested.emit(problem.file, problem.line or 1)
