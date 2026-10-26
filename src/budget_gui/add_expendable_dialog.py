"""The form of *Add expendable* (D-197): the answers a new expendable needs, none of them invented.

An expendable (propellant, an oxidizer, a pressurant, a consumable, jettisoned equipment) has a
mass in every mission phase of the spacecraft, so the form has one mass field per phase (write 0 if
the item is not on board then). The numbers start empty and the form does not accept an empty one;
the position of the centre of mass is optional, but all three coordinates or none. The id is
suggested from the name until it is typed by hand. The checks are those of
`budget_core.new_expendable`.
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

from budget_core.new_expendable import ExpendableAnswers, check_expendable, id_from_name
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button


def _number(text: str) -> float | None:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


def _optional_number(text: str) -> float | None:
    """Empty is None (left out); text that is not a number is NaN, which the checks refuse, so a
    typing error is not taken for an empty answer."""
    if not text.strip():
        return None
    number = _number(text)
    return float("nan") if number is None else number


class AddExpendableDialog(QDialog):
    """Asks for the id, the name, the subsystem, the maturity class, a mass per mission phase and
    optionally the position of the centre of mass; *Add expendable* stays off until every answer
    passes the checks."""

    def __init__(
        self,
        existing_ids: Sequence[str],
        classes: Sequence[str],
        phases: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add expendable")
        self._existing = list(existing_ids)
        self._classes = list(classes)
        self._phases = list(phases)
        self._id_typed = False

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.subsystem_edit = QLineEdit()
        self.maturity_combo = QComboBox()
        self.maturity_combo.addItems(self._classes)
        self.mass_edits: dict[str, QLineEdit] = {}
        for phase in self._phases:
            edit = QLineEdit()
            edit.setPlaceholderText("kg (0 if not on board)")
            edit.setAccessibleName(f"Mass in kilograms in the phase {phase}")
            self.mass_edits[phase] = edit
        self.x_edit, self.y_edit, self.z_edit = QLineEdit(), QLineEdit(), QLineEdit()
        for axis, edit in (("x", self.x_edit), ("y", self.y_edit), ("z", self.z_edit)):
            edit.setPlaceholderText(f"{axis}, m")
            edit.setAccessibleName(f"Centre of mass {axis} coordinate in metres, optional")
        for widget, label in (
            (self.name_edit, "Expendable name"),
            (self.id_edit, "Expendable id (the file name)"),
            (self.subsystem_edit, "Subsystem"),
            (self.maturity_combo, "Maturity class"),
        ):
            widget.setAccessibleName(label)

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Name", self.name_edit)
        form.addRow("Id", self.id_edit)
        form.addRow("Subsystem", self.subsystem_edit)
        form.addRow("Maturity", self.maturity_combo)
        for phase, edit in self.mass_edits.items():
            form.addRow(f"Mass in {phase}", edit)
        position = QHBoxLayout()
        position.setSpacing(theme.gap(1))
        for edit in (self.x_edit, self.y_edit, self.z_edit):
            position.addWidget(edit)
        form.addRow("Centre of mass (optional)", position)

        intro = QLabel(
            "An expendable is propellant, an oxidizer, a pressurant, a consumable or equipment "
            "that is jettisoned: its mass differs per mission phase. A bipropellant is two "
            "expendables, fuel and oxidizer, added one after the other. The position of the "
            "centre of mass (body frame, metres) is optional: all three coordinates or none."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button("Add expendable", "primary")
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
        for edit in (
            self.name_edit,
            self.id_edit,
            self.subsystem_edit,
            *self.mass_edits.values(),
            self.x_edit,
            self.y_edit,
            self.z_edit,
        ):
            edit.textChanged.connect(self._refresh)
        self.maturity_combo.currentIndexChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> ExpendableAnswers:
        coordinates = tuple(
            _optional_number(edit.text()) for edit in (self.x_edit, self.y_edit, self.z_edit)
        )
        given = any(c is not None for c in coordinates)
        return ExpendableAnswers(
            expendable_id=self.id_edit.text(),
            name=self.name_edit.text(),
            subsystem=self.subsystem_edit.text(),
            maturity=self.maturity_combo.currentText(),
            masses_kg={phase: _number(edit.text()) for phase, edit in self.mass_edits.items()},
            position=(coordinates[0], coordinates[1], coordinates[2]) if given else None,
        )

    def issues(self) -> list[Issue]:
        return check_expendable(
            self.answers(),
            existing_ids=self._existing,
            classes=self._classes,
            phases=self._phases,
        )

    # ---- reacting to typing ------------------------------------------------------------------
    def _name_edited(self, text: str) -> None:
        if not self._id_typed:
            self.id_edit.setText(id_from_name(text))

    def _id_edited(self, _text: str) -> None:
        self._id_typed = True

    def _refresh(self, *_args: object) -> None:
        issues = self.issues()
        started = any(
            edit.text().strip()
            for edit in (
                self.name_edit,
                self.subsystem_edit,
                *self.mass_edits.values(),
                self.x_edit,
                self.y_edit,
                self.z_edit,
            )
        )
        # say what is missing only once the user began, so the empty form is not a wall of errors
        self.error_label.setText(issues[0].message if issues and started else "")
        self.add_button.setEnabled(not issues)
