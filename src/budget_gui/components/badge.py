"""A status badge: an icon and a word in the colour of a level, never colour alone (D-169)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from budget_gui import icons, theme
from budget_gui.theme import Level


class StatusBadge(QWidget):
    """`critical`, `serious`, `caution`, `normal`, `standby` or `off`, with the text it carries."""

    def __init__(self, level: Level = Level.OFF, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._level = level
        self._icon = QLabel()
        self._label = QLabel(text)
        for label in (self._icon, self._label):
            label.setProperty("role", "badge")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.gap(0))
        row.addWidget(self._icon)
        row.addWidget(self._label)
        self.set_level(level, text)
        theme.manager().changed.connect(self._retint)

    @property
    def level(self) -> Level:
        return self._level

    def text(self) -> str:
        return self._label.text()

    def set_level(self, level: Level, text: str | None = None) -> None:
        self._level = level
        if text is not None:
            self._label.setText(text)
        for label in (self._icon, self._label):
            label.setProperty("level", level.value)
            label.style().unpolish(label)
            label.style().polish(label)
        self._retint()
        self.setAccessibleName(f"{level.value}: {self._label.text()}")

    def _retint(self) -> None:
        colour = theme.tokens().level(self._level).fg
        size = theme.px(theme.ICON_UI)
        pixmap = icons.icon(theme.LEVEL_ICONS[self._level], colour).pixmap(size, size)
        self._icon.setPixmap(pixmap)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
