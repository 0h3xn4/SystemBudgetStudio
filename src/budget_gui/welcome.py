"""The first screen, before a project is open (D-166).

Two actions and one gesture, nothing else: open a project folder, start a new project with the
guided steps, or drop a project folder on the window. There is no list of recent projects: the
tool keeps no path of the user's projects (D-150, `privacy.py`).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from budget_core import APP_NAME


class WelcomePage(QWidget):
    open_requested = Signal()
    new_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        title = QLabel(APP_NAME)
        title.setProperty("role", "heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lead = QLabel(
            "Power, mass, thermal and link budgets of one spacecraft model. "
            "Everything stays on this computer."
        )
        lead.setProperty("role", "muted")
        lead.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lead.setWordWrap(True)
        self.open_button = QPushButton("Open a project folder…")
        self.new_button = QPushButton("New project (guided)…")
        self.new_button.setProperty("kind", "secondary")
        self.open_button.clicked.connect(self.open_requested)
        self.new_button.clicked.connect(self.new_requested)
        hint = QLabel("or drop a project folder on this window")
        hint.setProperty("role", "muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        keys = QLabel("Ctrl+O open · Ctrl+N new · Ctrl+K find a command · F1 user guide")
        keys.setProperty("role", "muted")
        keys.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.new_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(14)
        layout.addStretch(2)
        layout.addWidget(title)
        layout.addWidget(lead)
        layout.addSpacing(8)
        layout.addLayout(buttons)
        layout.addWidget(hint)
        layout.addStretch(3)
        layout.addWidget(keys)
