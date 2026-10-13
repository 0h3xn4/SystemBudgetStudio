"""Hovering over a plot draws the cursor on a kept picture of the plot (audit GUI-28, D-147)."""

from __future__ import annotations

import time

import numpy as np
import pytest
from PySide6.QtGui import QImage

from budget_core.plots.spec import Panel, PlotSpec, Series
from budget_gui.plot_widget import PlotWidget

N = 604_800  # a week at 1 s


def week_spec(series_per_panel: int = 5, panels: int = 4) -> PlotSpec:
    x = np.arange(N, dtype=np.float64)
    return PlotSpec(
        "week",
        tuple(
            Panel(
                f"p{k}",
                "W",
                tuple(
                    Series(
                        f"s{k}{m}",
                        x,
                        np.sin(x / (900 + 37 * k + 11 * m)) * 30 + 40 + m,
                        step=m % 2 == 0,
                        x_end=float(N),
                    )
                    for m in range(series_per_panel)
                ),
            )
            for k in range(panels)
        ),
        x_max_s=float(N),
    )


@pytest.fixture
def plot(qtbot) -> PlotWidget:  # type: ignore[no-untyped-def]
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 650)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def test_moving_the_cursor_does_not_draw_the_plot_again(
    plot: PlotWidget, monkeypatch: pytest.MonkeyPatch
) -> None:
    plot.set_spec(week_spec(2, 2))
    plot.grab()
    drawn: list[int] = []
    original = PlotWidget._paint_panel

    def counting(self: PlotWidget, *args: object, **kwargs: object) -> None:
        drawn.append(1)
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(PlotWidget, "_paint_panel", counting)
    for t in (1000.0, 50_000.0, 300_000.0, 500_000.0):
        plot.set_cursor(t)
        plot.repaint()
    plot.pin_cursor(2000.0)
    plot.repaint()
    assert drawn == []  # the kept picture was used every time


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.zoom(2.0, 100_000.0),
        lambda p: p.pan(1000.0),
        lambda p: p.set_shading(False),
        lambda p: p.resize(700, 500),
    ],
    ids=["zoom", "pan", "shading", "resize"],
)
def test_a_change_of_view_shading_or_size_draws_the_plot_again(
    plot: PlotWidget, monkeypatch: pytest.MonkeyPatch, change
) -> None:  # type: ignore[no-untyped-def]
    plot.set_spec(week_spec(1, 2))
    plot.zoom(2.0, 100_000.0)  # so that a pan has room
    plot.grab()
    drawn: list[int] = []
    original = PlotWidget._paint_panel

    def counting(self: PlotWidget, *args: object, **kwargs: object) -> None:
        drawn.append(1)
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(PlotWidget, "_paint_panel", counting)
    change(plot)
    plot.grab()
    assert len(drawn) == 2  # both panels, once


def test_a_new_plot_replaces_the_kept_picture(plot: PlotWidget) -> None:
    plot.set_spec(week_spec(1, 1))
    before = plot.grab().toImage()
    x = np.arange(100, dtype=np.float64)
    plot.set_spec(PlotSpec("other", (Panel("p", "V", (Series("s", x, x * 0.0 + 5.0),)),)))
    after = plot.grab().toImage()
    assert before != after


def test_the_cursor_is_drawn_over_the_kept_picture(plot: PlotWidget) -> None:
    plot.set_spec(week_spec(1, 1))
    plain: QImage = plot.grab().toImage()
    plot.set_cursor(300_000.0)
    with_cursor: QImage = plot.grab().toImage()
    x = int(plot.time_to_x(300_000.0))
    assert plain != with_cursor
    changed_columns = {
        px
        for px in range(plain.width())
        for py in range(0, plain.height(), 5)
        if plain.pixel(px, py) != with_cursor.pixel(px, py)
    }
    assert x in changed_columns or x - 1 in changed_columns or x + 1 in changed_columns
    plot.set_cursor(None)
    assert plot.grab().toImage() == plain  # nothing of the cursor is left in the kept picture


def test_hovering_over_twenty_series_of_a_week_is_quick(plot: PlotWidget) -> None:
    plot.set_spec(week_spec())  # 20 series of 604,800 points: about 0.13 s a paint before D-147
    plot.grab()
    start = time.perf_counter()
    for i in range(20):
        plot.set_cursor(1000.0 + i * 20_000.0)
        plot.repaint()
    per_paint = (time.perf_counter() - start) / 20
    assert per_paint < 0.05  # about 0.001 s now; the bound leaves room for a slow machine
