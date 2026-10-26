"""The form of *Add link* (D-199): the structure of a link, none of the numbers invented.

It asks for the name, the id (suggested from the name until it is typed by hand), the direction,
the ground station at the other end (one of the stations that exist), the frequency in MHz, the
modulation with its coding and the data rates. The modulation and coding are a pair of the
project's `config/ebn0_table.yaml`; while that table is empty (a blank project) they are two text
fields. The numbers that come from a data sheet or a standard are written as placeholders and
filled in **Model > Inputs**. The checks are those of `budget_core.new_link`.
"""

from __future__ import annotations

import re
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

from budget_core.new_link import DIRECTIONS, LinkAnswers, check_link, id_from_name
from budget_core.wizard import Issue
from budget_gui import theme
from budget_gui.components import Button

_SEPARATORS = re.compile(r"[;\s]+")


def _optional_number(text: str) -> float | None:
    """Empty is None (the checks name it); text that is not a number is NaN, which the checks
    refuse, so a typing error is not taken for an empty answer."""
    if not text.strip():
        return None
    return _token(text)


def _token(text: str) -> float:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return float("nan")


def _rates(text: str) -> tuple[float, ...]:
    """The data rates, separated by semicolons or spaces (a comma is a decimal comma)."""
    return tuple(_token(part) for part in _SEPARATORS.split(text.strip()) if part)


class AddLinkDialog(QDialog):
    """Asks for the structure of a link; *Add link* stays off until every answer passes the
    checks."""

    def __init__(
        self,
        existing_ids: Sequence[str],
        ground_station_ids: Sequence[str],
        ebn0_pairs: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add link")
        self._existing = list(existing_ids)
        self._stations = list(ground_station_ids)
        self._pairs = list(ebn0_pairs)
        self._id_typed = False

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(list(DIRECTIONS))
        self.peer_combo = QComboBox()
        self.peer_combo.addItems(self._stations)
        self.peer_combo.setPlaceholderText("Choose a ground station")
        self.peer_combo.setCurrentIndex(-1)
        self.frequency_edit = QLineEdit()
        self.frequency_edit.setPlaceholderText("MHz, for example 2200")
        self.pair_combo = QComboBox()
        for modulation, coding in self._pairs:
            self.pair_combo.addItem(f"{modulation}, {coding}", (modulation, coding))
        self.pair_combo.setPlaceholderText("Choose a pair of the Eb/N0 table")
        self.pair_combo.setCurrentIndex(-1)
        self.modulation_edit = QLineEdit()
        self.modulation_edit.setPlaceholderText("for example QPSK")
        self.coding_edit = QLineEdit()
        self.coding_edit.setPlaceholderText("for example rate 1/2")
        self.rates_edit = QLineEdit()
        self.rates_edit.setPlaceholderText("bit/s, separated by semicolons: 32000; 128000")
        for widget, label in (
            (self.name_edit, "Link name"),
            (self.id_edit, "Link id (the file name)"),
            (self.direction_combo, "Direction"),
            (self.peer_combo, "Ground station at the other end"),
            (self.frequency_edit, "Frequency in megahertz"),
            (self.pair_combo, "Modulation and coding"),
            (self.modulation_edit, "Modulation"),
            (self.coding_edit, "Coding"),
            (self.rates_edit, "Data rates in bits per second"),
        ):
            widget.setAccessibleName(label)

        form = QFormLayout()
        form.setHorizontalSpacing(theme.gap(2))
        form.setVerticalSpacing(theme.gap(1))
        form.addRow("Name", self.name_edit)
        form.addRow("Id", self.id_edit)
        form.addRow("Direction", self.direction_combo)
        form.addRow("Ground station", self.peer_combo)
        form.addRow("Frequency, MHz", self.frequency_edit)
        form.addRow("Modulation and coding", self.pair_combo)
        form.addRow("Modulation", self.modulation_edit)
        form.addRow("Coding", self.coding_edit)
        form.addRow("Data rates, bit/s", self.rates_edit)
        has_table = bool(self._pairs)
        unused: tuple[QWidget, ...] = (
            (self.modulation_edit, self.coding_edit) if has_table else (self.pair_combo,)
        )
        for hidden in unused:
            hidden.hide()
            row_label = form.labelForField(hidden)
            if row_label is not None:
                row_label.hide()

        intro = QLabel(
            "A link joins the spacecraft and a ground station in one direction. The transmit "
            "power, the antenna gain, the G/T, the required margin and the losses come from a "
            "data sheet or a standard: they are written as placeholders (source TBD) and filled "
            "in under Model > Inputs; until then the link results that need them are not "
            "available."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        self.table_note = QLabel(
            "config/ebn0_table.yaml has no entry yet, so any modulation and coding is accepted; "
            "the required Eb/N0 stays unknown until the table lists the pair."
        )
        self.table_note.setWordWrap(True)
        self.table_note.setProperty("role", "muted")
        self.table_note.setVisible(not has_table)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.add_button = Button("Add link", "primary")
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
        layout.addWidget(self.table_note)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        self.name_edit.textEdited.connect(self._name_edited)
        self.id_edit.textEdited.connect(self._id_edited)
        for edit in self._edits():
            edit.textChanged.connect(self._refresh)
        for combo in (self.direction_combo, self.peer_combo, self.pair_combo):
            combo.currentIndexChanged.connect(self._refresh)
        self.resize(*theme.scaled(theme.PALETTE_SIZE))
        self._refresh()

    def _edits(self) -> tuple[QLineEdit, ...]:
        return (
            self.name_edit,
            self.id_edit,
            self.frequency_edit,
            self.modulation_edit,
            self.coding_edit,
            self.rates_edit,
        )

    # ---- the answers -------------------------------------------------------------------------
    def answers(self) -> LinkAnswers:
        if self._pairs:
            pair = self.pair_combo.currentData()
            modulation, coding = pair if pair is not None else ("", "")
        else:
            modulation, coding = self.modulation_edit.text(), self.coding_edit.text()
        return LinkAnswers(
            link_id=self.id_edit.text(),
            name=self.name_edit.text(),
            direction=self.direction_combo.currentText(),
            peer=self.peer_combo.currentText(),
            frequency_mhz=_optional_number(self.frequency_edit.text()),
            modulation=modulation,
            coding=coding,
            data_rates_bps=_rates(self.rates_edit.text()),
        )

    def issues(self) -> list[Issue]:
        return check_link(
            self.answers(),
            existing_ids=self._existing,
            ground_station_ids=self._stations,
            ebn0_pairs=self._pairs,
        )

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
