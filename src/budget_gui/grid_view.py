"""The grid widgets of the Model tab: a table with spreadsheet habits and the page around it.

The table edits through its model into the `ModelDocument`, so every change is an undo step and
nothing is written until Save. It reads and writes the clipboard as text with tabs (a range copied
from a spreadsheet pastes as it is), fills down, clears optional cells, moves down on Enter and
lets Tab leave the grid after the last cell. Pasting more than one cell shows what would change
first. Feedback is a line under the grid, never a message box.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import (
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_gui import icons, theme
from budget_gui.components import Button
from budget_gui.delegates import CellDelegate
from budget_gui.edit_bar import EditBar
from budget_gui.frozen_view import GridView
from budget_gui.grid_models import GridModel
from budget_gui.model_document import ModelDocument

PREVIEW_ROWS = 200
FIT_ROWS = 80  # rows measured to size the columns
MAX_COLUMN = 300  # a long source is cut off in the cell; its tooltip has all of it
SHOWN_PROBLEMS = 3


@dataclass
class PastePlan:
    """What a paste would do: the cells to write (source row, column, text) and what it skips."""

    cells: list[tuple[int, int, str]] = field(default_factory=list)
    skipped: int = 0  # cells that cannot be edited (ids, computed columns)
    clipped: int = 0  # cells that fall outside the grid


def parse_clipboard(text: str) -> list[list[str]]:
    """A block of text with tabs between cells and a line per row, as spreadsheets copy it."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()  # the line end after the last row
    return [line.split("\t") for line in lines]


class PastePreview(QDialog):
    """Old and new text of every cell a paste would change; Apply or Cancel."""

    def __init__(
        self, rows: list[tuple[str, str, str]], total: int, parent: QWidget | None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paste")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        message = QLabel(
            f"{total} cell{'s' if total != 1 else ''} would change. You can undo the paste."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        table = QTableWidget(len(rows), 3)
        table.setHorizontalHeaderLabels(["Cell", "Now", "Pasted"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # a preview: the buttons are what to reach
        mono = theme.mono_font()
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if c:  # the old and the new value: figures in the mono font
                    item.setFont(mono)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)
        if total > len(rows):
            more = QLabel(f"… and {total - len(rows)} more")
            more.setProperty("role", "muted")
            layout.addWidget(more)
        self.apply_button = Button(f"Paste {total} cells", "primary")
        cancel = Button("Cancel")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.gap(1))
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))


class GridProxy(QSortFilterProxyModel):
    """Filters rows by a text (any column) and, when set, by a test on the source row."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.row_test: Callable[[int], bool] | None = None

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        if self.row_test is not None and not self.row_test(source_row):
            return False
        return super().filterAcceptsRow(source_row, source_parent)


class GridTable(QWidget):
    """A table over a `GridModel` with filter, copy, paste, fill-down and clear. The widget is a
    holder: the view is `self.view`, the sorted and filtered model is `self.proxy`."""

    message = Signal(str)  # non-modal feedback for the line under the grid
    selection_changed = Signal()

    def __init__(self, model: GridModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self._fit_pending = True
        self.proxy = GridProxy(self)
        self.proxy.setSourceModel(model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.view = GridView()
        self.view.setModel(self.proxy)
        self.delegate = CellDelegate(self.view)
        self.delegate.closeEditor.connect(self._editor_closed)
        self.view.setItemDelegate(self.delegate)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.view.setTabKeyNavigation(True)
        self.view.verticalHeader().setDefaultSectionSize(theme.px(theme.ROW_HEIGHT))
        self.view.horizontalHeader().setStretchLastSection(False)
        self.view.horizontalHeader().setResizeContentsPrecision(
            FIT_ROWS
        )  # sample, do not measure all
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        frozen = self.view.frozen
        frozen.customContextMenuRequested.connect(
            lambda pos: self._context_menu(
                self.view.viewport().mapFromGlobal(frozen.viewport().mapToGlobal(pos))
            )
        )
        self.view.installEventFilter(self)
        self.view.selectionModel().selectionChanged.connect(
            lambda *_a: self.selection_changed.emit()
        )
        self.view.selectionModel().currentChanged.connect(lambda *_a: self.selection_changed.emit())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.extra_actions: list[Callable[[QMenu, int], None]] = []

    # ---- filter, size ------------------------------------------------------------------------
    def set_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text.strip())

    def set_row_test(self, test: Callable[[int], bool] | None) -> None:
        self.proxy.row_test = test
        self.proxy.invalidate()

    def request_fit(self) -> None:
        """Size the columns now when the grid is on screen, else when it is first shown (a grid
        of another tab is not measured on every reload)."""
        if self.isVisible():
            self.fit_columns()
        else:
            self._fit_pending = True

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if self._fit_pending:
            self.fit_columns()

    def fit_columns(self) -> None:
        """Size the columns to their contents, with room to spare so nothing is cut off."""
        self._fit_pending = False
        self.view.resizeColumnsToContents()
        header = self.view.horizontalHeader()
        for column in range(self.model.columnCount()):
            header.resizeSection(column, min(header.sectionSize(column) + 16, MAX_COLUMN))

    def visible_rows(self) -> int:
        return self.proxy.rowCount()

    # ---- positions ---------------------------------------------------------------------------
    def _source(self, index: QModelIndex) -> tuple[int, int]:
        mapped = self.proxy.mapToSource(index)
        return mapped.row(), mapped.column()

    def current_cell(self) -> tuple[int, int] | None:
        """The current cell as (source row, column); None when no cell is current."""
        index = self.view.currentIndex()
        return self._source(index) if index.isValid() else None

    def select_cell(self, source_row: int, column: int = 0) -> bool:
        """Make a cell current and visible (False when the filter hides it)."""
        index = self.proxy.mapFromSource(self.model.index(source_row, column))
        if not index.isValid():
            return False
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index)
        return True

    def _box(self) -> tuple[int, int, int, int] | None:
        """The bounding box of the selection in view coordinates: row0, col0, row1, col1."""
        indexes = self.view.selectionModel().selectedIndexes()
        if not indexes:
            current = self.view.currentIndex()
            if not current.isValid():
                return None
            return current.row(), current.column(), current.row(), current.column()
        rows = [i.row() for i in indexes]
        cols = [i.column() for i in indexes]
        return min(rows), min(cols), max(rows), max(cols)

    def _editor_closed(self, _editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
        """Enter ends an edit with this hint (Tab and Escape use others): go to the row below."""
        if hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            self._move_down()

    def _move_down(self) -> None:
        index = self.view.currentIndex()
        below = self.proxy.index(index.row() + 1, index.column())
        if below.isValid():
            self.view.setCurrentIndex(below)

    # ---- copy --------------------------------------------------------------------------------
    def _text_at(self, row: int, column: int) -> str:
        index = self.proxy.index(row, column)
        source_row, source_column = self._source(index)
        role = (
            Qt.ItemDataRole.EditRole
            if self.model.columns[source_column].editable
            else Qt.ItemDataRole.DisplayRole
        )
        return str(self.model.index(source_row, source_column).data(role) or "")

    def copy_text(self) -> str:
        box = self._box()
        if box is None:
            return ""
        r0, c0, r1, c1 = box
        return "\n".join(
            "\t".join(self._text_at(r, c) for c in range(c0, c1 + 1)) for r in range(r0, r1 + 1)
        )

    def copy(self) -> None:
        text = self.copy_text()
        if text:
            QApplication.clipboard().setText(text)
            cells = text.count("\t") + text.count("\n") + 1
            self.message.emit(f"Copied {cells} cell{'s' if cells != 1 else ''}.")

    # ---- paste -------------------------------------------------------------------------------
    def plan_paste(self, text: str) -> PastePlan:
        """Where a block of text would go: from the first selected cell, or over the whole
        selection when a single value is pasted into several cells."""
        plan = PastePlan()
        block = parse_clipboard(text)
        box = self._box()
        if not block or box is None:
            return plan
        r0, c0, r1, c1 = box
        if len(block) == 1 and len(block[0]) == 1 and (r1 > r0 or c1 > c0):
            targets = [(r, c, block[0][0]) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
        else:
            targets = [
                (r0 + i, c0 + j, cell)
                for i, line in enumerate(block)
                for j, cell in enumerate(line)
            ]
        for row, column, value in targets:
            if row >= self.proxy.rowCount() or column >= self.proxy.columnCount():
                plan.clipped += 1
                continue
            source_row, source_column = self._source(self.proxy.index(row, column))
            if not self.model.columns[source_column].editable:
                plan.skipped += 1
                continue
            if value.strip() != self._current_text(source_row, source_column).strip():
                plan.cells.append((source_row, source_column, value))
        return plan

    def _current_text(self, source_row: int, column: int) -> str:
        return str(self.model.index(source_row, column).data(Qt.ItemDataRole.EditRole) or "")

    def apply_cells(self, cells: list[tuple[int, int, str]], what: str) -> bool:
        """Write many cells as one undo step."""
        changes = []
        for row, column, text in cells:
            change = self.model.change_for(row, column, text)
            if change is not None:
                changes.append((change[0], change[1]))
        if not changes:
            return False
        n = len(cells)
        return self.model.document.edit(changes, f"{what} {n} cell{'s' if n != 1 else ''}")

    def paste(self) -> bool:
        plan = self.plan_paste(QApplication.clipboard().text())
        if not plan.cells:
            reason = "nothing to paste or nothing would change"
            if plan.skipped:
                reason += (
                    f" ({plan.skipped} cell{'s' if plan.skipped != 1 else ''} cannot be edited)"
                )
            self.message.emit(f"Paste: {reason}.")
            return False
        if len(plan.cells) > 1 and not self._confirm(plan):
            return False
        ok = self.apply_cells(plan.cells, "Paste")
        notes = []
        if plan.skipped:
            notes.append(f"{plan.skipped} that cannot be edited were left out")
        if plan.clipped:
            notes.append(f"{plan.clipped} fell outside the grid")
        extra = f" ({'; '.join(notes)})" if notes else ""
        n = len(plan.cells)
        self.message.emit(f"Pasted {n} cell{'s' if n != 1 else ''}{extra}. Undo with Ctrl+Z.")
        return ok

    def _confirm(self, plan: PastePlan) -> bool:
        rows = []
        for row, column, text in plan.cells[:PREVIEW_ROWS]:
            label = (
                f"{self.model.label_of(self.model._keys[row])}, {self.model.columns[column].key}"
            )
            rows.append((label, self._current_text(row, column), text.strip()))
        return self.preview(rows, len(plan.cells)) == QDialog.DialogCode.Accepted

    def preview(self, rows: list[tuple[str, str, str]], total: int) -> QDialog.DialogCode:
        dialog = PastePreview(rows, total, self.window())
        return QDialog.DialogCode(dialog.exec())

    # ---- fill down and clear -----------------------------------------------------------------
    def fill_down(self) -> bool:
        box = self._box()
        if box is None:
            return False
        r0, c0, r1, c1 = box
        if r1 == r0:
            self.message.emit("Fill down: select the cell to copy and the cells below it.")
            return False
        cells = []
        for column in range(c0, c1 + 1):
            top_row, source_column = self._source(self.proxy.index(r0, column))
            if not self.model.columns[source_column].editable:
                continue
            text = self._current_text(top_row, source_column)
            for row in range(r0 + 1, r1 + 1):
                target, _ = self._source(self.proxy.index(row, column))
                if self._current_text(target, source_column) != text:
                    cells.append((target, source_column, text))
        if not cells:
            return False
        ok = self.apply_cells(cells, "Fill down")
        self.message.emit(
            f"Filled {len(cells)} cell{'s' if len(cells) != 1 else ''}. Undo with Ctrl+Z."
        )
        return ok

    def clear_cells(self) -> bool:
        """Empty the selected cells that may be empty (optional ones); the others are left."""
        box = self._box()
        if box is None:
            return False
        r0, c0, r1, c1 = box
        cells, kept = [], 0
        for row in range(r0, r1 + 1):
            for column in range(c0, c1 + 1):
                source_row, source_column = self._source(self.proxy.index(row, column))
                col = self.model.columns[source_column]
                if col.editable and col.optional:
                    if self._current_text(source_row, source_column):
                        cells.append((source_row, source_column, ""))
                elif col.editable:
                    kept += 1
        if not cells:
            if kept:
                self.message.emit("These cells need a value; only optional cells can be emptied.")
            return False
        ok = self.apply_cells(cells, "Clear")
        self.message.emit(
            f"Cleared {len(cells)} cell{'s' if len(cells) != 1 else ''}. Undo with Ctrl+Z."
        )
        return ok

    # ---- keys and menu -----------------------------------------------------------------------
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt naming)
        is_key = event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent)
        if watched is self.view and is_key and self._key(event):  # type: ignore[arg-type]
            return True
        return super().eventFilter(watched, event)

    def _key(self, event: QKeyEvent) -> bool:
        if self.view.state() == QAbstractItemView.State.EditingState:
            return False
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            return True
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste()
            return True
        if event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.fill_down()
            return True
        if event.key() == Qt.Key.Key_Delete and not event.modifiers():
            self.clear_cells()
            return True
        if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return self._leave_on_tab(event)
        return False

    def _leave_on_tab(self, event: QKeyEvent) -> bool:
        """Tab walks the cells; after the last (or before the first) it leaves the grid."""
        index = self.view.currentIndex()
        forward = (
            event.key() == Qt.Key.Key_Tab
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        last = self.proxy.index(self.proxy.rowCount() - 1, self.proxy.columnCount() - 1)
        first = self.proxy.index(0, 0)
        if forward and (not index.isValid() or index == last):
            self.view.focusNextChild()
            return True
        if not forward and (not index.isValid() or index == first):
            self.view.focusPreviousChild()
            return True
        return False

    def _context_menu(self, pos: QPoint) -> None:
        index = self.view.indexAt(pos)
        if index.isValid() and not self.view.selectionModel().isSelected(index):
            self.view.selectionModel().select(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
            self.view.setCurrentIndex(index)
        menu = QMenu(self)
        for text, icon, slot, keys in (
            ("Copy", "copy", self.copy, QKeySequence.StandardKey.Copy),
            ("Paste", "clipboard-paste", self.paste, QKeySequence.StandardKey.Paste),
            ("Fill down", "", self.fill_down, QKeySequence("Ctrl+D")),
            ("Clear", "", self.clear_cells, QKeySequence(Qt.Key.Key_Delete)),
        ):
            action = QAction(icons.icon(icon) if icon else icons.icon("circle-dashed"), text, menu)
            action.setShortcut(keys)
            action.triggered.connect(lambda _c=False, s=slot: s())
            menu.addAction(action)
        row = self._source(index)[0] if index.isValid() else -1
        for add in self.extra_actions:
            add(menu, row)
        menu.exec(self.view.viewport().mapToGlobal(pos))


class GridPage(QWidget):
    """A grid under its toolbar (the filter, the page's own tools, Undo, Redo, the cell styles and
    Save) and above the lines of what is shown or wrong and of feedback (D-176)."""

    save_requested = Signal()
    legend_requested = Signal()

    def __init__(
        self,
        model: GridModel,
        document: ModelDocument,
        *,
        what: str,
        filter_hint: str = "Filter rows",
    ) -> None:
        super().__init__()
        self.model = model
        self.document = document
        self.what = what  # "unit" / "power mode" / "input": the thing a row is
        self.table = GridTable(model)
        self.table.view.setAccessibleName(f"{what.capitalize()} grid")
        self.table.view.frozen.setAccessibleName(f"{what.capitalize()} names")
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(filter_hint)
        self.filter.setClearButtonEnabled(True)
        self.filter.setAccessibleName(filter_hint)
        self.filter.textChanged.connect(self._filter_changed)
        self.tools = QHBoxLayout()
        self.tools.setSpacing(theme.gap(1))
        self.tools.addWidget(self.filter, 1)
        self.tools_extra = QHBoxLayout()
        self.tools_extra.setSpacing(theme.gap(0))
        self.tools.addLayout(self.tools_extra)
        self.bar = EditBar(document)
        self.undo_button, self.redo_button = self.bar.undo_button, self.bar.redo_button
        self.save_button, self.legend_button = self.bar.save_button, self.bar.legend_button
        self.bar.save_requested.connect(self.save_requested)
        self.bar.legend_requested.connect(self.legend_requested)
        self.count_label = QLabel()
        self.count_label.setProperty("role", "muted")
        self.problem_label = QLabel()
        self.problem_label.setWordWrap(True)
        self.problem_label.setProperty("role", "error")
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        self.tools.addWidget(self.bar)
        layout = QVBoxLayout(self)
        layout.addLayout(self.tools)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.problem_label)
        layout.addWidget(self.feedback_label)
        layout.addWidget(self.count_label)
        self.table.message.connect(self.show_message)
        document.changed.connect(self._refresh)
        self.model.modelReset.connect(self.table.request_fit)
        self._refresh()

    def show_message(self, text: str) -> None:
        """Say something under the grid (what an edit or a save did, why it did not)."""
        self.feedback_label.setText(text)
        self.feedback_label.setVisible(bool(text))

    def add_tool(self, widget: QWidget) -> None:
        self.tools_extra.addWidget(widget)

    def _filter_changed(self, text: str) -> None:
        self.table.set_filter(text)
        self._refresh()

    def _refresh(self) -> None:
        lines = self.model.problem_lines()
        if lines:
            shown = "; ".join(lines[:SHOWN_PROBLEMS])
            more = f" and {len(lines) - SHOWN_PROBLEMS} more" if len(lines) > SHOWN_PROBLEMS else ""
            n = len(lines)
            self.problem_label.setText(
                f"{n} cell{'s' if n != 1 else ''} need{'' if n != 1 else 's'} correcting: "
                f"{shown}{more}. Nothing is saved until they are right, or undone."
            )
        else:
            self.problem_label.setText("")
        self.problem_label.setVisible(bool(lines))
        shown_rows, rows = self.table.visible_rows(), self.model.rowCount()
        word = self.what if rows == 1 else f"{self.what}s"
        if rows == 0:
            self.count_label.setText(
                f"Open a project to see its {self.what}s."
                if self.document.root is None
                else f"No {self.what}s in this project."
            )
        elif shown_rows != rows:
            self.count_label.setText(f"Showing {shown_rows} of {rows} {word}.")
        else:
            self.count_label.setText(f"{rows} {word}")
