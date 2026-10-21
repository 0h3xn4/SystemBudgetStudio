"""Guided mode: a short wizard from project name and orbit to the first budget.

Five pages (project, spacecraft, orbit, scenario, review) with sensible defaults, so a first
budget needs a name and four clicks. The checks are the same ones the headless builder uses.
Choosing *Blank project* on the Spacecraft page skips the orbit and the scenario (a blank project
has no units to simulate), asks for the bus voltage, and goes straight to the review (D-185).
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from budget_core.blank import BlankAnswers, check_blank, create_blank_in
from budget_core.wizard import (
    MAX_DAYS,
    SAMPLES,
    Issue,
    WizardAnswers,
    WizardError,
    check_answers,
    create_project,
    folder_name,
)
from budget_gui import theme
from budget_gui.components import Button

REVIEW_SUBTITLE = "Finish creates the project, opens it and computes the first power timeline."
BLANK = "blank"  # the data of the blank entry of the sample list
BLANK_TEXT = "Blank project: no units, every number a placeholder (you add everything)"
BLANK_FIELDS = {  # the fields of `check_blank` that belong to each page
    "Project": ("project_name",),
    "Spacecraft": ("bus_name", "bus_voltage_v"),
    "Orbit": (),
    "Scenario": (),
    "Review": (),
}
PAGES = {
    "Project": ("project_name",),
    "Spacecraft": ("sample",),
    "Orbit": ("altitude_km", "inclination_deg", "raan_deg"),
    "Scenario": ("duration_days", "start_utc"),
}


class _Page(QWizardPage):
    def __init__(self, wizard: GuidedWizard, title: str, intro: str) -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle(title)
        self.setSubTitle(intro)
        self.form = QFormLayout()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(*theme.inset(3, 2))
        outer.setSpacing(theme.gap(2))
        self.form.setHorizontalSpacing(theme.gap(2))
        self.form.setVerticalSpacing(theme.gap(1))
        outer.addLayout(self.form)

    def isComplete(self) -> bool:  # noqa: N802 (Qt naming)
        return self._wizard.page_ok(self.title())

    def initializePage(self) -> None:  # noqa: N802 (Qt naming)
        self._wizard.refresh_error(self.title())


class GuidedWizard(QWizard):
    """Collects the answers and creates the project folder on Finish."""

    created = Signal(object)

    def __init__(self, parent_folder: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New project (guided mode)")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.parent_folder = Path(parent_folder)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")

        self.name_edit = QLineEdit("My first satellite")
        self.folder_edit = QLineEdit(str(self.parent_folder))
        browse = Button("Browse…", icon="folder-open")
        browse.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(theme.gap(1))
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)

        self.sample_combo = QComboBox()
        for key, text in SAMPLES.items():
            self.sample_combo.addItem(text, key)
        self.sample_combo.addItem(BLANK_TEXT, BLANK)
        self.bus_name_edit = QLineEdit("main")
        self.bus_voltage = self._spin(0.0, 1, " V", 0.0, 1000.0)
        self.bus_voltage.setSpecialValueText("not set")  # no default: it is the user's number
        self.altitude = self._spin(550.0, 1, " km", 0.0, 100000.0)
        self.inclination = self._spin(97.6, 1, " deg", 0.0, 180.0)
        self.raan = self._spin(100.0, 1, " deg", 0.0, 359.9)
        self.duration = self._spin(1.0, 2, " days", 0.01, 1000.0)
        self.start_edit = QLineEdit("2026-06-01T00:00:00Z")
        self.review = QLabel("")
        self.review.setWordWrap(True)
        for widget, name in (
            (self.name_edit, "Project name"),
            (self.folder_edit, "Parent folder"),
            (self.sample_combo, "Sample spacecraft"),
            (self.bus_name_edit, "Name of the main bus"),
            (self.bus_voltage, "Nominal voltage of the main bus in volts"),
            (self.altitude, "Altitude in kilometres"),
            (self.inclination, "Inclination in degrees"),
            (self.raan, "Right ascension of the ascending node in degrees"),
            (self.duration, "Length in days"),
            (self.start_edit, "Start time, UTC"),
        ):
            widget.setAccessibleName(name)

        project = _Page(self, "Project", "Name your project and choose where it is stored.")
        project.form.addRow("Project name", self.name_edit)
        project.form.addRow("Parent folder", folder_row)
        spacecraft = _Page(
            self,
            "Spacecraft",
            "Start from a sample spacecraft. Its numbers are invented; you replace them later.",
        )
        spacecraft.form.addRow("Sample", self.sample_combo)
        spacecraft.form.addRow("Bus name", self.bus_name_edit)
        spacecraft.form.addRow("Bus voltage", self.bus_voltage)
        orbit = _Page(
            self,
            "Orbit",
            "A near-circular orbit. The altitude is above the Earth's surface.",
        )
        orbit.form.addRow("Altitude", self.altitude)
        orbit.form.addRow("Inclination", self.inclination)
        orbit.form.addRow("RAAN (ascending node)", self.raan)
        scenario = _Page(
            self,
            "Scenario",
            f"How long to simulate (up to {MAX_DAYS:g} days) and when it starts (UTC).",
        )
        scenario.form.addRow("Length", self.duration)
        scenario.form.addRow("Start (UTC)", self.start_edit)
        review = _Page(self, "Review", REVIEW_SUBTITLE)
        review.form.addRow(self.review)
        self._pages = {p.title(): p for p in (project, spacecraft, orbit, scenario, review)}
        self._ids = {title: self.addPage(page) for title, page in self._pages.items()}
        self.spacecraft_form = spacecraft.form
        self._review_page = review
        self._show_bus_fields()
        # one shared error label moves with the current page
        self.currentIdChanged.connect(self._move_error_label)

        for widget in (self.name_edit, self.folder_edit, self.start_edit, self.bus_name_edit):
            widget.textChanged.connect(lambda _t: self._changed())
        for spin in (self.altitude, self.inclination, self.raan, self.duration, self.bus_voltage):
            spin.valueChanged.connect(lambda _v: self._changed())
        self.sample_combo.currentIndexChanged.connect(lambda _i: self._changed())
        self.sample_combo.currentIndexChanged.connect(lambda _i: self._show_bus_fields())
        self._style_buttons()
        self.currentIdChanged.connect(lambda _id: self._style_buttons())
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self.restart()  # makes the first page current and puts the error label on it

    def _style_buttons(self) -> None:
        """Next and Finish are the one primary action of a page; Back and Cancel are secondary
        (the style sheet reads the kind, so the buttons are polished again)."""
        kinds = {
            QWizard.WizardButton.NextButton: "primary",
            QWizard.WizardButton.FinishButton: "primary",
            QWizard.WizardButton.BackButton: "secondary",
            QWizard.WizardButton.CancelButton: "secondary",
        }
        for which, kind in kinds.items():
            button = self.button(which)
            if button is not None:
                button.setProperty("kind", kind)
                style = button.style()
                if style is not None:
                    style.unpolish(button)
                    style.polish(button)

    @staticmethod
    def _spin(value: float, decimals: int, suffix: str, low: float, high: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(low, high)
        box.setSuffix(suffix)
        box.setValue(value)
        return box

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the parent folder")
        if folder:
            self.folder_edit.setText(folder)

    # ---- answers -----------------------------------------------------------------------------
    def answers(self) -> WizardAnswers:
        return WizardAnswers(
            project_name=self.name_edit.text(),
            sample=str(self.sample_combo.currentData()),
            altitude_km=self.altitude.value(),
            inclination_deg=self.inclination.value(),
            raan_deg=self.raan.value(),
            duration_days=self.duration.value(),
            start_utc=self.start_edit.text(),
        )

    def is_blank(self) -> bool:
        return self.sample_combo.currentData() == BLANK

    def blank_answers(self) -> BlankAnswers:
        voltage = self.bus_voltage.value()
        return BlankAnswers(
            project_name=self.name_edit.text(),
            bus_voltage_v=voltage if voltage > 0.0 else None,
            bus_name=self.bus_name_edit.text(),
        )

    def _show_bus_fields(self) -> None:
        """The bus name and voltage are asked only for a blank project."""
        blank = self.is_blank()
        for widget in (self.bus_name_edit, self.bus_voltage):
            self.spacecraft_form.setRowVisible(widget, blank)

    def nextId(self) -> int:  # noqa: N802 (Qt naming)
        """A blank project has no orbit and no scenario to ask for: the review follows."""
        if self.is_blank() and self.currentId() == self._ids["Spacecraft"]:
            return self._ids["Review"]
        return super().nextId()

    def _parent(self) -> Path:
        """The parent folder as typed, with '~' expanded to the home folder."""
        return Path(self.folder_edit.text().strip() or ".").expanduser()

    def _target(self) -> Path:
        return self._parent() / folder_name(self.name_edit.text())

    def _parent_issue(self) -> str | None:
        text = self.folder_edit.text().strip()
        if not text:
            return "Choose the parent folder where the project folder is created."
        existing = self._parent()
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent  # the folder will be created below this one
        if not existing.is_dir():
            return "The parent folder is a file, not a folder. Choose another parent folder."
        if not os.access(existing, os.W_OK | os.X_OK):
            return "You may not write in the parent folder. Choose another one."
        return None

    def issues_for(self, page: str) -> list[Issue]:
        if self.is_blank():
            # a blank project asks for a name and a bus; the sample, orbit and scenario do not apply
            issues = [
                i
                for i in check_blank(self.blank_answers())
                if i.field in BLANK_FIELDS.get(page, ())
            ]
        else:
            fields = PAGES.get(page, ())
            issues = [i for i in check_answers(self.answers()) if i.field in fields]
        if page == "Project" and (problem := self._parent_issue()) is not None:
            issues.append(Issue("project_name", problem))
        elif page == "Project" and self._target().exists():
            issues.append(
                Issue(
                    "project_name",
                    f"The folder '{self._target().name}' already exists. "
                    "Choose another project name or folder.",
                )
            )
        return issues

    def page_ok(self, page: str) -> bool:
        return not self.issues_for(page)

    def refresh_error(self, page: str) -> None:
        issues = self.issues_for(page)
        self.error_label.setText(issues[0].message if issues else "")

    def _current_title(self) -> str:
        page = self.currentPage()
        return page.title() if page is not None else "Project"

    def _move_error_label(self, _id: int) -> None:
        page = self.currentPage()
        if page is None:
            return
        layout = page.layout()
        if layout is not None and self.error_label.parent() is not page:
            layout.addWidget(self.error_label)
        if self.is_blank():
            b = self.blank_answers()
            self.review.setText(
                f"Project: {b.project_name.strip()}\n"
                f"Folder: {self._target()}\n"
                "Spacecraft: a blank project with no units, no orbit and no scenario; "
                "every configuration number is a placeholder\n"
                f"Bus: {b.bus_name.strip()}, {b.bus_voltage_v or 0:g} V"
            )
            self._review_page.setSubTitle(
                "Finish creates the blank project and opens it. Add your units, an orbit and a "
                "scenario; the Problems panel lists what is still open."
            )
        else:
            a = self.answers()
            self.review.setText(
                f"Project: {a.project_name.strip()}\n"
                f"Folder: {self._target()}\n"
                f"Sample: {SAMPLES.get(a.sample, '')}\n"
                f"Orbit: {a.altitude_km:g} km, inclination {a.inclination_deg:g} deg, "
                f"RAAN {a.raan_deg:g} deg\n"
                f"Scenario: {a.duration_days:g} day(s) from {a.start_utc.strip()}"
            )
            self._review_page.setSubTitle(REVIEW_SUBTITLE)
        self.refresh_error(page.title())

    def _changed(self) -> None:
        title = self._current_title()
        self.refresh_error(title)
        page = self.currentPage()
        if page is not None:
            page.completeChanged.emit()

    # ---- finish ------------------------------------------------------------------------------
    def accept(self) -> None:
        try:
            if self.is_blank():
                folder = create_blank_in(self.blank_answers(), self._parent())
            else:
                folder = create_project(self.answers(), self._parent())
        except WizardError as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()
        self.created.emit(folder)
