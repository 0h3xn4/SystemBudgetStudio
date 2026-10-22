"""The form of *Add spacecraft mode* (D-188): a name, an id, a description and where the
assignments start from.

A spacecraft mode says which power mode every unit is in. Asking for all of them here would be a
form with a row per unit (hundreds, in a big project), so the mode starts from a copy of another
mode, or with every unit off, and the assignments are edited in the grid afterwards. The checks
are those of `budget_core.new_mode`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from budget_core.new_mode import ModeAnswers, check_mode, id_from_name
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button

FROM_OFF = ""  # the data of the first choice of "Start from"


class AddModeDialog(QDialog):
    """Asks for the id, the name, the description and the starting point; *Add mode* stays off
    until the answers pass the checks."""

    def __init__(
        self,
        existing_ids: Sequence[str],
        unit_ids: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add spacecraft mode")
        self._existing = list(existing_ids)
        self._units = list(unit_ids)
        self._id_typed = False

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.start_combo = QComboBox()
        self.start_combo.addItem("Every unit off (or in its first power mode)", FROM_OFF)
        for mode_id in self._existing:
            self.start_combo.addItem(f"A copy of {mode_id}", mode_id)
        for widget, label in (
            (self.name_edit, "Spacecraft mode name"),
            (self.id_edit, "Spacecraft mode id (the file name)"),
            (self.description_edit, "Description of the spacecraft mode"),
            (self.start_combo, "Where the assignments start from"),
        ):
            widget.setAccessibleName(label)
        self.description_edit.setPlaceholderText("optional")

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Name", self.name_edit)
        form.addRow("Id", self.id_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Start from", self.start_combo)

        intro = QLabel(
            "A spacecraft mode says which power mode each unit is in. The new mode starts from "
            "the choice below; change a unit's power mode in the grid afterwards."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button("Add mode", "primary")
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
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        self.name_edit.textEdited.connect(self._name_edited)
        self.id_edit.textEdited.connect(self._id_edited)
        for edit in (self.name_edit, self.id_edit, self.description_edit):
            edit.textChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> ModeAnswers:
        """`copy_of` is the id of the mode to copy the assignments of, "" for every unit off."""
        return ModeAnswers(
            mode_id=self.id_edit.text().strip(),
            name=self.name_edit.text().strip(),
            description=self.description_edit.text().strip(),
            copy_of=str(self.start_combo.currentData() or ""),
        )

    def issues(self) -> list[Issue]:
        return check_mode(
            self.id_edit.text(),
            self.name_edit.text(),
            self.description_edit.text(),
            existing_ids=self._existing,
            unit_ids=self._units,
        )

    # ---- reacting to typing ------------------------------------------------------------------
    def _name_edited(self, text: str) -> None:
        if not self._id_typed:
            self.id_edit.setText(id_from_name(text))

    def _id_edited(self, _text: str) -> None:
        self._id_typed = True

    def _refresh(self, *_args: object) -> None:
        issues = self.issues()
        started = bool(self.name_edit.text().strip() or self.id_edit.text().strip())
        # the missing unit is said at once; the rest only once the user began typing
        shown = [i for i in issues if i.field == "units" or started]
        self.error_label.setText(shown[0].message if shown else "")
        self.add_button.setEnabled(not issues)
