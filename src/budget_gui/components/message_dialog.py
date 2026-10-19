"""The message dialog: for confirmations of something that cannot be undone and for refusals that
need an answer (D-169). Everything else is inline, a toast or the Problems panel.

`ask` replaces `QMessageBox.question`, `inform` replaces `QMessageBox.information`: a title, one
sentence, a primary button and (for a question) a secondary one. A destructive primary is red and
the secondary one has the focus, so Enter never destroys.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from budget_gui import icons, theme
from budget_gui.components.buttons import Button
from budget_gui.theme import Level

_ICONS = {
    Level.CRITICAL: "circle-x",
    Level.CAUTION: "triangle-alert",
    Level.STANDBY: "info",
    Level.NORMAL: "circle-check",
}


class MessageDialog(QDialog):
    def __init__(
        self,
        title: str,
        text: str,
        *,
        primary: str = "OK",
        secondary: str | None = None,
        destructive: bool = False,
        level: Level = Level.STANDBY,
        detail: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setProperty("role", "raised")
        self.setMinimumWidth(theme.px(theme.PALETTE_SIZE[0] - 2 * theme.PALETTE_SIZE[0] // 5))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        top = QHBoxLayout()
        top.setSpacing(theme.gap(2))
        self.icon_label = QLabel()
        size = theme.px(theme.ICON_RAIL)
        self.icon_label.setPixmap(
            icons.icon(_ICONS.get(level, "info"), theme.tokens().level(level).fg).pixmap(size, size)
        )
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(theme.gap(0))
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "title")
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.title_label)
        body.addWidget(self.text_label)
        if detail:
            self.detail_label = QLabel(detail)
            self.detail_label.setProperty("role", "small")
            self.detail_label.setWordWrap(True)
            body.addWidget(self.detail_label)
        top.addWidget(self.icon_label)
        top.addLayout(body, 1)
        layout.addLayout(top)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.gap(1))
        buttons.addStretch(1)
        self.secondary_button: Button | None = None
        if secondary is not None:
            self.secondary_button = Button(secondary, "secondary")
            self.secondary_button.clicked.connect(self.reject)
            buttons.addWidget(self.secondary_button)
        self.primary_button = Button(primary, "danger" if destructive else "primary")
        self.primary_button.clicked.connect(self.accept)
        buttons.addWidget(self.primary_button)
        layout.addLayout(buttons)
        (
            self.secondary_button if destructive and self.secondary_button else self.primary_button
        ).setFocus()
        (
            self.secondary_button if destructive and self.secondary_button else self.primary_button
        ).setDefault(True)

    def ask(self) -> bool:
        """Show it and wait: True when the primary button was chosen."""
        return self.exec() == QDialog.DialogCode.Accepted


def ask(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    primary: str = "OK",
    secondary: str = "Cancel",
    destructive: bool = False,
    detail: str = "",
) -> bool:
    """A question with two answers; True for the primary one."""
    level = Level.CAUTION if destructive else Level.STANDBY
    dialog = MessageDialog(
        title,
        text,
        primary=primary,
        secondary=secondary,
        destructive=destructive,
        level=level,
        detail=detail,
        parent=parent,
    )
    return dialog.ask()


def inform(
    parent: QWidget | None, title: str, text: str, *, level: Level = Level.STANDBY, detail: str = ""
) -> None:
    """A message with one button."""
    MessageDialog(title, text, level=level, detail=detail, parent=parent).exec()
