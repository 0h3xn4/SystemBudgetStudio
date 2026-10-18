"""The three grid pages of the Model tab: units, power modes and sourced inputs (D-159)."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QCheckBox, QMenu

from budget_gui import icons
from budget_gui.grid_models import PowerModesModel, SourcedModel, UnitsModel
from budget_gui.grid_view import GridPage
from budget_gui.model_document import ModelDocument


class UnitsPage(GridPage):
    """One row per unit: name, subsystem, bus, maturity, mass and temperature limits."""

    def __init__(self, document: ModelDocument) -> None:
        self.units = UnitsModel(document)
        super().__init__(
            self.units, document, what="unit", filter_hint="Filter units (name, subsystem, bus…)"
        )

    def select_unit(self, unit_id: str) -> bool:
        self.filter.clear()
        row = self.units.row_of(unit_id)
        return row >= 0 and self.table.select_cell(row, 1)


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
