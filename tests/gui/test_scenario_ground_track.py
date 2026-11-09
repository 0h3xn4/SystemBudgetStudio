# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The ground track in the scenario window (2.2.0): a map tab and a line in the Statistics tab."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QTabWidget

from budget_core.environment.ground_track import GroundTrack
from budget_gui.ground_track_widget import GroundTrackWidget, MapSite
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    return w


def _compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.scenario_view.compute()
    qtbot.waitUntil(lambda: not window.scenario_view.is_busy(), timeout=120000)
    assert window.scenario_view.last_run is not None


def test_there_is_a_ground_track_tab(window: MainWindow) -> None:
    tabs = window.scenario_view.findChildren(QTabWidget)[0]
    assert "Ground track" in [tabs.tabText(i) for i in range(tabs.count())]


def test_the_map_has_the_track_and_the_sites_after_compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    assert not window.scenario_view.ground_track_widget.has_track
    _compute(window, qtbot)
    view = window.scenario_view
    assert view.ground_track_widget.has_track
    assert view.ground_track_widget.accessibleName() == "Ground track map"
    text = view.ground_track_label.text()
    assert text.startswith("Ground track: latitude") and "ascending equator crossing" in text


def test_a_new_run_with_nothing_clears_the_map(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    _compute(window, qtbot)
    window.scenario_view.ground_track_widget.set_track(None)
    assert not window.scenario_view.ground_track_widget.has_track


def test_the_line_is_cut_at_the_date_line(qtbot) -> None:  # type: ignore[no-untyped-def]
    widget = GroundTrackWidget()
    qtbot.addWidget(widget)
    lat = np.array([0.0, 1.0, 2.0, 3.0])
    lon = np.array([170.0, 179.0, -179.0, -170.0])
    widget.set_track(GroundTrack(lat, lon, np.zeros(4)))
    assert widget.line_count == 2


def test_it_paints_the_track_in_both_themes(qtbot) -> None:  # type: ignore[no-untyped-def]
    from budget_gui import theme

    widget = GroundTrackWidget()
    qtbot.addWidget(widget)
    widget.resize(720, 420)
    t = np.linspace(0.0, 2.0 * np.pi, 200)
    widget.set_track(
        GroundTrack(60.0 * np.sin(t), np.degrees(t) - 180.0, np.zeros_like(t)),
        [MapSite("gs_a", "ground_station", 10.0, 20.0), MapSite("tg_b", "target", -30.0, 100.0)],
    )
    for name in ("light", "dark"):
        theme.manager().set_mode(name)
        image = QImage(widget.size(), QImage.Format.Format_ARGB32)
        widget.render(image)
        colours = {
            image.pixel(x, y)
            for x in range(0, image.width(), 7)
            for y in range(0, image.height(), 7)
        }
        assert len(colours) > 5  # a grid, a line and markers, not an empty canvas
    theme.manager().set_mode("system")
