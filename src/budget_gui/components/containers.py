"""Cards, section headers, key-value lists and empty states (D-169)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from budget_gui import icons, theme
from budget_gui.components.buttons import Button


class Card(QFrame):
    """A panel: the surface colour, a 1 px subtle border, 8 px corners. Not a box in a box: use it
    for one group of related content, not around every control."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(2))
        layout.setSpacing(theme.gap(1))
        self.body = layout


class PanelTitle(QWidget):
    """The title row of a dock: the name, and a close button (a ghost icon button)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "panel-title")
        self.label = QLabel(title)
        self.close_button = Button("", "ghost", icon="x", compact=True, tip=f"Hide {title}")
        self.close_button.setAccessibleName(f"Hide {title}")
        self.close_button.setFixedSize(
            theme.px(theme.CONTROL_COMPACT), theme.px(theme.CONTROL_COMPACT)
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(theme.gap(1), 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.label, 1)
        row.addWidget(self.close_button)


class SectionHeader(QWidget):
    """A title with actions on the right (buttons are added with `add_action`)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(title)
        self.title.setProperty("role", "title")
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(theme.gap(1))
        self._row.addWidget(self.title)
        self._row.addStretch(1)

    def add_action(self, button: QWidget) -> None:
        self._row.addWidget(button)


class KeyValueList(QWidget):
    """Names on the left, values on the right in the monospaced font (IDs, paths, numbers)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(theme.gap(2))
        self._grid.setVerticalSpacing(theme.gap(0))
        self._grid.setColumnStretch(1, 1)
        self._values: list[QLabel] = []
        self._names: list[QLabel] = []

    def set_items(self, items: Sequence[tuple[str, str]]) -> None:
        for label in (*self._names, *self._values):
            self._grid.removeWidget(label)
            label.deleteLater()
        self._names, self._values = [], []
        for row, (name, value) in enumerate(items):
            key, text = QLabel(name), QLabel(value)
            key.setProperty("role", "muted")
            text.setFont(theme.mono_font(theme.TYPE_SMALL))
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.setWordWrap(True)
            self._grid.addWidget(key, row, 0, Qt.AlignmentFlag.AlignTop)
            self._grid.addWidget(text, row, 1)
            self._names.append(key)
            self._values.append(text)

    def values(self) -> dict[str, str]:
        return {k.text(): v.text() for k, v in zip(self._names, self._values, strict=True)}


class EmptyState(QFrame):
    """What an empty list or table shows: one line of explanation and the primary action."""

    action_requested = Signal()

    def __init__(
        self,
        message: str,
        action: str | None = None,
        *,
        icon: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "empty")
        self._icon_name = icon
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(4))
        layout.setSpacing(theme.gap(1))
        layout.addStretch(1)
        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message = QLabel(message)
        self.message.setProperty("role", "muted")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        layout.addWidget(self._icon)
        layout.addWidget(self.message)
        self.button: Button | None = None
        if action:
            self.button = Button(action, "primary")
            self.button.clicked.connect(self.action_requested)
            layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self._retint()
        theme.manager().changed.connect(self._retint)

    def _retint(self) -> None:
        if self._icon_name is None:
            self._icon.hide()
            return
        size = theme.px(theme.ICON_RAIL)
        pixmap = icons.icon(self._icon_name, theme.tokens().text_muted).pixmap(size, size)
        self._icon.setPixmap(pixmap)
        self._icon.show()
