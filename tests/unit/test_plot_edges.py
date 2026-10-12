"""Plot edge cases: missing samples break the line, a single sample is visible, tick labels differ,
the legend stays inside the picture (audit RC-20)."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from budget_core.plots.render import RIGHT, render_png
from budget_core.plots.spec import (
    BLUE,
    Panel,
    PlotSpec,
    Series,
    decimate,
    finite_runs,
    nice_ticks,
    tick_labels,
)


def spec_with(series: tuple[Series, ...], **panel: object) -> PlotSpec:
    return PlotSpec("T", (Panel("P", "Y", series, **panel),), (), 0.0, 100.0)  # type: ignore[arg-type]


def test_finite_runs_split_at_missing_samples() -> None:
    x = np.arange(7.0)
    y = np.array([1.0, 2.0, np.nan, 4.0, np.inf, 6.0, 7.0])
    runs = finite_runs(x, y)
    assert [r[0].tolist() for r in runs] == [[0.0, 1.0], [3.0], [5.0, 6.0]]


def test_a_nan_breaks_the_drawn_line() -> None:
    x = np.linspace(0.0, 100.0, 11)
    y = np.full(11, 5.0)
    y[5] = np.nan
    broken = render_png(spec_with((Series("s", x, y),), y_min=0.0, y_max=10.0))
    y_filled = y.copy()
    y_filled[5] = 5.0
    joined = render_png(spec_with((Series("s", x, y_filled),), y_min=0.0, y_max=10.0))
    a = np.asarray(Image.open(io.BytesIO(broken)).convert("L"))
    b = np.asarray(Image.open(io.BytesIO(joined)).convert("L"))
    # the series line is at y = 5 of 0..10: half way up the panel (rows 56..316)
    line = 186
    assert (b[line - 1 : line + 1, 650:820] < 200).any(axis=0).all()  # the joined plot is inked
    assert (a[line - 1 : line + 1, 650:820] > 200).all()  # the gap: no line across the NaN


def test_a_single_sample_is_drawn_as_a_marker() -> None:
    one = Series("s", np.array([50.0]), np.array([5.0]), BLUE)
    with_marker = render_png(spec_with((one,), y_min=0.0, y_max=10.0))
    without = render_png(
        spec_with((Series("s", np.array([]), np.array([]), BLUE),), y_min=0.0, y_max=10.0)
    )
    assert with_marker != without


def test_tick_labels_do_not_repeat() -> None:
    ticks = nice_ticks(0.01, 0.03, 5)
    labels = tick_labels(ticks)
    assert len(set(labels)) == len(labels)
    assert labels[0] == "0.010" and labels[-1] == "0.030"
    assert tick_labels([0.0, 2.0, 4.0]) == ["0", "2", "4"]
    assert tick_labels([-0.5, 0.0, 0.5]) == ["-0.5", "0.0", "0.5"]
    assert tick_labels([0.0, 2.5e6, 5.0e6]) == ["0", "2.5e+06", "5e+06"]


def test_decimation_keeps_peaks_with_missing_samples() -> None:
    x = np.arange(1000.0)
    y = np.sin(x / 10.0)
    y[500:510] = np.nan
    y[100] = 5.0
    dx, dy = decimate(x, y, 20)
    assert dy[np.isfinite(dy)].max() == 5.0  # the peak survives
    assert np.isnan(dy).any()  # and so does the gap


def test_many_series_keep_the_legend_inside_the_picture() -> None:
    x = np.linspace(0.0, 100.0, 20)
    series = tuple(
        Series(f"Margin at series number {i} of many", x, x * (i + 1) / 10.0, BLUE)
        for i in range(14)
    )
    png = render_png(spec_with(series))
    image = np.asarray(Image.open(io.BytesIO(png)).convert("L"))
    width = image.shape[1]
    strip = image[:300, width - RIGHT + 2 :]  # above the axis labels, right of the frame
    assert (strip > 250).all(), "legend or lines run into the right margin"


def test_rate_colours_do_not_repeat_for_ten_rates() -> None:
    from budget_core.plots.link import RATE_COLORS

    assert len(set(RATE_COLORS)) >= 10


def test_characters_the_font_lacks_are_drawn_as_question_marks() -> None:
    x = np.array([0.0, 100.0])
    shown = render_png(spec_with((Series("日本 ok", x, x, BLUE),)))
    expected = render_png(spec_with((Series("?? ok", x, x, BLUE),)))
    assert shown == expected
