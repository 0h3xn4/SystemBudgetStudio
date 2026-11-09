# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Help > Third-party licences: the licence texts of everything the installers contain."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from budget_core.about import third_party_text
from budget_gui import theme
from budget_gui.components import Button


class NoticesDialog(QDialog):
    """A read-only view of THIRD_PARTY_NOTICES.txt (installed copies) or a note where to find it."""

    def __init__(self, parent: QWidget | None = None, text: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Third-party licences")
        self.resize(*theme.scaled(theme.GUIDE_SIZE))
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setAccessibleName("Third-party licences")
        self.view.setFont(theme.mono_font())
        self.view.setPlainText(third_party_text() if text is None else text)
        close = Button("Close", "primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(self.view, 1)
        layout.addLayout(row)
