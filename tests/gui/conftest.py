"""GUI test support: a window with a running job refuses to close (it closes when the job is done),
so every test lets the jobs of the windows it made finish before the windows are torn down."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from budget_gui import session as session_module
from budget_gui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _synchronous_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most window tests check the logic, so a reload they trigger is finished when it returns.
    `test_background_load.py` replaces this fixture and tests the threaded path itself."""
    monkeypatch.setattr(session_module, "BACKGROUND_LOADING", False)


@pytest.fixture(autouse=True)
def _no_layout_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test never reads or writes the user's layout file (D-150)."""
    monkeypatch.setenv("BUDGET_NO_LAYOUT", "1")


@pytest.fixture(autouse=True)
def _light_theme_again():  # type: ignore[no-untyped-def]
    """The theme is one object for the whole process: a test that changed it puts it back."""
    yield
    from budget_gui import theme

    if QApplication.instance() is not None and theme.manager().mode is not theme.Mode.LIGHT:
        theme.manager().set_mode(theme.Mode.LIGHT)
    if QApplication.instance() is not None and theme.scale_percent() != theme.DEFAULT_SCALE:
        theme.manager().set_scale(theme.DEFAULT_SCALE)


@pytest.fixture(autouse=True)
def _finish_jobs(request: pytest.FixtureRequest):  # type: ignore[no-untyped-def]
    request.getfixturevalue("qtbot")  # set up first, so this runs before qtbot closes the windows
    yield
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.wait_for_jobs()
