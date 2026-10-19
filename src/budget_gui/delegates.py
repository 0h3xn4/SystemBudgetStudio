"""How a table cell looks: numbers, placeholders, `n/a`, limits and margins (D-150).

One delegate paints every cell of every table, so the same state always looks the same:

* a **number** is right-aligned in JetBrains Mono with the same digits in every row;
* a **placeholder** (an input without a source) is italic, has a dashed border and a hollow
  marker; its tooltip says that results depending on it show `n/a`;
* **n/a** (a result that could not be computed, a limit that could not be checked) has its own
  tint and a "minus" marker: it never looks like `0`, like a small number or like an empty cell;
* a **limit state** (within, near, broken) has a tint, an icon and text, never colour alone;
* a **margin** can carry a thin bar below the number that shows how much of the limit is used.

Models give the state through item data roles (below); a cell without a state is drawn as plain
text. Colours come from the theme.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from budget_gui import icons, theme
from budget_gui.theme import Status

Index = QModelIndex | QPersistentModelIndex

STATE_ROLE = int(Qt.ItemDataRole.UserRole) + 20  # a `Status` (or its value), or None
MARGIN_ROLE = int(Qt.ItemDataRole.UserRole) + 21  # share of the limit used, 0 to 1 (more: broken)
NUMERIC_ROLE = int(Qt.ItemDataRole.UserRole) + 22  # True: right-aligned figures in the mono font
TOTAL_ROLE = int(Qt.ItemDataRole.UserRole) + 23  # True: a totals row (bold, a line above it)
SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 23  # the source text, for the tooltip and the grid

PAD = theme.SPACE[1]
ICON = 14
BAR_HEIGHT = 3

TOOLTIPS = {
    Status.PLACEHOLDER: "Placeholder: this number has no source. Results that depend on it "
    "show n/a.",
    Status.NOT_CHECKED: "n/a: this result depends on an input that is a placeholder or missing, "
    "so it is not computed. Nothing is guessed.",
    Status.PASS: "Within the limit.",
    Status.NEAR: "Near the limit.",
    Status.FAIL: "The limit is broken.",
}


def status_of(value: object) -> Status | None:
    if value is None:
        return None
    try:
        return Status(str(value))
    except ValueError:
        return None


class CellDelegate(QStyledItemDelegate):
    """Paints the cells of a table by their state; see the module text."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._widths: dict[tuple[str, bool, Status | None, bool, str], int] = {}

    def sizeHint(self, option: QStyleOptionViewItem, index: Index) -> QSize:  # noqa: N802
        # Measured from the font directly: the default size hint asks the model for about nine
        # roles per cell, which made a table of 200 units take a third of a second to size.
        opt: Any = option
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        status = status_of(index.data(STATE_ROLE))
        numeric = bool(index.data(NUMERIC_ROLE))
        base: QFont = opt.font
        total = bool(index.data(TOTAL_ROLE))
        key = (text, numeric, status, total, base.key())
        width = self._widths.get(key)
        if width is None:
            font = self._font_for(base, numeric, status, total)
            width = QFontMetrics(font).horizontalAdvance(text)
            width += 2 * PAD + 1 + (ICON + PAD // 2 if status is not None else 0)  # 1: grid line
            self._widths[key] = width
        height = QFontMetrics(base).height() + PAD
        return QSize(width, max(height, ICON + PAD))

    @staticmethod
    def _font_for(base: QFont, numeric: bool, status: Status | None, total: bool = False) -> QFont:
        if numeric and status is not Status.NOT_CHECKED:
            font = theme.mono_font(theme.TYPE_BASE)
        else:
            font = QFont(base)
        if status is Status.PLACEHOLDER:
            font.setItalic(True)
        elif status is Status.FAIL or total:
            font.setWeight(QFont.Weight.DemiBold)
        return font

    def _font(self, option: Any, index: Index, status: Status | None) -> QFont:
        return self._font_for(
            option.font, bool(index.data(NUMERIC_ROLE)), status, bool(index.data(TOTAL_ROLE))
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Index) -> None:
        opt: Any = option  # the stubs of QStyleOptionViewItem lack rect, state, font, features
        t = theme.tokens()
        status = status_of(index.data(STATE_ROLE))
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        rect = QRect(opt.rect)
        painter.save()
        painter.setClipRect(rect)
        if selected:
            painter.fillRect(rect, QColor(t.selected))
        elif status is not None:
            painter.fillRect(rect, QColor(t.status(status).bg))
        elif opt.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor(t.hover))
        text_colour = QColor(t.text)
        if status is not None and not selected:
            text_colour = QColor(t.status(status).fg)
        left = rect.left() + PAD
        if status is not None:
            pixmap = icons.status_icon(status, t).pixmap(QSize(ICON, ICON))
            painter.drawPixmap(left, rect.center().y() - ICON // 2 + 1, pixmap)
            left += ICON + PAD // 2
        font = self._font(opt, index, status)
        painter.setFont(font)
        painter.setPen(text_colour)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        numeric = bool(index.data(NUMERIC_ROLE))
        text_rect = QRect(left, rect.top(), rect.right() + 1 - PAD - left, rect.height())
        flags = Qt.AlignmentFlag.AlignVCenter | (
            Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft
        )
        painter.drawText(
            text_rect,
            int(flags),
            QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
        )
        if index.data(TOTAL_ROLE):
            painter.setPen(QPen(QColor(t.border_strong), 1))
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
        if status is Status.PLACEHOLDER:
            pen = QPen(QColor(t.status(status).fg), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))  # whole pixels: crisp dashes
        share = index.data(MARGIN_ROLE)
        if isinstance(share, int | float) and status is not None:
            width = max(0.0, min(float(share), 1.0)) * (rect.width() - 2 * PAD)
            bar = QRectF(rect.left() + PAD, rect.bottom() - BAR_HEIGHT - 1, width, BAR_HEIGHT)
            painter.fillRect(bar, QColor(t.status(status).fg))
        painter.restore()


def tooltip_for(status: Status | None, source: str | None = None) -> str | None:
    """The tooltip of a cell: what its state means, and its source when it has one."""
    parts = []
    if status is not None:
        parts.append(TOOLTIPS[status])
    if source:
        parts.append(f"Source: {source}")
    return "\n".join(parts) if parts else None
