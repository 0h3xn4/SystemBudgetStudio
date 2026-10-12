"""Unit-aware table editor for one unit: header fields plus a table of power modes.

Cells accept plain numbers (canonical unit) or numbers with units ("2500 mW"); the unit model
validates every edit and explains problems in plain words. Saving patches the unit file in place:
comments, key order and every value the table does not show (for example the heat dissipation
ratio of a mode) stay as written, and a save without an edit leaves the file byte-identical
(decision D-103).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.io.errors import explain
from budget_core.io.project_loader import model_to_data
from budget_core.io.roundtrip import file_stamp, save_edited_data
from budget_core.io.yamlio import LineMap
from budget_core.model import Unit
from budget_core.reports.files import OutputError
from budget_core.units.quantity import canonical_unit

COLUMNS = (
    "name",
    "avg_power_w",
    "peak_power_w",
    "duty_cycle_ratio",
    "min_duration_s",
    "max_duration_s",
)
OPTIONAL = {"min_duration_s", "max_duration_s"}
HIDDEN_ROLE = int(Qt.ItemDataRole.UserRole) + 7  # keys of a mode that the table has no column for
FIELDS = ("name", "subsystem", "mass_kg", "bus", "maturity")


def _header(name: str) -> str:
    unit = canonical_unit(name)
    return f"{name} [{unit}]" if unit else name


def _value(text: str) -> Any:
    """Plain numbers mean the canonical unit; anything else goes to the unit parser."""
    stripped = text.strip()
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _show(value: Any) -> str:
    return "" if value is None else str(value)


class UnitEditor(QWidget):
    saved = Signal()
    modified_changed = Signal(bool)

    def __init__(self, root: Path, unit_id: str, unit: Unit) -> None:
        super().__init__()
        self.rel_path = f"units/{unit_id}.yaml"
        self.path = root / self.rel_path
        self.unit_id = unit_id
        self._original = unit
        self._stamp = file_stamp(self.path)  # the file as this table was loaded from it
        self._modified = False
        self._loading = False

        self.fields = {name: QLineEdit() for name in FIELDS}
        form = QFormLayout()
        for name, edit in self.fields.items():
            form.addRow(_header(name), edit)
            edit.textEdited.connect(self._edited)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([_header(c) for c in COLUMNS])
        self.table.itemChanged.connect(lambda _item: self._edited())

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #da1e28;")
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)

        add = QPushButton("Add mode")
        add.clicked.connect(self.add_mode)
        remove = QPushButton("Remove selected mode")
        remove.clicked.connect(lambda: self.remove_mode(self.table.currentRow()))
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        buttons = QHBoxLayout()
        for button in (add, remove, save):
            buttons.addWidget(button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Unit file: {self.rel_path}"))
        layout.addLayout(form)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.error_label)
        layout.addWidget(self.note_label)
        layout.addLayout(buttons)
        self._populate(unit)

    # ---- state -------------------------------------------------------------------------------
    def is_modified(self) -> bool:
        return self._modified

    def _set_modified(self, value: bool) -> None:
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def _populate(self, unit: Unit) -> None:
        self._loading = True
        data = model_to_data(unit)
        for name, edit in self.fields.items():
            edit.setText(_show(data.get(name)))
        self.table.setRowCount(0)
        for mode in data["modes"]:
            hidden = {k: v for k, v in mode.items() if k not in COLUMNS}
            self._append_row([_show(mode.get(c)) for c in COLUMNS], hidden)
        self.table.resizeColumnsToContents()
        self._loading = False
        self.error_label.setText("")
        self.note_label.setText("")

    def _append_row(self, values: list[str], hidden: dict[str, Any] | None = None) -> None:
        """A row of the table; `hidden` holds the keys of the mode the table has no column for,
        carried with the row so they are written back unchanged."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            if column > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if column == 0:
                item.setData(HIDDEN_ROLE, dict(hidden or {}))
            self.table.setItem(row, column, item)

    def discard_changes(self) -> None:
        self._populate(self._original)
        self._set_modified(False)

    def reload(self, unit: Unit) -> None:
        """After the project reloaded: show the unit as the file now holds it, unless the user has
        edits pending (their save is then checked against the file, see `save`) or nothing
        changed (the cursor and selection stay)."""
        if self._modified:
            return
        stamp = file_stamp(self.path)
        if unit == self._original and stamp == self._stamp:
            return
        self._original = unit
        self._stamp = stamp
        self._populate(unit)

    def file_changed_on_disk(self) -> bool:
        return file_stamp(self.path) != self._stamp

    # ---- editing -----------------------------------------------------------------------------
    def add_mode(self) -> None:
        self._loading = True
        n = self.table.rowCount() + 1
        self._append_row([f"mode_{n}", "0.0", "0.0", "1.0", "", ""])
        self._loading = False
        self._edited()

    def remove_mode(self, row: int) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.removeRow(row)
            self._edited()

    def _edited(self) -> None:
        if self._loading:
            return
        self._set_modified(True)
        self._validate()

    def _data(self) -> dict[str, Any]:
        data = model_to_data(self._original)
        for name, edit in self.fields.items():
            data[name] = _value(edit.text()) if name == "mass_kg" else edit.text().strip()
        modes: list[dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            mode: dict[str, Any] = {}
            for column, name in enumerate(COLUMNS):
                item = self.table.item(row, column)
                text = item.text() if item else ""
                if name == "name":
                    mode[name] = text.strip()
                elif text.strip() or name not in OPTIONAL:
                    mode[name] = _value(text)
            first = self.table.item(row, 0)
            hidden = first.data(HIDDEN_ROLE) if first is not None else None
            mode.update(hidden if isinstance(hidden, dict) else {})
            modes.append(mode)
        data["modes"] = modes
        return data

    def current_unit(self) -> Unit:
        """The unit as currently edited; raises ValidationError when it is not valid."""
        return Unit.model_validate(self._data())

    def _validate(self) -> Unit | None:
        try:
            unit = self.current_unit()
        except ValidationError as exc:
            lines = [
                f"{p.path or 'unit'}: {p.message}" + (f" {p.hint}" if p.hint else "")
                for p in explain(exc, Unit, self.rel_path, LineMap())
            ]
            self.error_label.setText("\n".join(lines))
            return None
        self.error_label.setText("")
        return unit

    def save(self) -> bool:
        if self.file_changed_on_disk():
            if self._modified:
                self.error_label.setText(
                    "The unit file changed on disk after this table was opened. Saving would "
                    "overwrite that change. Close this tab (Discard) and open the unit again."
                )
                return False
            return True  # nothing to save; the table is refreshed on the next reload
        if not self._modified:
            return True
        unit = self._validate()
        if unit is None:
            return False
        try:
            result = save_edited_data(
                self.path,
                model_to_data(self._original),
                model_to_data(unit),
                lambda data: model_to_data(Unit.model_validate(data)),
            )
        except (OSError, OutputError, UnicodeDecodeError):
            self.error_label.setText("The file could not be written. Check the folder permissions.")
            return False
        self._original = unit
        self._stamp = file_stamp(self.path)
        self.note_label.setText(
            "Saved. The file could not be edited in place, so it was rewritten in the standard "
            "layout; its comments were not kept."
            if result.canonical
            else ""
        )
        self._set_modified(False)
        self.saved.emit()
        return True
