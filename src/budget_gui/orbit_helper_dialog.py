"""The orbit helper (2.2.0, D-228): from a local time of the ascending node, a sun-synchronous
request or a repeat ground track to the elements an orbit file takes.

The numbers come from `budget_core.orbit_design`; the dialog only asks, shows what was derived and
says in words when a request has no solution. With a list of orbits it writes to one of them; with
none (opened from the *Add scenario* form) it hands the values over.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.orbit_design import (
    OrbitDesignError,
    design_sun_synchronous,
    j2_secular_rates,
    mean_solar_time_of_node_h,
    raan_from_ltan_deg,
    repeat_ground_track,
)
from budget_core.timeutil import parse_utc
from budget_gui import theme
from budget_gui.components import Button


@dataclass(frozen=True)
class OrbitHelperValues:
    """What the helper derived: the elements to write, and the words that say how."""

    epoch_utc: str
    altitude_km: float
    semi_major_axis_m: float
    eccentricity: float
    inclination_deg: float
    raan_deg: float | None  # None: no local time given, the node is left as it is
    note: str  # for the provenance of the inputs it sets


def _number(text: str) -> float | None:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


def _local_time_h(text: str) -> float | None:
    text = text.strip()
    try:
        if ":" in text:
            hours_text, _, minutes_text = text.partition(":")
            hours, minutes = float(hours_text), float(minutes_text)
            if not 0.0 <= minutes < 60.0:
                return None
            value = hours + minutes / 60.0
        else:
            value = float(text)
    except ValueError:
        return None
    return value if 0.0 <= value < 24.0 else None


def _clock(hours: float) -> str:
    total = round(hours * 60.0) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


class OrbitHelperDialog(QDialog):
    MODE_SSO, MODE_REPEAT, MODE_LTAN = 0, 1, 2

    def __init__(
        self,
        orbit_ids: Sequence[str],
        parent: QWidget | None = None,
        *,
        epoch: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Orbit helper")
        self._values: OrbitHelperValues | None = None

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(
            [
                "Sun-synchronous orbit (altitude and local time of the node)",
                "Repeat ground track (revolutions in days)",
                "Local time of the node of a given orbit (altitude and inclination)",
            ]
        )
        self.mode_combo.setAccessibleName("What the orbit is asked for")
        self.epoch_edit = QLineEdit(epoch)
        self.epoch_edit.setPlaceholderText("UTC, for example 2026-06-01T00:00:00Z")
        self.epoch_edit.setAccessibleName("Epoch of the elements, UTC")
        self.earth_combo = QComboBox()
        self.earth_combo.addItems(sorted(EARTH_MODELS))
        self.earth_combo.setCurrentText(DEFAULT_EARTH_MODEL)
        self.earth_combo.setAccessibleName("Earth constants")
        self.altitude_edit = QLineEdit()
        self.altitude_edit.setPlaceholderText("km, for example 600")
        self.altitude_edit.setAccessibleName("Altitude in kilometres")
        self.inclination_edit = QLineEdit()
        self.inclination_edit.setPlaceholderText("degrees")
        self.inclination_edit.setAccessibleName("Inclination in degrees")
        self.ltan_edit = QLineEdit()
        self.ltan_edit.setPlaceholderText("HH:MM or hours, mean local solar time")
        self.ltan_edit.setAccessibleName("Local time of the ascending node")
        self.revolutions_edit = QLineEdit()
        self.revolutions_edit.setPlaceholderText("N, for example 15")
        self.revolutions_edit.setAccessibleName("Revolutions of the repeat cycle")
        self.days_edit = QLineEdit()
        self.days_edit.setPlaceholderText("D, for example 1")
        self.days_edit.setAccessibleName("Days of the repeat cycle")
        self.sso_check = QCheckBox("Sun-synchronous")
        self.sso_check.setChecked(True)
        self.eccentricity_edit = QLineEdit("0")
        self.eccentricity_edit.setAccessibleName("Eccentricity")

        self._rows: dict[str, tuple[QLabel, QWidget]] = {}
        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        for key, label, widget in (
            ("mode", "Ask for", self.mode_combo),
            ("epoch", "Epoch", self.epoch_edit),
            ("earth", "Earth constants", self.earth_combo),
            ("altitude", "Altitude", self.altitude_edit),
            ("inclination", "Inclination", self.inclination_edit),
            ("revolutions", "Revolutions", self.revolutions_edit),
            ("days", "Days", self.days_edit),
            ("sso", "", self.sso_check),
            ("ltan", "Local time of the node", self.ltan_edit),
            ("eccentricity", "Eccentricity", self.eccentricity_edit),
        ):
            caption = QLabel(label)
            form.addRow(caption, widget)
            self._rows[key] = (caption, widget)

        intro = QLabel(
            "Derives the elements an orbit needs from what a mission is usually described by. The "
            "local time is the mean local solar time of the ascending node; the relations are "
            "first-order J2 (see Models: orbit design). The elements are mean elements."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setAccessibleName("Derived orbit")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")

        self.orbit_combo = QComboBox()
        self.orbit_combo.addItems(list(orbit_ids))
        self.orbit_combo.setAccessibleName("Orbit to write to")
        self.apply_button = Button("Write to orbit" if orbit_ids else "Use these values", "primary")
        self.apply_button.setDefault(True)
        cancel = Button("Cancel")
        self.apply_button.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.gap(1))
        if orbit_ids:
            buttons.addWidget(QLabel("Orbit"))
            buttons.addWidget(self.orbit_combo)
        else:
            self.orbit_combo.setVisible(False)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.apply_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.result_label)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        self.mode_combo.currentIndexChanged.connect(self._refresh)
        self.earth_combo.currentIndexChanged.connect(self._refresh)
        self.sso_check.toggled.connect(self._refresh)
        for edit in (
            self.epoch_edit,
            self.altitude_edit,
            self.inclination_edit,
            self.ltan_edit,
            self.revolutions_edit,
            self.days_edit,
            self.eccentricity_edit,
        ):
            edit.textChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    # ---- the answers -------------------------------------------------------------------------
    def values(self) -> OrbitHelperValues | None:
        return self._values

    def target_orbit(self) -> str:
        return self.orbit_combo.currentText()

    # ---- working it out ----------------------------------------------------------------------
    def _show_rows(self) -> None:
        mode = self.mode_combo.currentIndex()
        visible = {
            "mode",
            "epoch",
            "earth",
            "ltan",
            "eccentricity",
            *({"altitude"} if mode in (self.MODE_SSO, self.MODE_LTAN) else set()),
            *({"inclination"} if mode == self.MODE_LTAN else set()),
            *({"revolutions", "days", "sso"} if mode == self.MODE_REPEAT else set()),
        }
        if mode == self.MODE_REPEAT and not self.sso_check.isChecked():
            visible.add("inclination")
        for key, (caption, widget) in self._rows.items():
            caption.setVisible(key in visible)
            widget.setVisible(key in visible)

    def _typed(self) -> bool:
        return any(
            edit.text().strip()
            for edit in (
                self.epoch_edit,
                self.altitude_edit,
                self.inclination_edit,
                self.ltan_edit,
                self.revolutions_edit,
                self.days_edit,
            )
        )

    def _refresh(self, *_args: object) -> None:
        self._show_rows()
        self._values = None
        self.result_label.setText("")
        message = ""
        try:
            self._values, text = self._derive()
            self.result_label.setText(text)
        except OrbitDesignError as exc:
            message = str(exc)
        except _IncompleteError:
            message = ""
        self.error_label.setText(message if self._typed() else "")
        self.apply_button.setEnabled(self._values is not None)

    def _epoch(self) -> datetime:
        text = self.epoch_edit.text().strip()
        if not text:
            raise _IncompleteError
        try:
            return parse_utc(text).astimezone(UTC)
        except ValueError:
            raise OrbitDesignError(
                "The epoch is a UTC time such as 2026-06-01T00:00:00Z."
            ) from None

    def _local_time(self, required: bool) -> float | None:
        text = self.ltan_edit.text().strip()
        if not text:
            if required:
                raise _IncompleteError
            return None
        hours = _local_time_h(text)
        if hours is None:
            raise OrbitDesignError("The local time is HH:MM or decimal hours, from 0 up to 24.")
        return hours

    def _number(self, edit: QLineEdit) -> float:
        text = edit.text().strip()
        if not text:
            raise _IncompleteError
        value = _number(text)
        if value is None:
            raise OrbitDesignError(f"'{edit.accessibleName()}' is a number.")
        return value

    def _derive(self) -> tuple[OrbitHelperValues, str]:
        mode = self.mode_combo.currentIndex()
        earth = self.earth_combo.currentText()
        radius = EARTH_MODELS[earth].radius_m
        e = self._number(self.eccentricity_edit)
        epoch = self._epoch()
        epoch_text = self.epoch_edit.text().strip()
        raan: float | None
        hours: float | None
        if mode == self.MODE_SSO:
            altitude_m = self._number(self.altitude_edit) * 1000.0
            hours = self._local_time(required=True)
            assert hours is not None
            design = design_sun_synchronous(
                altitude_m=altitude_m, ltan_h=hours, epoch=epoch, eccentricity=e, earth_model=earth
            )
            inclination, raan = design.inclination_deg, design.raan_deg
            period = design.nodal_period_s
            note = (
                f"sun-synchronous at {altitude_m / 1000.0:g} km, ascending node at "
                f"{_clock(hours)} mean local solar time on {epoch_text}"
            )
            extra = ""
        elif mode == self.MODE_REPEAT:
            revolutions = round(self._number(self.revolutions_edit))
            days = round(self._number(self.days_edit))
            if self.sso_check.isChecked():
                solution = repeat_ground_track(
                    revolutions, days, eccentricity=e, sun_synchronous=True, earth_model=earth
                )
            else:
                solution = repeat_ground_track(
                    revolutions,
                    days,
                    eccentricity=e,
                    inclination_deg=self._number(self.inclination_edit),
                    earth_model=earth,
                )
            altitude_m, inclination = solution.altitude_m, solution.inclination_deg
            period = solution.nodal_period_s
            hours = self._local_time(required=False)
            raan = None if hours is None else raan_from_ltan_deg(hours, epoch)
            plural = "s" if days != 1 else ""
            note = f"repeat ground track, {revolutions} revolutions in {days} day{plural}" + (
                ", sun-synchronous" if solution.sun_synchronous else ""
            )
            extra = f"Track spacing at the equator: {solution.track_spacing_km:.0f} km. "
        else:
            altitude_m = self._number(self.altitude_edit) * 1000.0
            inclination = self._number(self.inclination_edit)
            hours = self._local_time(required=True)
            assert hours is not None
            a = radius + altitude_m
            period = j2_secular_rates(a, e, inclination, earth).nodal_period_s
            raan = raan_from_ltan_deg(hours, epoch)
            note = (
                f"ascending node at {_clock(hours)} mean local solar time on {epoch_text}, "
                f"altitude {altitude_m / 1000.0:g} km"
            )
            extra = ""
        a = radius + altitude_m
        lines = [
            f"Altitude {altitude_m / 1000.0:.3f} km, semi-major axis {a / 1000.0:.3f} km, "
            f"inclination {inclination:.4f} deg"
        ]
        if raan is not None:
            lines.append(
                f"RAAN {raan:.4f} deg at {epoch_text}; ascending node "
                f"{_clock(mean_solar_time_of_node_h(raan, epoch))}, descending node "
                f"{_clock(mean_solar_time_of_node_h(raan, epoch) + 12.0)} (mean local solar time)"
            )
        else:
            lines.append("No local time given: the node of the orbit is left as it is.")
        lines.append(f"{extra}Nodal period {period / 60.0:.3f} min.")
        if mode == self.MODE_REPEAT:
            lines.insert(0, f"{revolutions} revolutions in {days} day{'s' if days != 1 else ''}.")
        values = OrbitHelperValues(
            epoch_text, altitude_m / 1000.0, a, e, inclination, raan, "Orbit helper: " + note
        )
        return values, "\n".join(lines)


class _IncompleteError(Exception):
    """An answer is still missing: nothing is said until the user has typed something."""
