"""Keyboard only: Tab goes everywhere and never gets stuck (UX step 6, UX-41)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(tmp_path / "p")
    w.show()
    qtbot.waitExposed(w)
    return w


def area_of(window: MainWindow, widget: QWidget | None) -> str:
    """Which part of the window has the keyboard."""
    if widget is None:
        return "none"
    for name, part in (
        ("tree", window.tree),
        ("problems", window.problems_panel),
        ("inspector", window.inspector),
        ("top bar", window.top_bar),
        ("workspace", window.workspace),
    ):
        if part is widget or part.isAncestorOf(widget):
            return name
    return "other"


def test_tab_visits_every_part_of_the_window_and_comes_back(window: MainWindow) -> None:
    window.tree.setFocus()
    QApplication.processEvents()
    visited: list[str] = []
    first = QApplication.focusWidget()
    returned = False
    for step in range(120):
        QTest.keyClick(QApplication.focusWidget() or window, Qt.Key.Key_Tab)
        QApplication.processEvents()
        focus = QApplication.focusWidget()
        visited.append(area_of(window, focus))
        if step > 3 and focus is first:
            returned = True
            break
    assert {"tree", "top bar", "workspace", "problems"} <= set(visited), visited
    assert returned, "Tab never came back to where it started: it is stuck or goes round without"
