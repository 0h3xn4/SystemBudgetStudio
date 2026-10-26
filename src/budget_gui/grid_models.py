"""The table models of the Model grids: units, power modes and sourced inputs (D-159).

Each model shows a slice of the `ModelDocument` and writes edits back into it (never to a file).
A cell is one of: a number (fixed decimals per column, right-aligned figures), text, a value that
is **not given** (drawn as *not checked*: a missing temperature limit or heat ratio means the
result that needs it is not worked out), a **placeholder** (a sourced number without a value or
with source `TBD`) or **wrong** (the model refused the value; the tooltip says why). The full
precision and the unit are in the tooltip; the header carries the unit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal

from budget_core.units.quantity import canonical_unit
from budget_gui.delegates import CELL_ROLE, CHOICES_ROLE, NUMERIC_ROLE, STATE_ROLE
from budget_gui.entry import cell_value, has_decimal_comma
from budget_gui.model_document import ModelDocument, Path_, set_at, value_at
from budget_gui.theme import Status

Index = QModelIndex | QPersistentModelIndex
PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 40  # (file, path) of the value in a cell, or None
ROW_ROLE = int(Qt.ItemDataRole.UserRole) + 41  # the row key: (file, position)


@dataclass(frozen=True)
class Column:
    title: str  # the field name with its unit, e.g. "avg_power_w [W]"
    key: str  # the field name inside the file ("" for a computed or identifying column)
    kind: str = "number"  # "number", "text" or "id" (read-only)
    decimals: int = 3
    optional: bool = False  # an empty cell removes the field
    absent_means_not_checked: bool = False  # a missing value is drawn as "not checked"
    absent_tip: str = ""
    parent: str = ""  # a mapping that holds the field ("temperature_limits")

    @property
    def editable(self) -> bool:
        return self.kind != "id"


def header_of(field: str) -> str:
    unit = canonical_unit(field)
    return f"{field} [{unit}]" if unit else field


def number_text(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def edit_text(value: Any) -> str:
    """The text an editor starts with: the exact value, not the rounded one that is shown."""
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def parse_cell(text: str, column: Column) -> Any:
    """What a typed (or pasted) text means for a column: a number, a number with a unit (for the
    model to convert), text, or None for an optional field that is emptied."""
    stripped = text.strip()
    if column.kind == "text":
        return stripped
    if not stripped:
        return None if column.optional else ""
    return cell_value(stripped)


_READ_ONLY = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_EDITABLE = _READ_ONLY | Qt.ItemFlag.ItemIsEditable


class GridModel(QAbstractTableModel):
    """Common behaviour: rows as keys, cells as (file, path), edits into the document."""

    columns: tuple[Column, ...] = ()

    def __init__(self, document: ModelDocument) -> None:
        super().__init__()
        self.document = document
        self._keys: list[tuple[str, int]] = []
        self._rebuild()
        document.changed.connect(self._document_changed)

    # ---- rows --------------------------------------------------------------------------------
    def row_keys(self) -> list[tuple[str, int]]:
        raise NotImplementedError

    def path_of(self, key: tuple[str, int], column: Column) -> Path_ | None:
        raise NotImplementedError

    def label_of(self, key: tuple[str, int]) -> str:
        """The row in words, for messages (ids only, never values)."""
        raise NotImplementedError

    def _rebuild(self) -> None:
        self._keys = self.row_keys()

    def _document_changed(self) -> None:
        keys = self.row_keys()
        if keys != self._keys:
            self.beginResetModel()
            self._keys = keys
            self.endResetModel()
        elif keys:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(keys) - 1, len(self.columns) - 1)
            )

    # ---- Qt ----------------------------------------------------------------------------------
    def rowCount(self, parent: Index | None = None) -> int:  # noqa: N802
        return 0 if parent is not None and parent.isValid() else len(self._keys)

    def columnCount(self, parent: Index | None = None) -> int:  # noqa: N802
        return 0 if parent is not None and parent.isValid() else len(self.columns)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.columns):
            if role == Qt.ItemDataRole.DisplayRole:
                return self.columns[section].title
            if role == Qt.ItemDataRole.ToolTipRole:
                return self.column_tip(self.columns[section])
        return None

    def column_tip(self, column: Column) -> str:
        return column.title

    def flags(self, index: Index) -> Qt.ItemFlag:
        if index.isValid() and self.columns[index.column()].editable:
            return _EDITABLE
        return _READ_ONLY

    def cell(self, row: int, column: int) -> tuple[str, Path_] | None:
        """The file and the path of the value in a cell (None for a column without one)."""
        key = self._keys[row]
        path = self.path_of(key, self.columns[column])
        return (key[0], path) if path is not None else None

    def value_of(self, row: int, column: int) -> Any:
        found = self.cell(row, column)
        return self.document.value(*found) if found else None

    def state_of(self, row: int, column: int) -> Status | None:
        found = self.cell(row, column)
        col = self.columns[column]
        if found is None:
            return None
        if self.document.problem_at(*found) is not None:
            return Status.FAIL
        if col.absent_means_not_checked and self.document.value(*found) is None:
            return Status.NOT_CHECKED
        return None

    def row_has_problem(self, row: int) -> bool:
        """Whether a cell of the row is wrong: the identifier cell carries the marker, so a
        problem is seen in its row also when the cell is scrolled out of view (D-176)."""
        if not self.document.has_problems():
            return False
        for column in range(len(self.columns)):
            found = self.cell(row, column)
            if found is not None and self.document.problem_at(*found) is not None:
                return True
        return False

    def marked_state(self, row: int, column: int) -> Status | None:
        """The state of a cell, and for the identifier column the problem marker of the row."""
        state = self.state_of(row, column)
        if column == 0 and state is None and self.row_has_problem(row):
            return Status.FAIL
        return state

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        col = self.columns[column]
        if role == Qt.ItemDataRole.DisplayRole:
            return self.display(row, column)
        if role == Qt.ItemDataRole.EditRole:
            return edit_text(self.value_of(row, column))
        if role == CELL_ROLE:
            numeric = col.kind == "number" or (not col.key and self.id_is_numeric(column))
            return (self.display(row, column), self.marked_state(row, column), numeric, False, None)
        if role == NUMERIC_ROLE:
            return col.kind == "number" or (not col.key and self.id_is_numeric(column))
        if role == STATE_ROLE:
            return self.marked_state(row, column)
        if role == PATH_ROLE:
            return self.cell(row, column)
        if role == CHOICES_ROLE:
            return self.choices(row, column)
        if role == ROW_ROLE:
            return self._keys[row]
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = self.tooltip(row, column)
            if column == 0 and self.row_has_problem(row):
                note = "A cell of this row needs correcting."
                return f"{note}\n{tip}" if tip else note
            return tip
        return None

    def message_at(self, found: tuple[str, Path_], hint: bool = False) -> str | None:
        """Why the model refuses the value in a cell, in words (None when it does not); the hint
        (what to write instead) is for the tooltip, not for the one line under the grid."""
        problem = self.document.problem_at(*found)
        if problem is None:
            return None
        value = self.document.value(*found)
        if isinstance(value, str) and has_decimal_comma(value):
            return "Use a decimal point, not a comma, for example 1.5."
        return problem.message + (f" {problem.hint}" if hint and problem.hint else "")

    def choices(self, row: int, column: int) -> list[str] | None:
        """The values a cell may take, when it is a choice from a list (None: typed text)."""
        return None

    def id_text(self, row: int, column: int) -> str:
        """The text of a column that is not a field of the file (an id, a computed number)."""
        return ""

    def id_tip(self, row: int, column: int) -> str | None:
        return None

    def id_is_numeric(self, column: int) -> bool:
        return False

    def display(self, row: int, column: int) -> str:
        col = self.columns[column]
        if not col.key:
            return self.id_text(row, column)
        value = self.value_of(row, column)
        if value is None:
            return "n/a" if col.absent_means_not_checked else ""
        if col.kind == "number" and isinstance(value, int | float) and not isinstance(value, bool):
            return number_text(float(value), col.decimals)
        return str(value)

    def tooltip(self, row: int, column: int) -> str | None:
        found = self.cell(row, column)
        col = self.columns[column]
        if not col.key:
            return self.id_tip(row, column)
        if found is None:
            return None
        parts: list[str] = []
        message = self.message_at(found, hint=True)
        if message is not None:
            parts.append(message)
        elif col.absent_means_not_checked and self.document.value(*found) is None:
            parts.append(col.absent_tip)
        value = self.document.value(*found)
        if col.kind == "number" and isinstance(value, int | float) and not isinstance(value, bool):
            unit = canonical_unit(col.key)
            parts.append(f"{edit_text(value)}{' ' + unit if unit else ''}")
        return "\n".join(parts) if parts else None

    def setData(  # noqa: N802
        self, index: Index, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        return self.set_text(index.row(), index.column(), str(value))

    def set_text(self, row: int, column: int, text: str) -> bool:
        change = self.change_for(row, column, text)
        if change is None:
            return False
        rel, fn, what = change
        return self.document.edit([(rel, fn)], what)

    def change_for(
        self, row: int, column: int, text: str
    ) -> tuple[str, Callable[[dict[str, Any]], None], str] | None:
        """The edit that typing `text` into a cell means: (file, change, undo text)."""
        col = self.columns[column]
        found = self.cell(row, column)
        if found is None or not col.editable:
            return None
        rel, path = found
        value = parse_cell(text, col)

        def apply(data: dict[str, Any]) -> None:
            set_at(data, path, value)

        return rel, apply, f"Edit {self.label_of(self._keys[row])}: {col.key}"

    def file_label(self, rel: str) -> str:
        return rel.split("/")[-1].removesuffix(".yaml")

    def problem_lines(self) -> list[str]:
        """One line per wrong cell, in words (row and field, never the typed value); a problem
        of a file that no cell of this grid shows (a duplicate name) is listed by its file."""
        if not self.document.has_problems():
            return []
        lines: list[str] = []
        seen: set[tuple[str, str]] = set()
        for row, key in enumerate(self._keys):
            for column, col in enumerate(self.columns):
                found = self.cell(row, column)
                problem = self.document.problem_at(*found) if found else None
                if problem is not None and found is not None:
                    seen.add((found[0], problem.path))
                    text = (self.message_at(found) or "").rstrip(".")
                    lines.append(f"{self.label_of(key)}, {col.key}: {text}")
        for rel in {key[0] for key in self._keys}:
            for problem in self.document.problems(rel):
                if (rel, problem.path) not in seen:
                    lines.append(f"{self.file_label(rel)}: {problem.message.rstrip('.')}")
        return lines

    def has_value_at(self, row: int, column: int) -> bool:
        found = self.cell(row, column)
        return found is not None and self.document.value(*found) is not None


# ---- units ----------------------------------------------------------------------------------
class UnitsModel(GridModel):
    """One row per unit: its identity, its mass and its temperature limits (each in kelvin)."""

    columns = (
        Column("unit", "", "id"),
        Column("name", "name", "text"),
        Column("subsystem", "subsystem", "text"),
        Column("bus", "bus", "text"),
        Column("maturity", "maturity", "text"),
        Column(header_of("mass_kg"), "mass_kg", decimals=3),
        *(
            Column(
                header_of(key),
                key,
                decimals=2,
                optional=True,
                absent_means_not_checked=True,
                absent_tip="No limit given: the unit is not checked against it.",
                parent="temperature_limits",
            )
            for key in ("operating_min_k", "operating_max_k", "survival_min_k", "survival_max_k")
        ),
    )

    def row_keys(self) -> list[tuple[str, int]]:
        return [(rel, 0) for rel in self.document.rels("units/")]

    def path_of(self, key: tuple[str, int], column: Column) -> Path_ | None:
        if not column.key:
            return None
        return (column.parent, column.key) if column.parent else (column.key,)

    def label_of(self, key: tuple[str, int]) -> str:
        return key[0].removeprefix("units/").removesuffix(".yaml")

    def id_text(self, row: int, column: int) -> str:
        return self.label_of(self._keys[row])

    def id_tip(self, row: int, column: int) -> str | None:
        return self._keys[row][0]

    def row_of(self, unit_id: str) -> int:
        try:
            return self._keys.index((f"units/{unit_id}.yaml", 0))
        except ValueError:
            return -1


# ---- power modes ----------------------------------------------------------------------------
class PowerModesModel(GridModel):
    """One row per power mode of every unit, in the order of the files."""

    columns = (
        Column("unit", "", "id"),
        Column("mode", "name", "text"),
        Column(header_of("avg_power_w"), "avg_power_w", decimals=3),
        Column(header_of("peak_power_w"), "peak_power_w", decimals=3),
        Column(header_of("duty_cycle_ratio"), "duty_cycle_ratio", decimals=3),
        Column(
            header_of("heat_dissipation_ratio"),
            "heat_dissipation_ratio",
            decimals=3,
            optional=True,
            absent_means_not_checked=True,
            absent_tip="Not given: thermal results that need it are n/a.",
        ),
        Column(header_of("min_duration_s"), "min_duration_s", decimals=1, optional=True),
        Column(header_of("max_duration_s"), "max_duration_s", decimals=1, optional=True),
        Column("average x duty [W]", "", "id"),
    )

    def row_keys(self) -> list[tuple[str, int]]:
        keys: list[tuple[str, int]] = []
        for rel in self.document.rels("units/"):
            modes = self.document.value(rel, ("modes",))
            if isinstance(modes, list):
                keys.extend((rel, index) for index in range(len(modes)))
        return keys

    def path_of(self, key: tuple[str, int], column: Column) -> Path_ | None:
        return ("modes", key[1], column.key) if column.key else None

    def label_of(self, key: tuple[str, int]) -> str:
        unit = key[0].removeprefix("units/").removesuffix(".yaml")
        name = self.document.value(key[0], ("modes", key[1], "name"))
        return (
            f"{unit} / {name}" if isinstance(name, str) and name else f"{unit} / mode {key[1] + 1}"
        )

    def column_tip(self, column: Column) -> str:
        tips = {
            "avg_power_w": "Average power while the unit is in this mode and switched on.",
            "peak_power_w": "Peak power; not below the average.",
            "duty_cycle_ratio": "Share of the time the unit is on in this mode (0 to 1).",
            "heat_dissipation_ratio": "Share of the electrical power that ends up as heat.",
        }
        return tips.get(column.key, column.title)

    def effective(self, row: int) -> float | None:
        avg = self.value_of(row, 2)
        duty = self.value_of(row, 4)
        if isinstance(avg, int | float) and isinstance(duty, int | float):
            return float(avg) * float(duty)
        return None

    def id_text(self, row: int, column: int) -> str:
        if column == 0:
            return self._keys[row][0].removeprefix("units/").removesuffix(".yaml")
        value = self.effective(row)
        return "" if value is None else number_text(value, 3)

    def id_tip(self, row: int, column: int) -> str | None:
        if column == 0:
            return self._keys[row][0]
        return "Average power times duty cycle: what the budget counts."

    def id_is_numeric(self, column: int) -> bool:
        return column != 0

    def rows_of(self, unit_id: str) -> list[int]:
        rel = f"units/{unit_id}.yaml"
        return [row for row, key in enumerate(self._keys) if key[0] == rel]

    # ---- adding and removing a mode ----------------------------------------------------------
    def add_mode(self, rel: str) -> bool:
        modes = self.document.value(rel, ("modes",))
        if not isinstance(modes, list):
            return False
        taken = {m.get("name") for m in modes if isinstance(m, dict)}
        n = len(modes) + 1
        while f"mode_{n}" in taken:
            n += 1
        unit = rel.removeprefix("units/").removesuffix(".yaml")

        def apply(data: dict[str, Any]) -> None:
            data["modes"].append(
                {
                    "name": f"mode_{n}",
                    "avg_power_w": 0.0,
                    "peak_power_w": 0.0,
                    "duty_cycle_ratio": 1.0,
                }
            )

        return self.document.edit([(rel, apply)], f"Add mode mode_{n} to {unit}")

    def remove_mode(self, row: int) -> bool:
        rel, index = self._keys[row]
        label = self.label_of(self._keys[row])
        modes = self.document.value(rel, ("modes",))
        if not isinstance(modes, list) or len(modes) <= 1:
            return False  # a unit needs at least one power mode

        def apply(data: dict[str, Any]) -> None:
            del data["modes"][index]

        return self.document.edit([(rel, apply)], f"Remove mode {label}")


# ---- spacecraft modes -----------------------------------------------------------------------
class ModeAssignmentsModel(GridModel):
    """One row per unit in every spacecraft mode: the power mode the unit is in. A name the unit
    has no power mode of is refused (with a reason), not written, so a typing error cannot turn
    into an unknown-mode error at the next load (D-188)."""

    refused = Signal(str)  # why an edit was not made

    columns = (
        Column("spacecraft mode", "", "id"),
        Column("unit", "", "id"),
        Column("power mode", "power_mode", "text"),
    )

    def row_keys(self) -> list[tuple[str, int]]:
        keys: list[tuple[str, int]] = []
        for rel in self.document.rels("modes/"):
            assignments = self.document.value(rel, ("assignments",))
            if isinstance(assignments, dict):
                keys.extend((rel, index) for index in range(len(assignments)))
        return keys

    def unit_of(self, key: tuple[str, int]) -> str:
        assignments = self.document.value(key[0], ("assignments",))
        names = sorted(assignments) if isinstance(assignments, dict) else []
        return str(names[key[1]]) if key[1] < len(names) else ""

    def mode_of(self, key: tuple[str, int]) -> str:
        return key[0].removeprefix("modes/").removesuffix(".yaml")

    def path_of(self, key: tuple[str, int], column: Column) -> Path_ | None:
        return ("assignments", self.unit_of(key)) if column.key else None

    def label_of(self, key: tuple[str, int]) -> str:
        return f"{self.mode_of(key)} / {self.unit_of(key)}"

    def id_text(self, row: int, column: int) -> str:
        key = self._keys[row]
        return self.mode_of(key) if column == 0 else self.unit_of(key)

    def id_tip(self, row: int, column: int) -> str | None:
        key = self._keys[row]
        if column == 0:
            name = self.document.value(key[0], ("name",))
            return f"{key[0]}\n{name}" if isinstance(name, str) and name else key[0]
        return f"units/{self.unit_of(key)}.yaml"

    def rows_of(self, mode_id: str) -> list[int]:
        rel = f"modes/{mode_id}.yaml"
        return [row for row, key in enumerate(self._keys) if key[0] == rel]

    def power_modes_of(self, unit_id: str) -> list[str]:
        modes = (
            self.document.value(f"units/{unit_id}.yaml", ("modes",))
            if self.document.has(f"units/{unit_id}.yaml")
            else None
        )
        if not isinstance(modes, list):
            return []
        return [str(m["name"]) for m in modes if isinstance(m, dict) and "name" in m]

    def choices(self, row: int, column: int) -> list[str] | None:
        if column != 2:
            return None
        return self.power_modes_of(self.unit_of(self._keys[row])) or None

    def column_tip(self, column: Column) -> str:
        if column.key == "power_mode":
            return "The power mode the unit is in while the spacecraft is in this mode."
        return column.title

    def change_for(
        self, row: int, column: int, text: str
    ) -> tuple[str, Callable[[dict[str, Any]], None], str] | None:
        if column == 2:
            key = self._keys[row]
            unit = self.unit_of(key)
            wanted = text.strip()
            names = self.power_modes_of(unit)
            if wanted not in names:
                listing = ", ".join(names) if names else "none"
                self.refused.emit(
                    f"{unit} has no power mode of that name, so it was not changed. "
                    f"Its power modes: {listing}."
                )
                return None
            return super().change_for(row, column, wanted)
        return super().change_for(row, column, text)


# ---- sourced inputs -------------------------------------------------------------------------
def is_sourced(node: Any) -> bool:
    return (
        isinstance(node, dict)
        and "value" in node
        and "source" in node
        and set(node) <= {"value", "source", "note"}
    )


def sourced_paths(data: Any, prefix: Path_ = ()) -> list[Path_]:
    """Where the sourced numbers are inside a file's data, in file order."""
    found: list[Path_] = []
    if is_sourced(data):
        return [prefix] if prefix else []
    if isinstance(data, dict):
        for key, child in data.items():
            found.extend(sourced_paths(child, (*prefix, key)))
    elif isinstance(data, list):
        for index, child in enumerate(data):
            found.extend(sourced_paths(child, (*prefix, index)))
    return found


def is_placeholder(node: Any) -> bool:
    """A sourced number without a value, or whose source is `TBD` (as the model decides)."""
    if not is_sourced(node):
        return False
    source = node.get("source")
    return node.get("value") is None or (
        isinstance(source, str) and source.strip().upper() == "TBD"
    )


class SourcedModel(GridModel):
    """One row per sourced number of the configuration and link files: value, unit, source."""

    columns = (
        Column("input", "", "id"),
        Column("value", "value", decimals=6, optional=True),
        Column("unit", "", "id"),
        Column("source", "source", "text"),
        Column("note", "note", "text"),
    )

    def __init__(self, document: ModelDocument) -> None:
        self._items: list[tuple[str, Path_]] = []
        super().__init__(document)

    def row_keys(self) -> list[tuple[str, int]]:
        self._items = [
            (rel, path)
            for rel in (*self.document.rels("config/"), *self.document.rels("links/"))
            for path in sourced_paths(self.document.data(rel))
        ]
        return [(rel, position) for position, (rel, _path) in enumerate(self._items)]

    def item(self, row: int) -> tuple[str, Path_]:
        return self._items[row]

    def path_of(self, key: tuple[str, int], column: Column) -> Path_ | None:
        if not column.key:
            return None
        return (*self._items[key[1]][1], column.key)

    def label_of(self, key: tuple[str, int]) -> str:
        rel, path = self._items[key[1]]
        from budget_core.io.yamlio import format_path

        return f"{rel.split('/')[-1].removesuffix('.yaml')} {format_path(path)}"

    def is_placeholder_row(self, row: int) -> bool:
        rel, path = self._items[row]
        return is_placeholder(self.document.value(rel, path))

    def unit_of(self, row: int) -> str:
        path = self._items[row][1]
        names = [p for p in path if isinstance(p, str)]
        return (canonical_unit(names[-1]) or "") if names else ""

    def id_text(self, row: int, column: int) -> str:
        return self.label_of(self._keys[row]) if column == 0 else self.unit_of(row)

    def id_tip(self, row: int, column: int) -> str | None:
        return self._items[row][0] if column == 0 else None

    def display(self, row: int, column: int) -> str:
        if not self.columns[column].key:
            return self.id_text(row, column)
        value = self.value_of(row, column)
        if column == 1:
            return "" if value is None else (str(value) if isinstance(value, str) else f"{value:g}")
        return "" if value is None else str(value)

    def state_of(self, row: int, column: int) -> Status | None:
        found = self.cell(row, column)
        if found is not None and self.document.problem_at(*found) is not None:
            return Status.FAIL
        if column in (1, 3) and self.is_placeholder_row(row):
            return Status.PLACEHOLDER
        return None

    def tooltip(self, row: int, column: int) -> str | None:
        base = super().tooltip(row, column)
        if column in (1, 3) and self.is_placeholder_row(row):
            note = (
                "Placeholder: no value or source. Results that depend on it show n/a. "
                "Type the value and its source."
            )
            return f"{note}\n{base}" if base else note
        return base

    def column_tip(self, column: Column) -> str:
        return {
            "value": "The number, in the unit of the field.",
            "source": "Where the number comes from (a standard, a data sheet, a requirement). "
            "'TBD' marks a placeholder.",
        }.get(column.key, column.title)

    def change_for(
        self, row: int, column: int, text: str
    ) -> tuple[str, Callable[[dict[str, Any]], None], str] | None:
        if column == 1:  # an emptied value is a placeholder: the field stays, its value is null
            rel, path = self._items[row]
            parsed = parse_cell(text, self.columns[1])

            def apply_value(data: dict[str, Any]) -> None:
                node = value_at(data, path)
                if isinstance(node, dict):
                    node["value"] = parsed

            return rel, apply_value, f"Edit {self.label_of(self._keys[row])}: value"
        if column == 4:  # an emptied note is dropped
            rel, path = self._items[row]
            stripped = text.strip()

            def apply_note(data: dict[str, Any]) -> None:
                node = value_at(data, path)
                if isinstance(node, dict):
                    if stripped:
                        node["note"] = stripped
                    else:
                        node.pop("note", None)

            return rel, apply_note, f"Edit {self.label_of(self._keys[row])}: note"
        return super().change_for(row, column, text)
