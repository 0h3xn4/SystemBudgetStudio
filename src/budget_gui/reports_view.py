"""The Reports tab. For now the exports of the File menu in one place; the full page (budgets x
formats, result list, provenance first) is step 5 of the redesign."""

from __future__ import annotations

from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ReportsView(QWidget):
    reports_requested = Signal()
    timeline_requested = Signal()
    scenario_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Reports")
        title.setProperty("role", "heading")
        intro = QLabel(
            "Write the budgets of the open project to a folder as XLSX, PDF, DOCX, CSV and JSON. "
            "Every file carries the provenance of the run (tool version, project, date)."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.reports_button = self._button("Export budget reports…", self.reports_requested)
        self.timeline_button = self._button("Export power timeline…", self.timeline_requested)
        self.scenario_button = self._button("Export scenario results…", self.scenario_requested)
        row = QHBoxLayout()
        for button in (self.reports_button, self.timeline_button, self.scenario_button):
            row.addWidget(button)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addStretch(1)

    @staticmethod
    def _button(text: str, signal: SignalInstance) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("kind", "secondary")
        button.clicked.connect(signal)
        return button
