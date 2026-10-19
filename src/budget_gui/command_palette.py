"""The command palette, Ctrl+K: type a few words, press Enter (D-166).

One list of everything the window can do or go to: the menu commands, the units, the files, the
scenarios and the problems of the open project. The words typed must all appear in a command, in
any order and case; the nearest to the start comes first. Up and Down move in the list while the
cursor stays in the field; Enter runs the command; Esc closes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
)

from budget_gui import icons, theme

MAX_SHOWN = 60


@dataclass(frozen=True)
class Command:
    text: str  # what is searched and shown
    run: Callable[[], object]
    hint: str = ""  # a shortcut, or the kind of thing ("unit", "file")


def rank(query: str, commands: list[Command]) -> list[Command]:
    """The commands that contain every word of the query, the nearest to the start first (then
    the shortest). An empty query lists the commands in the order they were given."""
    words = query.lower().split()
    if not words:
        return list(commands)
    scored: list[tuple[int, int, int, Command]] = []
    for position, command in enumerate(commands):
        haystack = f"{command.text} {command.hint}".lower()
        spots = [haystack.find(word) for word in words]
        if min(spots) < 0:
            continue
        scored.append((sum(spots), len(command.text), position, command))
    scored.sort(key=lambda item: item[:3])
    return [item[3] for item in scored]


KINDS = {"unit": "Unit", "scenario": "Scenario", "file": "File", "problem": "Problem"}
SECTION_ROLE, LABEL_ROLE, CHIP_ROLE = (Qt.ItemDataRole.UserRole + i for i in (1, 2, 3))


def display_parts(command: Command) -> tuple[str, str, str]:
    """(section, label, shortcut) of a command as the palette shows it: the menu a command is in,
    what it does, and its key. 'File > Open project' is 'File', 'Open project'."""
    kind = KINDS.get(command.hint)
    if kind is not None:
        label = command.text
        for prefix in ("Open unit ", "Select scenario ", "Open file ", "Go to problem: "):
            label = label.removeprefix(prefix)
        return kind, label, ""
    section, _, label = command.text.partition(" > ")
    chip = "" if command.hint in ("", "menu") else command.hint
    return (section, label, chip) if label else ("", command.text, chip)


Index = QModelIndex | QPersistentModelIndex


class _RowDelegate(QStyledItemDelegate):
    """A row of the palette: the section in muted type, the command, the shortcut as a chip."""

    def sizeHint(self, option: QStyleOptionViewItem, index: Index) -> QSize:  # noqa: N802
        return QSize(0, theme.px(theme.CONTROL_COMPACT))

    def paint(  # noqa: D102
        self, painter: QPainter, option: QStyleOptionViewItem, index: Index
    ) -> None:
        t = theme.tokens()
        rect = QRect(option.rect)  # type: ignore[attr-defined]
        state = option.state  # type: ignore[attr-defined]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inner = rect.adjusted(theme.gap(0), 1, -theme.gap(0), -1)
        if state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(t.selected))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(inner, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        elif state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(t.hover))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(inner, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        pad = theme.gap(1)
        section_width = theme.px(theme.SECTION_COLUMN)
        left = inner.left() + pad
        chip = str(index.data(CHIP_ROLE) or "")
        chip_width = 0
        small = theme.ui_font(theme.TYPE_SMALL)
        painter.setFont(small)
        painter.setPen(QColor(t.text_muted))
        painter.drawText(
            QRect(left, inner.top(), section_width - pad, inner.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            painter.fontMetrics().elidedText(
                str(index.data(SECTION_ROLE) or ""),
                Qt.TextElideMode.ElideRight,
                section_width - pad,
            ),
        )
        if chip:
            mono = theme.mono_font(theme.TYPE_CAPTION)
            painter.setFont(mono)
            chip_width = painter.fontMetrics().horizontalAdvance(chip) + 2 * pad
            chip_rect = QRect(
                inner.right() - pad - chip_width,
                inner.top() + pad // 2 + 1,
                chip_width,
                inner.height() - pad - 2,
            )
            painter.setPen(QPen(QColor(t.border_strong), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(chip_rect, theme.RADIUS_CONTROL - 2, theme.RADIUS_CONTROL - 2)
            painter.setPen(QColor(t.text_secondary))
            painter.drawText(chip_rect, int(Qt.AlignmentFlag.AlignCenter), chip)
        painter.setFont(theme.ui_font(theme.TYPE_BASE))
        painter.setPen(QColor(t.text))
        room = inner.right() - left - section_width - chip_width - 2 * pad
        painter.drawText(
            QRect(left + section_width, inner.top(), max(room, 0), inner.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            painter.fontMetrics().elidedText(
                str(index.data(LABEL_ROLE) or ""), Qt.TextElideMode.ElideRight, max(room, 0)
            ),
        )
        painter.restore()


class CommandPalette(QDialog):
    def __init__(self, commands: list[Command], parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle("Find a command")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setProperty("role", "raised")  # a raised card over the window
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._commands = list(commands)
        self._shown: list[Command] = []
        self.field = QLineEdit()
        self.field.setPlaceholderText("Type to find a command, a unit, a file or a problem")
        self.field.setClearButtonEnabled(True)
        self.field.addAction(
            icons.icon("search", theme.tokens().text_muted),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.listing = QListWidget()
        self.listing.setItemDelegate(_RowDelegate(self.listing))
        self.listing.setMouseTracking(True)
        self.listing.setFrameShape(QListWidget.Shape.NoFrame)
        self.listing.setTabKeyNavigation(False)
        self.listing.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the keys stay in the field
        self.empty = QLabel("Nothing matches.")
        self.empty.setProperty("role", "muted")
        self.footer = QLabel("↑ ↓ to move   ·   Enter to run   ·   Esc to close")
        self.footer.setProperty("role", "caption")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(1))
        layout.setSpacing(theme.gap(1))
        layout.addWidget(self.field)
        layout.addWidget(self.listing, 1)
        layout.addWidget(self.empty)
        layout.addWidget(self.footer)
        self.field.textChanged.connect(self._filter)
        self.listing.itemActivated.connect(lambda _item: self.run_current())
        self.listing.itemClicked.connect(lambda _item: self.run_current())
        self._filter("")

    def _filter(self, text: str) -> None:
        self._shown = rank(text, self._commands)[:MAX_SHOWN]
        self.listing.clear()
        for command in self._shown:
            section, label, chip = display_parts(command)
            item = QListWidgetItem(command.text)  # the text is what a screen reader reads
            item.setData(SECTION_ROLE, section)
            item.setData(LABEL_ROLE, label)
            item.setData(CHIP_ROLE, chip)
            self.listing.addItem(item)
        if self._shown:
            self.listing.setCurrentRow(0)
        self.empty.setVisible(not self._shown)

    def showEvent(self, event: object) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)  # type: ignore[arg-type]
        parent = self.parentWidget()
        if parent is not None:  # near the top, in the middle of the window
            window = parent.window()
            top_left = window.mapToGlobal(QPoint(0, 0))
            self.move(
                top_left.x() + (window.width() - self.width()) // 2,
                top_left.y() + window.height() // 8,
            )
        self.field.setFocus()

    def shown(self) -> list[str]:
        return [c.text for c in self._shown]

    def run_current(self) -> None:
        row = self.listing.currentRow()
        if 0 <= row < len(self._shown):
            command = self._shown[row]
            self.accept()  # close first: the command may open a dialog of its own
            command.run()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            step = 1 if key == Qt.Key.Key_Down else -1
            row = min(max(self.listing.currentRow() + step, 0), self.listing.count() - 1)
            self.listing.setCurrentRow(row)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.run_current()
        else:
            super().keyPressEvent(event)
