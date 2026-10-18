"""Helpers for the window tests that edit the grids of the Model tab."""

from __future__ import annotations

from budget_gui.main_window import MainWindow


def mode_row(window: MainWindow, unit_id: str, mode: str) -> int:
    """The row of a unit's power mode in the Power modes grid (source row)."""
    model = window.modes_page.modes
    return next(r for r in model.rows_of(unit_id) if model.index(r, 1).data() == mode)


def mode_column(window: MainWindow, field: str) -> int:
    return next(i for i, c in enumerate(window.modes_page.modes.columns) if c.key == field)


def set_mode_value(window: MainWindow, unit_id: str, mode: str, field: str, text: str) -> bool:
    """Type `text` into a cell of the Power modes grid."""
    model = window.modes_page.modes
    row, column = mode_row(window, unit_id, mode), mode_column(window, field)
    return model.setData(model.index(row, column), text)


def unit_column(window: MainWindow, field: str) -> int:
    return next(i for i, c in enumerate(window.units_page.units.columns) if c.key == field)


def set_unit_value(window: MainWindow, unit_id: str, field: str, text: str) -> bool:
    model = window.units_page.units
    return model.setData(model.index(model.row_of(unit_id), unit_column(window, field)), text)
