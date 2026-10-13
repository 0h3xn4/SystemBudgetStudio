"""How a cell looks: numbers, placeholders, n/a, limit states, margin bars, the legend (D-150)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTableView

from budget_core.reports.document import NA, Column, Table
from budget_gui import theme
from budget_gui.delegates import (
    MARGIN_ROLE,
    NUMERIC_ROLE,
    STATE_ROLE,
    CellDelegate,
    status_of,
    tooltip_for,
)
from budget_gui.legend import ROWS, CellStyleLegend, LegendDialog
from budget_gui.main_window import MainWindow
from budget_gui.theme import DARK, LIGHT, Mode, Status
from budget_gui.widgets import DocTableModel


def render(qtbot, text: str, status: Status | None, *, numeric=True, share=None) -> QImage:  # type: ignore[no-untyped-def]
    """One cell in a table with the delegate, as an image."""
    model = QStandardItemModel(1, 1)
    item = QStandardItem(text)
    item.setData(status.value if status else None, STATE_ROLE)
    item.setData(numeric, NUMERIC_ROLE)
    item.setData(share, MARGIN_ROLE)
    model.setItem(0, 0, item)
    view = QTableView()
    qtbot.addWidget(view)
    view.setModel(model)
    view.setItemDelegate(CellDelegate(view))
    view.horizontalHeader().setVisible(False)
    view.verticalHeader().setVisible(False)
    view.setShowGrid(False)
    view.setColumnWidth(0, 160)
    view.setRowHeight(0, 32)
    view.resize(164, 36)
    view.show()
    return view.grab().toImage()


def pixels(image: QImage) -> set[str]:
    return {
        image.pixelColor(x, y).name()
        for x in range(0, image.width(), 1)
        for y in range(0, image.height(), 1)
    }


@pytest.mark.parametrize("status", list(Status))
def test_a_state_paints_its_tint_and_its_text_colour(qtbot, status: Status) -> None:  # type: ignore[no-untyped-def]
    style = LIGHT.status(status)
    image = render(qtbot, "1.0", status)
    assert style.bg in pixels(image)  # the tint behind the cell
    # Text and icons are anti-aliased (and differ by platform), so the exact foreground colour
    # need not occur: a pixel close to it must, and it must be far from the tint.
    assert has_pixel_near(image, style.fg, tolerance=24)


def has_pixel_near(image: QImage, colour: str, *, tolerance: int) -> bool:
    want = QColor(colour)
    for x in range(image.width()):
        for y in range(image.height()):
            got = image.pixelColor(x, y)
            if (
                abs(got.red() - want.red()) <= tolerance
                and abs(got.green() - want.green()) <= tolerance
                and abs(got.blue() - want.blue()) <= tolerance
            ):
                return True
    return False


def test_a_plain_number_has_no_tint(qtbot) -> None:  # type: ignore[no-untyped-def]
    image = render(qtbot, "1.250", None)
    # A pixel in the corner of the cell, where no text or icon is. (Anti-aliased text can blend
    # into the exact colour of a tint, so looking for the colour anywhere in the image is unsafe.)
    corner = image.pixelColor(8, 8).name()
    for status in Status:
        assert LIGHT.status(status).bg != corner


def test_n_a_does_not_look_like_zero_or_like_an_empty_cell(qtbot) -> None:  # type: ignore[no-untyped-def]
    na = render(qtbot, "n/a", Status.NOT_CHECKED, numeric=False)
    zero = render(qtbot, "0.000", None)
    empty = render(qtbot, "", None, numeric=False)
    assert na != zero and na != empty and zero != empty


def test_a_placeholder_has_a_dashed_border(qtbot) -> None:  # type: ignore[no-untyped-def]
    image = render(qtbot, "12.0", Status.PLACEHOLDER)
    fg = QColor(LIGHT.s_placeholder.fg).name()
    top = [image.pixelColor(x, 2).name() for x in range(8, image.width() - 8)]
    # a dashed line alternates between the colour of the border and the tint behind it
    assert fg in top and LIGHT.s_placeholder.bg in top


def test_a_margin_bar_is_as_long_as_the_share_of_the_limit_used(qtbot) -> None:  # type: ignore[no-untyped-def]
    def bar_length(share: float) -> int:
        image = render(qtbot, "0.2", Status.PASS, share=share)
        fg = QColor(LIGHT.s_pass.fg).name()
        y = image.height() - 6
        return sum(1 for x in range(image.width()) if image.pixelColor(x, y).name() == fg)

    short, long_, over = bar_length(0.25), bar_length(0.75), bar_length(1.5)
    assert 0 < short < long_ <= over
    assert over >= 140  # more than the limit: the bar is full, never longer than the cell


def test_the_cell_follows_the_theme(qtbot) -> None:  # type: ignore[no-untyped-def]
    light = render(qtbot, "n/a", Status.NOT_CHECKED, numeric=False)
    theme.manager().set_mode(Mode.DARK)
    dark = render(qtbot, "n/a", Status.NOT_CHECKED, numeric=False)
    assert DARK.s_not_checked.bg in pixels(dark)
    assert LIGHT.s_not_checked.bg in pixels(light) and light != dark


def test_status_of_and_the_tooltips() -> None:
    assert status_of("fail") is Status.FAIL and status_of(None) is None
    assert status_of("nonsense") is None
    for status in Status:
        assert tooltip_for(status)
    assert "Source: datasheet rev C" in (tooltip_for(Status.PASS, "datasheet rev C") or "")
    assert tooltip_for(None) is None
    assert "placeholder" in tooltip_for(Status.NOT_CHECKED).lower()  # type: ignore[union-attr]


def test_the_report_tables_mark_n_a_as_not_checked_with_a_tooltip(qtbot) -> None:  # type: ignore[no-untyped-def]
    table = Table(
        "T",
        (Column("Name", "text"), Column("Mass (kg)", "number", 3)),
        (("a", 1.5), ("b", None)),
    )
    model = DocTableModel(table)
    n_a = model.index(1, 1)
    assert model.data(n_a) == NA
    assert model.data(n_a, STATE_ROLE) == Status.NOT_CHECKED.value
    assert "placeholder" in model.data(n_a, Qt.ItemDataRole.ToolTipRole).lower()
    value = model.index(0, 1)
    assert model.data(value, STATE_ROLE) is None and model.data(value, NUMERIC_ROLE) is True
    assert model.data(model.index(0, 0), NUMERIC_ROLE) is False


def test_the_legend_lists_every_style_with_the_same_delegate(qtbot) -> None:  # type: ignore[no-untyped-def]
    legend = CellStyleLegend()
    qtbot.addWidget(legend)
    model = legend.model()
    assert model.rowCount() == len(ROWS) == 7
    states = {status_of(model.index(r, 1).data(STATE_ROLE)) for r in range(model.rowCount())} - {
        None
    }
    assert states == set(Status)  # every status has an example
    assert isinstance(legend.itemDelegateForColumn(1), CellDelegate)
    legend.resize(760, 620)
    legend.show()
    assert LIGHT.s_placeholder.bg in pixels(legend.grab().toImage())


def test_the_view_menu_opens_the_legend_and_switches_the_theme(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    dialog = window.show_cell_styles()
    assert isinstance(dialog, LegendDialog) and dialog.windowTitle() == "Cell styles"
    dialog.close()
    assert set(window.theme_actions) == set(Mode)
    window.theme_actions[Mode.DARK].trigger()
    assert theme.tokens() is DARK and window.theme_actions[Mode.DARK].isChecked()
    window.theme_actions[Mode.LIGHT].trigger()
    assert theme.tokens() is LIGHT


def test_the_chosen_theme_is_kept_for_the_next_start(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from budget_gui.app import create_app

    monkeypatch.delenv("BUDGET_NO_LAYOUT", raising=False)
    monkeypatch.setenv("BUDGET_CONFIG_DIR", str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_theme(Mode.DARK)
    text = (tmp_path / "layout.ini").read_text(encoding="utf-8")
    assert "[theme]" in text and "mode=dark" in text
    theme.manager().set_mode(Mode.LIGHT)
    create_app(["x"])  # the next start reads the file
    assert theme.manager().mode is Mode.DARK
    assert [ln for ln in text.splitlines() if ln.startswith("[")] == ["[theme]"]
