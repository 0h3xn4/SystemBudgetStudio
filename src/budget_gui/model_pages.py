"""The three grid pages of the Model tab: units, power modes and sourced inputs (D-159)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QCheckBox, QDialog, QMenu

from budget_core.model import Unit
from budget_core.new_unit import UnitAnswers, unit_data
from budget_gui import icons
from budget_gui.add_unit_dialog import AddUnitDialog
from budget_gui.grid_models import PowerModesModel, SourcedModel, UnitsModel
from budget_gui.grid_view import GridPage
from budget_gui.model_document import ModelDocument


def _assign(unit_id: str, mode: str) -> Callable[[dict[str, Any]], None]:
    """An edit of a spacecraft mode file: this unit does `mode` in it."""

    def apply(data: dict[str, Any]) -> None:
        data["assignments"][unit_id] = mode

    return apply


def _unassign(unit_id: str) -> Callable[[dict[str, Any]], None]:
    """An edit of a spacecraft mode file: the unit is no longer in it."""

    def apply(data: dict[str, Any]) -> None:
        data["assignments"].pop(unit_id, None)

    return apply


class UnitsPage(GridPage):
    """One row per unit: name, subsystem, bus, maturity, mass and temperature limits. Add a unit
    (a form that asks for the numbers it needs) and remove one (D-187)."""

    def __init__(self, document: ModelDocument) -> None:
        self.units = UnitsModel(document)
        super().__init__(
            self.units, document, what="unit", filter_hint="Filter units (name, subsystem, bus…)"
        )
        self.add_button = self.bar.make_button(
            "Add unit",
            "plus",
            "Add a unit: a form asks for its mass and first power mode",
            "Ctrl+Shift+N",
        )
        self.remove_button = self.bar.make_button(
            "Remove unit",
            "trash-2",
            "Remove the selected unit (Undo brings it back; Save deletes its file)",
            "Ctrl+Shift+Delete",
        )
        self.add_button.clicked.connect(self.add_unit)
        self.remove_button.clicked.connect(self.remove_unit)
        self.add_tool(self.add_button)
        self.add_tool(self.remove_button)
        self.table.extra_actions.append(self._menu)

    def _menu(self, menu: QMenu, row: int) -> None:
        menu.addSeparator()
        add = QAction(icons.icon("plus"), "Add a unit…", menu)
        add.triggered.connect(self.add_unit)
        remove = QAction(icons.icon("trash-2"), "Remove this unit", menu)
        remove.setEnabled(row >= 0)
        remove.triggered.connect(self.remove_unit)
        menu.addAction(add)
        menu.addAction(remove)

    def select_unit(self, unit_id: str) -> bool:
        self.filter.clear()
        row = self.units.row_of(unit_id)
        return row >= 0 and self.table.select_cell(row, 1)

    def buses(self) -> list[str]:
        found = self.document.value("spacecraft.yaml", ("buses",))
        names = (
            [b.get("name") for b in found if isinstance(b, dict)] if isinstance(found, list) else []
        )
        return [name for name in names if isinstance(name, str)]

    def maturity_classes(self) -> list[str]:
        classes = self.document.value("config/margin_policy.yaml", ("classes",))
        return list(classes) if isinstance(classes, dict) else []

    def thermal_nodes(self) -> list[str] | None:
        """The nodes of the thermal model; None when the project has none."""
        if not self.document.has("config/thermal_model.yaml"):
            return None
        nodes = self.document.value("config/thermal_model.yaml", ("nodes",))
        return list(nodes) if isinstance(nodes, dict) else []

    def _ask(
        self,
        existing: list[str],
        buses: list[str],
        classes: list[str],
        thermal_nodes: list[str] | None,
    ) -> UnitAnswers | None:
        """The form; the tests put their own answers here."""
        dialog = AddUnitDialog(existing, buses, classes, self, thermal_nodes)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.answers()

    def add_unit(self) -> bool:
        buses, classes = self.buses(), self.maturity_classes()
        if not buses:
            self.show_message("The spacecraft has no bus: add one in spacecraft.yaml first.")
            return False
        if not classes:
            self.show_message(
                "The margin policy has no maturity class: add one in "
                "config/margin_policy.yaml first."
            )
            return False
        existing = [
            rel.removeprefix("units/").removesuffix(".yaml") for rel in self.document.rels("units/")
        ]
        answers = self._ask(existing, buses, classes, self.thermal_nodes())
        if answers is None:
            return False
        try:
            data = unit_data(answers)
        except ValueError:
            self.show_message("The answers do not make a valid unit.")
            return False
        unit_id, mode = answers.unit_id.strip(), answers.mode_name.strip()
        rel = f"units/{unit_id}.yaml"
        document = self.document
        document.undo_stack.beginMacro(f"Add unit {unit_id}")
        try:
            if not document.add_file(rel, Unit, data, f"Add unit {unit_id}"):
                self.show_message(
                    f"There is already a file for {unit_id} (removed in this session? Undo it, or "
                    "Save first)."
                )
                return False
            # every spacecraft mode has to say what the unit does: the power mode just given
            modes = document.rels("modes/")
            document.edit([(m, _assign(unit_id, mode)) for m in modes], f"Add unit {unit_id}")
        finally:
            document.undo_stack.endMacro()
        self.select_unit(unit_id)
        placed = (
            f" and put it in {len(modes)} spacecraft mode{'s' if len(modes) != 1 else ''} "
            f"with the power mode {mode} (change that in modes/)"
            if modes
            else ""
        )
        self.show_message(
            f"Added {unit_id}{placed}. Save (Ctrl+S) writes units/{unit_id}.yaml; Undo with Ctrl+Z."
        )
        return True

    def remove_unit(self) -> bool:
        current = self.table.current_cell()
        if current is None:
            self.show_message("Select the unit to remove first.")
            return False
        key = self.units._keys[current[0]]
        rel, unit_id = key[0], self.units.label_of(key)
        document = self.document
        using = [
            m
            for m in document.rels("modes/")
            if unit_id in (document.value(m, ("assignments",)) or {})
        ]
        alone = [
            m.removeprefix("modes/").removesuffix(".yaml")
            for m in using
            if len(document.value(m, ("assignments",))) <= 1
        ]
        if alone:
            self.show_message(
                f"{unit_id} is the only unit of the spacecraft mode(s) {', '.join(alone)}: a mode "
                "needs at least one unit. It was not removed."
            )
            return False
        document.undo_stack.beginMacro(f"Remove unit {unit_id}")
        try:
            document.edit([(m, _unassign(unit_id)) for m in using], f"Remove unit {unit_id}")
            removed = document.remove_file(rel, f"Remove unit {unit_id}")
        finally:
            document.undo_stack.endMacro()
        if not removed:
            return False
        note = f" and took it out of {len(using)} spacecraft mode(s)" if using else ""
        self.show_message(
            f"Removed {unit_id}{note}. Save (Ctrl+S) deletes {rel}; "
            "Undo with Ctrl+Z brings it back."
        )
        return True


class PowerModesPage(GridPage):
    """One row per power mode of every unit; add and remove modes."""

    def __init__(self, document: ModelDocument) -> None:
        self.modes = PowerModesModel(document)
        super().__init__(
            self.modes,
            document,
            what="power mode",
            filter_hint="Filter power modes (unit or mode name…)",
        )
        self.add_button = self.bar.make_button(
            "Add mode", "plus", "Add a power mode to the unit of the selected row"
        )
        self.remove_button = self.bar.make_button(
            "Remove mode", "trash-2", "Remove the selected power mode (Undo brings it back)"
        )
        self.add_button.clicked.connect(self.add_mode)
        self.remove_button.clicked.connect(self.remove_mode)
        self.add_tool(self.add_button)
        self.add_tool(self.remove_button)
        self.table.extra_actions.append(self._menu)

    def _menu(self, menu: QMenu, row: int) -> None:
        menu.addSeparator()
        add = QAction(icons.icon("plus"), "Add a mode to this unit", menu)
        add.triggered.connect(self.add_mode)
        remove = QAction(icons.icon("trash-2"), "Remove this mode", menu)
        remove.triggered.connect(self.remove_mode)
        menu.addAction(add)
        menu.addAction(remove)

    def select_unit(self, unit_id: str) -> bool:
        self.filter.clear()
        rows = self.modes.rows_of(unit_id)
        return bool(rows) and self.table.select_cell(rows[0], 1)

    def add_mode(self) -> bool:
        current = self.table.current_cell()
        if current is None:
            self.show_message("Select a row of the unit first, then add a mode.")
            return False
        rel = self.modes.cell(current[0], 2)
        if rel is None:
            return False
        if not self.modes.add_mode(rel[0]):
            return False
        unit = rel[0].removeprefix("units/").removesuffix(".yaml")
        self.show_message(f"Added a mode to {unit}. Name it and give its powers. Undo with Ctrl+Z.")
        return True

    def remove_mode(self) -> bool:
        current = self.table.current_cell()
        if current is None:
            self.show_message("Select the power mode to remove first.")
            return False
        label = self.modes.label_of(self.modes._keys[current[0]])
        if not self.modes.remove_mode(current[0]):
            self.show_message("A unit needs at least one power mode: it was not removed.")
            return False
        self.show_message(f"Removed {label}. Undo with Ctrl+Z.")
        return True


class InputsPage(GridPage):
    """Every sourced number of the configuration and the links: value, unit and source."""

    def __init__(self, document: ModelDocument) -> None:
        self.inputs = SourcedModel(document)
        super().__init__(
            self.inputs,
            document,
            what="input",
            filter_hint="Filter inputs (file, field, source…)",
        )
        self.only_placeholders = QCheckBox("Placeholders only")
        self.only_placeholders.setToolTip("Show only the numbers without a value or a source")
        self.only_placeholders.toggled.connect(self._placeholders_toggled)
        self.add_tool(self.only_placeholders)
        self.table.extra_actions.append(self._menu)
        document.changed.connect(self._count)
        self._count()

    def _menu(self, menu: QMenu, row: int) -> None:
        if row < 0:
            return
        menu.addSeparator()
        mark = QAction(icons.icon("pencil"), "Mark as sourced…", menu)
        mark.setEnabled(self.inputs.is_placeholder_row(row))
        mark.triggered.connect(lambda _c=False, r=row: self.mark_as_sourced(r))
        menu.addAction(mark)

    def mark_as_sourced(self, row: int) -> bool:
        """Take the cursor to what a placeholder lacks: the value first, then the source."""
        column = 1 if self.inputs.value_of(row, 1) is None else 3
        if not self.table.select_cell(row, column):
            return False
        self.table.view.edit(self.table.view.currentIndex())
        self.show_message(
            "Type the value, then its source (a standard, data sheet or requirement)."
        )
        return True

    def _placeholders_toggled(self, on: bool) -> None:
        self.table.set_row_test(self.inputs.is_placeholder_row if on else None)
        self._refresh()

    def placeholder_count(self) -> int:
        return sum(self.inputs.is_placeholder_row(r) for r in range(self.inputs.rowCount()))

    def _count(self) -> None:
        n = self.placeholder_count()
        self.only_placeholders.setText(f"Placeholders only ({n})")
