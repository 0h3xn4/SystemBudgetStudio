"""The Explain dock: how the value that was asked about was obtained (D-206).

It shows the title of the cell, its value, then each step with the equation, the inputs with units
and where each comes from, and the equations with their sources. The text is the one
`budget explain` prints. The panel is hidden until a value is explained, as the Inspector and the
Provenance panel are in the focused view.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from budget_core.explain import Explanation
from budget_gui import theme
from budget_gui.components import EmptyState

HINT = (
    "Select a value in a result table and choose Explain this value (Ctrl+Shift+I, or the "
    "right-click menu) to see its equation, its inputs and the steps."
)


class ExplainPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.title = QLabel("")
        self.title.setProperty("role", "title")
        self.title.setWordWrap(True)
        self.result = QLabel("")
        self.result.setFont(theme.mono_font())
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(theme.mono_font())
        self.text.setAccessibleName("How the value was obtained")
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.empty = EmptyState(HINT, icon="info")
        self.details = QWidget()
        details = QVBoxLayout(self.details)
        details.setContentsMargins(0, 0, 0, 0)
        details.addWidget(self.title)
        details.addWidget(self.result)
        details.addWidget(self.text, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(2, 1))
        layout.addWidget(self.empty)
        layout.addWidget(self.details, 1)
        self.clear()

    def clear(self) -> None:
        self.empty.setVisible(True)
        self.details.setVisible(False)
        self.empty.message.setText(HINT)
        self.text.clear()

    def show_message(self, message: str) -> None:
        """Say why nothing can be explained (a table that has no explanation yet, a cell that
        does not exist)."""
        self.empty.setVisible(True)
        self.details.setVisible(False)
        self.text.clear()
        self.empty.message.setText(message)

    def show_explanation(self, explanation: Explanation) -> None:
        self.empty.setVisible(False)
        self.details.setVisible(True)
        self.title.setText(explanation.title)
        self.result.setText(f"= {explanation.result.text()}")
        self.text.setPlainText(explanation.format_text())
        self.text.moveCursor(QTextCursor.MoveOperation.Start)
