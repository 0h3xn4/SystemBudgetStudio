"""A plot is prepared in the worker thread, so its first paint costs the window thread little
(D-182): the y ranges and the block summaries of the series, the power plot of both cases and the
plot of every link."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from budget_core.plots.envelope import BLOCK
from budget_core.plots.spec import HLine, Panel, PlotSpec, Series
from budget_gui import plot_widget
from budget_gui.main_window import MainWindow
from budget_gui.plot_prepare import PreparedPlot, panel_y_range, prepare
from budget_gui.plot_widget import PlotWidget

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
N = 20 * BLOCK


def long_spec() -> PlotSpec:
    x = np.arange(N, dtype=float)
    wave = 50.0 + 20.0 * np.sin(x / 90.0)
    return PlotSpec(
        "t",
        (
            Panel(
                "Power",
                "Power (W)",
                (Series("Generation", x, wave, "green"), Series("Demand", x, wave * 0.5, "blue")),
                (HLine("Limit", 80.0, "red"),),
            ),
            Panel("Battery", "SoC (%)", (Series("SoC", x, wave / 100.0),), y_scale=100.0),
        ),
        x_max_s=float(N),
    )


def test_prepare_works_out_the_ranges_and_the_summaries() -> None:
    spec = long_spec()
    prepared = prepare(spec)
    assert prepared.spec is spec
    for panel in spec.panels:
        assert prepared.ranges[id(panel)] == panel_y_range(panel)
    for panel in spec.panels:
        for series in panel.series:
            assert prepared.envelopes.is_summarised(series)


def test_a_widget_takes_the_prepared_plot_and_works_nothing_out(
    qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    spec = long_spec()
    prepared = prepare(spec)
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 500)
    widget.show()
    qtbot.waitExposed(widget)

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the widget worked something out that was prepared")

    monkeypatch.setattr(plot_widget, "panel_y_range", boom)
    monkeypatch.setattr(prepared.envelopes, "warm", boom)
    widget.set_spec(spec, prepared)
    assert widget.grab().width() > 0  # painted, from the prepared ranges and summaries


def test_a_prepared_plot_looks_like_one_the_widget_prepares_itself(qtbot) -> None:  # type: ignore[no-untyped-def]
    spec = long_spec()
    a, b = PlotWidget(), PlotWidget()
    for widget in (a, b):
        qtbot.addWidget(widget)
        widget.resize(900, 500)
        widget.show()
        qtbot.waitExposed(widget)
    a.set_spec(spec)
    b.set_spec(spec, prepare(spec))
    assert a.grab().toImage() == b.grab().toImage()


def test_a_plot_prepared_for_another_spec_is_not_used(qtbot) -> None:  # type: ignore[no-untyped-def]
    spec, other = long_spec(), long_spec()
    widget = PlotWidget()
    qtbot.addWidget(widget)
    widget.set_spec(spec, prepare(other))
    assert widget._y_range(spec.panels[0]) == panel_y_range(spec.panels[0])


def test_a_prepared_plot_is_held_by_identity() -> None:
    spec = long_spec()
    prepared = prepare(spec)
    assert isinstance(prepared, PreparedPlot)
    assert prepared.envelopes.is_summarised(spec.panels[0].series[0])
    assert not prepared.envelopes.is_summarised(long_spec().panels[0].series[0])


# ---- the views build their plots in the worker -----------------------------------------------


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


@pytest.fixture
def micro(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_150kg", tmp_path / "p")
    return tmp_path / "p"


def on_window_thread() -> bool:
    return QThread.currentThread() is QApplication.instance().thread()  # type: ignore[union-attr]


def test_the_power_plots_of_both_cases_are_built_in_the_worker(
    window: MainWindow, micro: Path, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    from budget_gui import timeline_view

    real = timeline_view.power_plot
    calls: list[tuple[str, bool]] = []

    def spy(result: Any, case: str, **kwargs: Any) -> PlotSpec:
        calls.append((case, on_window_thread()))
        return real(result, case, **kwargs)

    monkeypatch.setattr(timeline_view, "power_plot", spy)
    window.open_project(micro)
    view = window.timeline_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    assert {case for case, _ in calls} == {"bol", "eol"}
    assert not any(main for _case, main in calls)
    calls.clear()
    view.case_combo.setCurrentText("EOL")
    view.case_combo.setCurrentText("BOL")
    assert calls == []  # changing the case takes the plot that is ready
    assert view.plot.spec() is not None


def test_the_plot_of_every_link_is_built_in_the_worker(
    window: MainWindow, micro: Path, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    from budget_gui import link_view

    real = link_view.link_plot
    calls: list[bool] = []

    def spy(series: Any, duration_s: float) -> PlotSpec:
        calls.append(on_window_thread())
        return real(series, duration_s)

    monkeypatch.setattr(link_view, "link_plot", spy)
    window.open_project(micro)
    view = window.link_passes_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    assert calls and not any(calls)
    calls.clear()
    for index in range(view.link_combo.count()):
        view.link_combo.setCurrentIndex(index)
    assert calls == []
    assert view.plot.spec() is not None


def test_a_view_without_prepared_plots_builds_them_itself(
    window: MainWindow, micro: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    """A result set without a worker (as some tests and the exporters do) still shows its plot."""
    window.open_project(micro)
    view = window.timeline_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    result = view.result
    view._prepared = {}
    view._show()
    assert view.result is result and view.plot.spec() is not None
    assert threading.current_thread() is threading.main_thread()
