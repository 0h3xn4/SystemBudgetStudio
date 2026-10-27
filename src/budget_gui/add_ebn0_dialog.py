"""The form of *Add Eb/N0 entry* (D-200): the modulation and the coding of a new row of the
project's `config/ebn0_table.yaml`, nothing invented.

A link takes its modulation and coding from this table, and the Eb/N0 each pair requires comes
from a standard or a data sheet, so the form does not ask for it: the row is written with a
placeholder (source TBD) that is filled in **Model > Inputs**. The checks are those of
`budget_core.new_ebn0`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from budget_core.new_ebn0 import Ebn0Answers, check_ebn0
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button


class AddEbn0Dialog(QDialog):
    """Asks for the modulation and the coding; *Add entry* stays off until both are given and the
    pair is not in the table yet."""

    def __init__(
        self, existing_pairs: Sequence[tuple[str, str]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Eb/N0 entry")
        self._existing = list(existing_pairs)

        self.modulation_edit = QLineEdit()
        self.modulation_edit.setPlaceholderText("for example QPSK")
        self.modulation_edit.setAccessibleName("Modulation")
        self.coding_edit = QLineEdit()
        self.coding_edit.setPlaceholderText("for example rate 1/2, or none")
        self.coding_edit.setAccessibleName("Coding")

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Modulation", self.modulation_edit)
        form.addRow("Coding", self.coding_edit)

        self.intro = QLabel(
            "A link names a modulation and a coding, and the project's Eb/N0 table must list "
            "the pair. The Eb/N0 that the pair requires comes from a standard or a data sheet, "
            "so it is written as a placeholder (source TBD) and filled in under Model > Inputs; "
            "until then the link results that need it are not available. The text is compared "
            "exactly when a link is loaded: write it as the link will."
        )
        self.intro.setWordWrap(True)
        self.intro.setProperty("role", "muted")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button("Add entry", "primary")
        cancel = Button("Cancel")
        self.add_button.setDefault(True)
        self.add_button.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.gap(1))
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(self.intro)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        self.modulation_edit.textChanged.connect(self._refresh)
        self.coding_edit.textChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> Ebn0Answers:
        return Ebn0Answers(self.modulation_edit.text(), self.coding_edit.text())

    def issues(self) -> list[Issue]:
        return check_ebn0(self.answers(), existing_pairs=self._existing)

    def _refresh(self, *_args: object) -> None:
        issues = self.issues()
        started = bool(self.modulation_edit.text().strip() or self.coding_edit.text().strip())
        # say what is missing only once the user began, so the empty form is not an error
        self.error_label.setText(issues[0].message if issues and started else "")
        self.add_button.setEnabled(not issues)
