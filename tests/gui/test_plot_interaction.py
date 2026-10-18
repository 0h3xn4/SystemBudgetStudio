"""Plot interaction: legend hide and solo, violation markers, the time axis (UX step 3b, D-162)."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage

from budget_core.plots.spec import HLine, Panel, PlotSpec, Series
from budget_gui import theme
from budget_gui.plot_widget import PlotMarker, PlotWidget
from budget_gui.time_axis import ElapsedAxis, OrbitAxis, UtcAxis

N = 1000


def spec_two_panels() -> PlotSpec:
    x = np.arange(N, dtype=float)
    return PlotSpec(
        "t",
        (
            Panel(
                "Power",
                "Power (W)",
                (
                    Series("Generation", x, np.full(N, 60.0), "green", True, float(N)),
                    Series("Demand", x, np.full(N, 40.0), "blue", True, float(N)),
                ),
                (HLine("Limit", 80.0, "red"),),
                y_min=0.0,
                y_max=100.0,
            ),
            Panel("Battery", "SoC (%)", (Series("State of charge", x, np.full(N, 0.9)),)),
        ),
        x_max_s=float(N),
    )


@pytest.fixture
def plot(qtbot) -> PlotWidget:  # type: ignore[no-untyped-def]
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 600)
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_spec(spec_two_panels())
    widget.grab()
    return widget


def count_colour(image: QImage, colour: str, region: tuple[int, int, int, int]) -> int:
    x0, y0, x1, y1 = region
    target = theme.plot_colour(theme.tokens(), colour).rgb()
    return sum(
        1
        for x in range(x0, x1)
        for y in range(y0, y1)
        if image.pixel(x, y) & 0xFFFFFF == target & 0xFFFFFF
    )


# ---- legend ---------------------------------------------------------------------------------
def test_the_legend_lists_every_series_and_limit_of_every_panel(plot: PlotWidget) -> None:
    entries = plot.legend_entries()
    assert [(e.panel, e.label) for e in entries] == [
        (0, "Generation"),
        (0, "Demand"),
        (0, "Limit"),
        (1, "State of charge"),
    ]
    assert not any(e.hidden for e in entries)


def test_hiding_a_series_removes_it_from_the_plot_and_greys_its_entry(plot: PlotWidget) -> None:
    rect = plot._panel_rects()[0]
    region = (int(rect.left()), int(rect.top()), int(rect.right()), int(rect.bottom()))
    before = count_colour(plot.grab().toImage(), "green", region)
    assert before > 100
    plot.toggle_series(0, "Generation")
    image = plot.grab().toImage()
    assert count_colour(image, "green", region) == 0
    assert [e.hidden for e in plot.legend_entries()][:2] == [True, False]
    plot.toggle_series(0, "Generation")
    assert count_colour(plot.grab().toImage(), "green", region) == before


def test_a_click_on_a_legend_entry_hides_it_and_a_second_click_shows_it(
    plot: PlotWidget, qtbot
) -> None:  # type: ignore[no-untyped-def]
    entry = plot.legend_entries()[1]  # Demand
    point = QPoint(int(entry.rect.center().x()), int(entry.rect.center().y()))
    qtbot.mouseClick(plot, Qt.MouseButton.LeftButton, pos=point)
    assert plot.legend_entries()[1].hidden
    assert plot.cursor_s() is None and plot.pinned_s() is None  # it was not a click on the plot
    plot.grab()
    entry = plot.legend_entries()[1]
    qtbot.mouseClick(
        plot,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(entry.rect.center().x()), int(entry.rect.center().y())),
    )
    assert not plot.legend_entries()[1].hidden


def test_solo_keeps_one_series_of_a_panel_and_a_second_solo_brings_the_others_back(
    plot: PlotWidget,
) -> None:
    plot.solo_series(0, "Demand")
    hidden = {(e.panel, e.label) for e in plot.legend_entries() if e.hidden}
    assert hidden == {(0, "Generation"), (0, "Limit")}  # the other panel is untouched
    plot.solo_series(0, "Demand")
    assert not any(e.hidden for e in plot.legend_entries())


def test_a_shift_click_is_a_solo(plot: PlotWidget, qtbot) -> None:  # type: ignore[no-untyped-def]
    entry = plot.legend_entries()[0]
    point = QPoint(int(entry.rect.center().x()), int(entry.rect.center().y()))
    qtbot.mouseClick(plot, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=point)
    assert {e.label for e in plot.legend_entries() if e.hidden} == {"Demand", "Limit"}


def test_a_new_plot_shows_everything_again(plot: PlotWidget) -> None:
    plot.toggle_series(0, "Generation")
    plot.set_spec(spec_two_panels())
    assert not any(e.hidden for e in plot.legend_entries())


# ---- markers --------------------------------------------------------------------------------
def test_markers_are_drawn_in_the_fail_colour_at_the_top_of_every_panel(plot: PlotWidget) -> None:
    fail = theme.tokens().status(theme.Status.FAIL).fg
    plot.set_markers([PlotMarker(200.0, 300.0, "peak power")])
    image = plot.grab().toImage()
    for rect in plot._panel_rects():
        row = int(rect.top()) + 2
        x = int(plot.time_to_x(250.0))
        assert image.pixelColor(x, row).name() == fail
    outside = int(plot.time_to_x(600.0))
    assert image.pixelColor(outside, int(plot._panel_rects()[0].top()) + 2).name() != fail


def test_a_marker_survives_switching_the_shading_off(plot: PlotWidget) -> None:
    fail = theme.tokens().status(theme.Status.FAIL).fg
    plot.set_markers([PlotMarker(200.0, 300.0)])
    plot.set_shading(False)
    x = int(plot.time_to_x(250.0))
    assert plot.grab().toImage().pixelColor(x, int(plot._panel_rects()[0].top()) + 2).name() == fail


def test_the_selected_marker_is_shaded_across_the_panel(plot: PlotWidget) -> None:
    plot.set_markers([PlotMarker(200.0, 300.0)], selected=0)
    rect = plot._panel_rects()[0]
    middle = plot.grab().toImage().pixelColor(int(plot.time_to_x(250.0)), int(rect.center().y()))
    plain = plot.grab().toImage().pixelColor(int(plot.time_to_x(700.0)), int(rect.center().y()))
    assert middle != plain


def test_clicking_a_marker_says_which(plot: PlotWidget, qtbot) -> None:  # type: ignore[no-untyped-def]
    plot.set_markers([PlotMarker(100.0, 150.0), PlotMarker(400.0, 460.0)])
    plot.grab()
    top = int(plot._panel_rects()[0].top()) + 3
    with qtbot.waitSignal(plot.marker_clicked, timeout=500) as signal:
        qtbot.mouseClick(
            plot, Qt.MouseButton.LeftButton, pos=QPoint(int(plot.time_to_x(430.0)), top)
        )
    assert signal.args == [1]
    assert plot.pinned_s() is None


def test_markers_are_kept_across_a_new_spec_only_when_set_again(plot: PlotWidget) -> None:
    plot.set_markers([PlotMarker(1.0, 2.0)])
    plot.set_spec(spec_two_panels())
    assert plot.markers() == []


# ---- time axis ------------------------------------------------------------------------------
def test_the_axis_can_be_elapsed_utc_or_orbits(plot: PlotWidget) -> None:
    elapsed = plot.grab().toImage()
    plot.set_time_axis(UtcAxis(datetime(2026, 6, 1, tzinfo=UTC)))
    utc = plot.grab().toImage()
    assert plot.time_axis().name == "utc" and utc != elapsed
    assert plot.axis_title() == "UTC (a date marks midnight)"
    plot.set_time_axis(OrbitAxis(100.0))
    assert plot.axis_title().startswith("Orbit number")
    plot.set_time_axis(ElapsedAxis())
    assert plot.grab().toImage() == elapsed


def test_a_new_spec_keeps_the_chosen_axis(plot: PlotWidget) -> None:
    plot.set_time_axis(UtcAxis(datetime(2026, 6, 1, tzinfo=UTC)))
    plot.set_spec(spec_two_panels())
    assert plot.time_axis().name == "utc"
