"""A table whose first column stays in view when the grid scrolls sideways (D-176).

The first column of every grid names the row (a unit, a power mode, an input), so it must not
scroll away from the cells that belong to it. A second, read-only view of the same model and the
same selection sits over the left edge of the first one and shows only that column; the two scroll
together vertically. Nothing is copied: a click in the frozen column selects in the one selection
model, and the keyboard always belongs to the main view.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QMouseEvent, QResizeEvent
from PySide6.QtWidgets import QAbstractItemDelegate, QAbstractItemView, QTableView, QWidget

from budget_gui import theme

Index = QModelIndex | QPersistentModelIndex


class _FrozenColumn(QTableView):
    """The overlay: column 0 of the model, no scroll bars, no keyboard, no editing."""

    def __init__(self, owner: GridView) -> None:
        super().__init__(owner)
        self._owner = owner
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QTableView.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionsClickable(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setProperty("role", "frozen")

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        super().mousePressEvent(event)
        self._owner.setFocus()  # the keyboard stays with the main view

    def wheelEvent(self, event: object) -> None:  # noqa: N802
        self._owner.wheelEvent(event)  # type: ignore[arg-type]


class GridView(QTableView):
    """A `QTableView` with its first column frozen over the left edge."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frozen = _FrozenColumn(self)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        row = theme.px(theme.ROW_HEIGHT)
        self.verticalHeader().setDefaultSectionSize(row)
        self.frozen.verticalHeader().setDefaultSectionSize(row)
        self.horizontalHeader().sectionResized.connect(self._section_resized)
        self.verticalScrollBar().valueChanged.connect(self.frozen.verticalScrollBar().setValue)
        self.frozen.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)

    # ---- what the two views share --------------------------------------------------------------
    def setModel(self, model: QAbstractItemModel | None) -> None:  # noqa: N802
        super().setModel(model)
        self.frozen.setModel(model)
        selection = self.selectionModel()
        if selection is not None:
            self.frozen.setSelectionModel(selection)
        if model is not None:
            model.modelReset.connect(self._hide_other_columns)
        self._hide_other_columns()

    def setItemDelegate(self, delegate: QAbstractItemDelegate) -> None:  # noqa: N802
        super().setItemDelegate(delegate)
        self.frozen.setItemDelegate(delegate)

    def _hide_other_columns(self) -> None:
        model = self.model()
        for column in range(1, model.columnCount() if model is not None else 0):
            self.frozen.setColumnHidden(column, True)
        self._place()

    # ---- geometry ------------------------------------------------------------------------------
    def _section_resized(self, column: int, _old: int, new: int) -> None:
        if column == 0:
            self.frozen.setColumnWidth(0, new)
            self._place()

    def _place(self) -> None:
        """Put the overlay over the left edge of the viewport, as wide as column 0."""
        left = self.verticalHeader().width() + self.frameWidth()
        header = self.horizontalHeader()
        self.frozen.setColumnWidth(0, self.columnWidth(0))
        self.frozen.setGeometry(
            left,
            self.frameWidth(),
            self.columnWidth(0),
            self.viewport().height() + (header.height() if header.isVisible() else 0),
        )
        self.frozen.raise_()

    def frozen_width(self) -> int:
        return self.columnWidth(0)

    def updateGeometries(self) -> None:  # noqa: N802
        super().updateGeometries()
        if hasattr(self, "frozen"):
            self._place()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place()

    # ---- the keyboard never leaves a cell hidden under the overlay -------------------------------
    def scrollTo(  # noqa: N802
        self,
        index: Index,
        hint: QAbstractItemView.ScrollHint = QAbstractItemView.ScrollHint.EnsureVisible,
    ) -> None:
        super().scrollTo(index, hint)
        if index.column() > 0:
            hidden = self.frozen_width() - self.visualRect(index).left()
            if hidden > 0:
                bar = self.horizontalScrollBar()
                bar.setValue(bar.value() - hidden)
