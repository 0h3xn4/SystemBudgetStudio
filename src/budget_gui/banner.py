"""A banner under the top bar: a state of the results that must not go unnoticed.

Two are used: *stale* (the tables show the last results that worked, from before an error) and
*failed* (the last run did not finish). A banner has an icon, a sentence and one action, and it
stays until the state is gone; it is not a dialog and it does not go away by itself.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from budget_gui import icons, theme

ICON = {"stale": "triangle-alert", "failed": "circle-x"}


class Banner(QFrame):
    action_requested = Signal()

    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind
        self.setProperty("role", "banner-bar")
        self.setProperty("kind", kind)
        self._icon = QLabel()
        self._icon.setFixedSize(theme.px(theme.ICON_UI), theme.px(theme.ICON_UI))
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.action_button = QPushButton()
        self.action_button.setProperty("kind", "link")
        self.action_button.setFlat(True)
        self.action_button.clicked.connect(self.action_requested)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3, 1))
        layout.setSpacing(theme.gap(1))
        layout.addWidget(self._icon)
        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.action_button)
        self.setVisible(False)
        theme.manager().changed.connect(self._retint)

    def show_message(self, text: str, action: str = "") -> None:
        self.text_label.setText(text)
        self.action_button.setText(action)
        self.action_button.setVisible(bool(action))
        self._retint()
        self.setVisible(True)

    def clear(self) -> None:
        self.setVisible(False)

    def _retint(self) -> None:
        colour, _tint = theme.banner_colours(theme.tokens(), self.kind)
        self._icon.setPixmap(icons.icon(ICON[self.kind], colour).pixmap(18, 18))
