"""The seven tabs of the main area (UX step 1, D-151)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QTabWidget

from budget_gui.main_window import MainWindow
from budget_gui.workspace import TABS

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    w.open_project(EXAMPLES / "microsat_250kg_eps")
    return w


def test_there_are_seven_tabs_in_the_order_of_the_standard(window: MainWindow) -> None:
    titles = [window.workspace.tabText(i) for i in range(window.workspace.count())]
    assert (
        titles
        == list(TABS)
        == [
            "Model",
            "Power",
            "Mass",
            "Thermal",
            "Link",
            "Compare",
            "Reports",
        ]
    )


def test_a_file_tab_does_not_push_a_budget_out_of_view(window: MainWindow) -> None:
    for rel in ("units/obc.yaml", "units/radio.yaml", "config/power_system.yaml"):
        window.open_file(rel)
    assert window.workspace.count() == 7  # editors live inside the Model tab
    assert window.workspace.currentWidget() is window.editors
    assert window.editors.count() == 3 + 1 + 3  # three grids, the scenario and three files


def test_power_and_link_have_a_page_for_the_time_domain_results(window: MainWindow) -> None:
    power = window.workspace.widget(1)
    link = window.workspace.widget(4)
    assert isinstance(power, QTabWidget) and isinstance(link, QTabWidget)
    assert [power.tabText(i) for i in range(power.count())] == ["Budget", "Timeline"]
    assert [link.tabText(i) for i in range(link.count())] == ["Budget", "Passes"]


def test_show_view_finds_a_view_wherever_it_sits(window: MainWindow) -> None:
    for view in (
        window.timeline_view,
        window.link_passes_view,
        window.scenario_view,
        window.mass_view,
        window.compare_view,
        window.reports_view,
        window.power_view,
    ):
        assert window.show_view(view)
        assert window.workspace.is_showing(view) and view.isVisible()
    assert not window.workspace.show_view(window.tree)  # not part of the workspace


def test_opening_a_unit_table_brings_the_model_tab_forward(window: MainWindow) -> None:
    window.show_view(window.mass_view)
    page = window.show_unit("radio")
    assert page is not None
    assert window.workspace.currentWidget() is window.editors
    assert window.editors.currentWidget() is page


def test_ctrl_number_goes_to_the_tab(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtCore import Qt

    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
    assert window.workspace.tabText(window.workspace.currentIndex()) == "Mass"
    qtbot.keyClick(window, Qt.Key.Key_7, Qt.KeyboardModifier.ControlModifier)
    assert window.workspace.tabText(window.workspace.currentIndex()) == "Reports"
    qtbot.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
    assert window.workspace.tabText(window.workspace.currentIndex()) == "Model"


def test_save_only_acts_on_the_model_tab(window: MainWindow) -> None:
    window.open_file("units/obc.yaml")
    window.show_view(window.mass_view)
    assert window.save_current() is False  # the text tab is not in front: nothing is written


def test_the_reports_tab_offers_the_exports(window: MainWindow, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a, **_k: "")  # Cancel
    view = window.reports_view
    assert [
        b.text() for b in (view.reports_button, view.timeline_button, view.scenario_button)
    ] == [
        "Export budget reports…",
        "Export power timeline…",
        "Export scenario results…",
    ]
    with qtbot.waitSignal(view.reports_requested, timeout=1000):
        view.reports_button.click()
