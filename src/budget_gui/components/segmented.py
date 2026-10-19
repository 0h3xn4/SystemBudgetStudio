"""A segmented control: a few choices side by side, one chosen (D-169)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QFrame):
    """`choices` are (key, text) pairs; `changed` carries the key that was chosen."""

    changed = Signal(str)

    def __init__(
        self,
        choices: Sequence[tuple[str, str]],
        *,
        current: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "segmented")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)  # the style sheet gives the frame its padding
        row.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, text in choices:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setProperty("kind", "ghost")
            button.setProperty("size", "compact")
            self._group.addButton(button)
            row.addWidget(button)
            self._buttons[key] = button
            button.clicked.connect(self._clicked)
        first = current if current in self._buttons else next(iter(self._buttons), None)
        if first is not None:
            self._buttons[first].setChecked(True)

    def _clicked(self) -> None:
        self.changed.emit(self.current())

    def current(self) -> str:
        return next((k for k, b in self._buttons.items() if b.isChecked()), "")

    def set_current(self, key: str) -> None:
        if key in self._buttons and key != self.current():
            self._buttons[key].setChecked(True)
            self.changed.emit(key)

    def button(self, key: str) -> QPushButton:
        return self._buttons[key]
