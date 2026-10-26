"""The form of *Add ground station* and *Add imaging target* (D-198): the answers a new site needs,
none of them invented.

Both are a point on the ground: a name, an id (the file name, suggested from the name until it is
typed by hand), the latitude and longitude in degrees, the altitude in metres and the minimum
elevation in degrees. The four numbers start empty and the form does not accept an empty one or text
that is not a number. The checks are those of `budget_core.new_site`.
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

from budget_core.new_site import GROUND_STATION, SiteAnswers, check_site, id_from_name
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button


def _optional_number(text: str) -> float | None:
    """Empty is None (the checks name it); text that is not a number is NaN, which the checks
    refuse, so a typing error is not taken for an empty answer."""
    if not text.strip():
        return None
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return float("nan")


class AddSiteDialog(QDialog):
    """Asks for the name, the id and the four numbers of a ground station or an imaging target;
    the Add button stays off until every answer passes the checks."""

    def __init__(
        self, kind: str, existing_ids: Sequence[str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._existing = list(existing_ids)
        self._id_typed = False
        noun = "ground station" if kind == GROUND_STATION else "imaging target"
        self.setWindowTitle(f"Add {noun}")

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.latitude_edit = QLineEdit()
        self.longitude_edit = QLineEdit()
        self.altitude_edit = QLineEdit()
        self.elevation_edit = QLineEdit()
        for edit, label, hint in (
            (self.name_edit, f"Name of the {noun}", ""),
            (self.id_edit, f"Id of the {noun} (the file name)", ""),
            (self.latitude_edit, "Latitude in degrees", "−90 to 90"),
            (self.longitude_edit, "Longitude in degrees", "−180 to 180"),
            (self.altitude_edit, "Altitude in metres", "m above the ellipsoid"),
            (self.elevation_edit, "Minimum elevation in degrees", "0 to below 90"),
        ):
            edit.setAccessibleName(label)
            if hint:
                edit.setPlaceholderText(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Name", self.name_edit)
        form.addRow("Id", self.id_edit)
        form.addRow("Latitude, °", self.latitude_edit)
        form.addRow("Longitude, °", self.longitude_edit)
        form.addRow("Altitude, m", self.altitude_edit)
        form.addRow("Minimum elevation, °", self.elevation_edit)

        what = (
            "A ground station is a link peer and a place where a scenario rule can start a mode "
            "during a pass."
            if kind == GROUND_STATION
            else "An imaging target is a point on the ground whose passes count for imaging."
        )
        intro = QLabel(f"{what} A scenario uses it once its id is listed in the scenario's sites.")
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button(f"Add {noun}", "primary")
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
        for edit in self._edits():
            edit.textChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    def _edits(self) -> tuple[QLineEdit, ...]:
        return (
            self.name_edit,
            self.id_edit,
            self.latitude_edit,
            self.longitude_edit,
            self.altitude_edit,
            self.elevation_edit,
        )

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> SiteAnswers:
        return SiteAnswers(
            kind=self._kind,
            site_id=self.id_edit.text(),
            name=self.name_edit.text(),
            latitude_deg=_optional_number(self.latitude_edit.text()),
            longitude_deg=_optional_number(self.longitude_edit.text()),
            altitude_m=_optional_number(self.altitude_edit.text()),
            min_elevation_deg=_optional_number(self.elevation_edit.text()),
        )

    def issues(self) -> list[Issue]:
        return check_site(self.answers(), existing_ids=self._existing)

    # ---- reacting to typing ------------------------------------------------------------------
    def _name_edited(self, text: str) -> None:
        if not self._id_typed:
            self.id_edit.setText(id_from_name(text))

    def _id_edited(self, _text: str) -> None:
        self._id_typed = True

    def _refresh(self, *_args: object) -> None:
        issues = self.issues()
        started = any(edit.text().strip() for edit in self._edits())
        # say what is missing only once the user began, so the empty form is not a wall of errors
        self.error_label.setText(issues[0].message if issues and started else "")
        self.add_button.setEnabled(not issues)
