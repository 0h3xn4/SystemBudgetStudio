"""Budget tables: two-line headers, a totals row, text that fits its column (D-163)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QTableView

from budget_core.reports.document import Column, Table
from budget_gui.delegates import PAD, TOTAL_ROLE, CellDelegate
from budget_gui.widgets import DocTableModel, wrap_header


def test_a_long_header_is_broken_at_the_space_nearest_the_middle() -> None:
    assert wrap_header("Average, unit margins (W)") == "Average, unit\nmargins (W)"
    assert wrap_header("Peak at source, with margins (W)") == "Peak at source,\nwith margins (W)"
    assert wrap_header("Mode") == "Mode"
    assert wrap_header("Averyveryverylongsingleword") == "Averyveryverylongsingleword"


def test_the_header_keeps_its_whole_text_as_a_tooltip() -> None:
    table = Table("t", (Column("Average, unit margins (W)"),), ((1.0,),))
    model = DocTableModel(table)
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Average, unit\nmargins (W)"
    tip = model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
    assert tip == "Average, unit margins (W)"


def test_only_the_last_row_of_a_table_that_asks_for_it_is_a_totals_row() -> None:
    rows = (("a", 1.0), ("b", 2.0), ("Total", 3.0))
    plain = DocTableModel(Table("t", (Column("x"), Column("y", "number", 1)), rows))
    totals = DocTableModel(
        Table("t", (Column("x"), Column("y", "number", 1)), rows, emphasise_last_row=True)
    )
    assert [plain.index(r, 1).data(TOTAL_ROLE) for r in range(3)] == [False] * 3
    assert [totals.index(r, 1).data(TOTAL_ROLE) for r in range(3)] == [False, False, True]


@pytest.mark.parametrize("value", ["Downlink", "Separation adapter", 1.0, 147.46])
def test_a_column_sized_to_its_contents_does_not_cut_the_text(qtbot, value) -> None:  # type: ignore[no-untyped-def]
    numeric = not isinstance(value, str)
    table = Table("t", (Column("c", "number" if numeric else "text", 3),), ((value,),))
    view = QTableView()
    qtbot.addWidget(view)
    view.setModel(DocTableModel(table))
    delegate = CellDelegate(view)
    view.setItemDelegate(delegate)
    view.show()
    view.resizeColumnsToContents()
    shown = view.model().index(0, 0).data(Qt.ItemDataRole.DisplayRole)
    font = delegate._font_for(view.font(), numeric, None)
    available = view.columnWidth(0) - 1 - 2 * PAD  # minus the grid line and the padding
    assert QFontMetrics(font).horizontalAdvance(shown) <= available
