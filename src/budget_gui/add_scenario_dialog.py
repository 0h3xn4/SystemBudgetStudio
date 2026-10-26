"""The form of *Add orbit and scenario* (D-189, D-196): a name, an id, a near-circular or an
elliptical orbit, a start, a length (up to 180 days) and the spacecraft mode that is active.

The numbers (altitude, inclination, RAAN, start, length) start empty and the form does not accept
an empty one: an orbit with a made-up altitude would look like data. The checks are those of
`budget_core.new_scenario`.
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

from budget_core.new_scenario import ScenarioAnswers, check_scenario, id_from_name
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button


def _number(text: str) -> float | None:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


def _optional_number(text: str) -> float | None:
    """Empty is None (the answer is left out); text that is not a number is NaN, which the checks
    refuse, so a typing error is not taken for an empty answer."""
    if not text.strip():
        return None
    number = _number(text)
    return float("nan") if number is None else number


class AddScenarioDialog(QDialog):
    """Asks for the id, the name, the orbit, the start, the length and the default mode; *Add*
    stays off until every answer passes the checks."""

    def __init__(
        self,
        existing_scenario_ids: Sequence[str],
        existing_orbit_ids: Sequence[str],
        mode_ids: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add orbit and scenario")
        self._scenarios = list(existing_scenario_ids)
        self._orbits = list(existing_orbit_ids)
        self._modes = list(mode_ids)
        self._id_typed = False

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.altitude_edit = QLineEdit()
        self.altitude_edit.setPlaceholderText("km, for example 550")
        self.inclination_edit = QLineEdit()
        self.inclination_edit.setPlaceholderText("degrees, 0 to 180")
        self.raan_edit = QLineEdit()
        self.raan_edit.setPlaceholderText("degrees, 0 to 360")
        self.apogee_edit = QLineEdit()
        self.apogee_edit.setPlaceholderText("km, optional: empty for a near-circular orbit")
        self.arg_perigee_edit = QLineEdit()
        self.arg_perigee_edit.setPlaceholderText("degrees, 0 to 360, with an apogee altitude")
        self.arg_perigee_edit.setEnabled(False)  # it only has a meaning for an elliptical orbit
        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("UTC, for example 2026-06-01T00:00:00Z")
        self.duration_edit = QLineEdit()
        self.duration_edit.setPlaceholderText("days, for example 1")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(self._modes)
        rows = (
            ("Name", self.name_edit, "Scenario name"),
            ("Id", self.id_edit, "Scenario id (the file name)"),
            (
                "Altitude",
                self.altitude_edit,
                "Altitude of the orbit in kilometres (the perigee altitude if there is an apogee)",
            ),
            (
                "Apogee altitude",
                self.apogee_edit,
                "Apogee altitude in kilometres, optional: empty gives a near-circular orbit",
            ),
            (
                "Argument of perigee",
                self.arg_perigee_edit,
                "Argument of perigee in degrees, for an elliptical orbit",
            ),
            ("Inclination", self.inclination_edit, "Inclination of the orbit in degrees"),
            ("RAAN", self.raan_edit, "Right ascension of the ascending node in degrees"),
            ("Start", self.start_edit, "Start of the scenario, UTC"),
            ("Length", self.duration_edit, "Length of the scenario in days"),
            ("Spacecraft mode", self.mode_combo, "Spacecraft mode that is active the whole time"),
        )
        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        for label, widget, accessible in rows:
            widget.setAccessibleName(accessible)
            form.addRow(label, widget)

        intro = QLabel(
            "A scenario is a stretch of time on an orbit, up to 180 days, with one spacecraft mode "
            "the whole time. The orbit is near-circular from three numbers; give an apogee "
            "altitude (and an argument of perigee) for an elliptical one, which starts at "
            "perigee. Ground stations and rules are added afterwards in the scenario editor."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button("Add scenario", "primary")
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
            self.altitude_edit,
            self.inclination_edit,
            self.raan_edit,
            self.apogee_edit,
            self.arg_perigee_edit,
            self.start_edit,
            self.duration_edit,
        ):
            edit.textChanged.connect(self._refresh)
        self.mode_combo.currentIndexChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> ScenarioAnswers:
        return ScenarioAnswers(
            scenario_id=self.id_edit.text().strip(),
            name=self.name_edit.text().strip(),
            altitude_km=_number(self.altitude_edit.text()),
            inclination_deg=_number(self.inclination_edit.text()),
            raan_deg=_number(self.raan_edit.text()),
            start_utc=self.start_edit.text().strip(),
            duration_days=_number(self.duration_edit.text()),
            default_mode=self.mode_combo.currentText(),
            apogee_altitude_km=_optional_number(self.apogee_edit.text()),
            arg_perigee_deg=(
                _optional_number(self.arg_perigee_edit.text())
                if self.apogee_edit.text().strip()
                else None
            ),
        )

    def issues(self) -> list[Issue]:
        return check_scenario(
            self.answers(),
            existing_scenario_ids=self._scenarios,
            existing_orbit_ids=self._orbits,
            mode_ids=self._modes,
        )

    # ---- reacting to typing ------------------------------------------------------------------
    def _name_edited(self, text: str) -> None:
        if not self._id_typed:
            self.id_edit.setText(id_from_name(text))

    def _id_edited(self, _text: str) -> None:
        self._id_typed = True

    def _refresh(self, *_args: object) -> None:
        self.arg_perigee_edit.setEnabled(bool(self.apogee_edit.text().strip()))
        issues = self.issues()
        started = any(
            edit.text().strip()
            for edit in (
                self.name_edit,
                self.id_edit,
                self.altitude_edit,
                self.inclination_edit,
                self.raan_edit,
                self.start_edit,
                self.duration_edit,
            )
        )
        # a missing spacecraft mode is said at once; the rest only once the user began typing
        shown = [i for i in issues if i.field == "default_mode" and not self._modes or started]
        self.error_label.setText(shown[0].message if shown else "")
        self.add_button.setEnabled(not issues)
