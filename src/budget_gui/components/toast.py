"""Toasts: short, non-modal confirmations that go away by themselves (D-169).

A toast says that something worked ("Saved", "Exported 3 files"). It never carries a problem: a
problem is persistent and lives in the Problems panel. The toast sits at the bottom right of its
window, rises into place in 120 ms (not at all when motion is reduced) and a new one replaces the
one before it.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QWidget

from budget_gui import icons, theme

SHOWN_MS = 4000


class Toast(QFrame):
    """One toast, parented to the window it is shown in."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setProperty("role", "raised")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row = QHBoxLayout(self)
        row.setContentsMargins(*theme.inset(2, 1))
        row.setSpacing(theme.gap(1))
        self._icon = QLabel()
        self._text = QLabel()
        row.addWidget(self._icon)
        row.addWidget(self._text, 1)
        self._shadow = QGraphicsDropShadowEffect(self)  # floating elements, and only they, have one
        self._shadow.setBlurRadius(theme.gap(3))
        self._shadow.setOffset(0, theme.gap(0))
        self.setGraphicsEffect(self._shadow)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._animation: QPropertyAnimation | None = None
        self.hide()

    def text(self) -> str:
        return self._text.text()

    def show_message(self, text: str, icon: str = "circle-check", ms: int = SHOWN_MS) -> None:
        self._text.setText(text)
        size = theme.px(theme.ICON_UI)
        self._icon.setPixmap(icons.icon(icon, theme.tokens().normal.fg).pixmap(size, size))
        self._shadow.setColor(QColor(theme.tokens().shadow))
        self.setAccessibleName(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            return
        margin = theme.gap(3)
        end = QPoint(
            parent.width() - self.width() - margin, parent.height() - self.height() - margin
        )
        self.move(end)
        self.raise_()
        self.show()
        duration = theme.manager().motion_ms(0)
        if duration:
            animation = QPropertyAnimation(self, QByteArray(b"pos"), self)
            animation.setDuration(duration)
            animation.setStartValue(end + QPoint(0, theme.gap(1)))
            animation.setEndValue(end)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._animation = animation
            animation.start()
        self._timer.start(ms)
