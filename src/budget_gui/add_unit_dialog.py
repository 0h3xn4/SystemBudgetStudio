"""The form of *Add unit* (D-187): the answers a new unit needs, none of them invented.

The id is suggested from the name until it is typed by hand. The numbers (mass, the powers of the
first mode) start empty and the form does not accept an empty one: a unit with a made-up mass or
power would look like data. The checks are those of `budget_core.new_unit`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from budget_core.new_unit import UnitAnswers, check_unit, id_from_name
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button


def _number(text: str) -> float | None:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


class AddUnitDialog(QDialog):
    """Asks for the id, the name, the subsystem, the bus, the maturity class, the mass and the
    first power mode; *Add unit* stays off until every answer passes the checks."""

    def __init__(
        self,
        existing_ids: Sequence[str],
        buses: Sequence[str],
        classes: Sequence[str],
        parent: QWidget | None = None,
        thermal_nodes: Sequence[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add unit")
        self._existing = list(existing_ids)
        self._buses = list(buses)
        self._classes = list(classes)
        self._nodes = None if thermal_nodes is None else list(thermal_nodes)
        self._id_typed = False

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.subsystem_edit = QLineEdit()
        if self._nodes:  # the thermal model names the subsystems a unit can be in
            self.subsystem_edit.setCompleter(QCompleter(self._nodes, self.subsystem_edit))
        self.bus_combo = QComboBox()
        self.bus_combo.addItems(self._buses)
        self.maturity_combo = QComboBox()
        self.maturity_combo.addItems(self._classes)
        self.mass_edit = QLineEdit()
        self.mass_edit.setPlaceholderText("kg")
        self.mode_edit = QLineEdit()
        self.mode_edit.setPlaceholderText("for example nominal")
        self.avg_edit = QLineEdit()
        self.avg_edit.setPlaceholderText("W")
        self.peak_edit = QLineEdit()
        self.peak_edit.setPlaceholderText("W")
        for widget, label in (
            (self.name_edit, "Unit name"),
            (self.id_edit, "Unit id (the file name)"),
            (self.subsystem_edit, "Subsystem"),
            (self.bus_combo, "Bus"),
            (self.maturity_combo, "Maturity class"),
            (self.mass_edit, "Mass in kilograms"),
            (self.mode_edit, "Name of the first power mode"),
            (self.avg_edit, "Average power of the mode in watts"),
            (self.peak_edit, "Peak power of the mode in watts"),
        ):
            widget.setAccessibleName(label)

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Name", self.name_edit)
        form.addRow("Id", self.id_edit)
        form.addRow("Subsystem", self.subsystem_edit)
        form.addRow("Bus", self.bus_combo)
        form.addRow("Maturity", self.maturity_combo)
        form.addRow("Mass", self.mass_edit)
        form.addRow("First power mode", self.mode_edit)
        form.addRow("Average power", self.avg_edit)
        form.addRow("Peak power", self.peak_edit)

        intro = QLabel(
            "A unit needs a mass and at least one power mode. Give the numbers you have; "
            "more modes, limits and the rest are edited in the grids afterwards."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button("Add unit", "primary")
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
            self.mass_edit,
            self.mode_edit,
            self.avg_edit,
            self.peak_edit,
        ):
            edit.textChanged.connect(self._refresh)
        for combo in (self.bus_combo, self.maturity_combo):
            combo.currentIndexChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> UnitAnswers:
        return UnitAnswers(
            unit_id=self.id_edit.text(),
            name=self.name_edit.text(),
            subsystem=self.subsystem_edit.text(),
            bus=self.bus_combo.currentText(),
            maturity=self.maturity_combo.currentText(),
            mass_kg=_number(self.mass_edit.text()),
            mode_name=self.mode_edit.text(),
            avg_power_w=_number(self.avg_edit.text()),
            peak_power_w=_number(self.peak_edit.text()),
        )

    def issues(self) -> list[Issue]:
        return check_unit(
            self.answers(),
            existing_ids=self._existing,
            buses=self._buses,
            classes=self._classes,
            thermal_nodes=self._nodes,
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
                self.mass_edit,
                self.mode_edit,
                self.avg_edit,
                self.peak_edit,
            )
        )
        # say what is missing only once the user began, so the empty form is not a wall of errors
        self.error_label.setText(issues[0].message if issues and started else "")
        self.add_button.setEnabled(not issues)
