"""GUI test support: a window with a running job refuses to close (it closes when the job is done),
so every test lets the jobs of the windows it made finish before the windows are torn down."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from budget_gui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _finish_jobs(request: pytest.FixtureRequest):  # type: ignore[no-untyped-def]
    request.getfixturevalue("qtbot")  # set up first, so this runs before qtbot closes the windows
    yield
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.wait_for_jobs()
