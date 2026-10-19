import pytest
from PySide6.QtGui import QFontDatabase

from budget_core import APP_NAME
from budget_gui.main_window import MainWindow
from budget_gui.theme import load_fonts

pytestmark = pytest.mark.gui


def test_window_title_and_status(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == APP_NAME
    assert "Offline" in window.statusBar().currentMessage()


def test_the_bundled_fonts_load(qtbot) -> None:  # type: ignore[no-untyped-def]
    families = load_fonts()
    assert "Inter" in families
    assert "JetBrains Mono" in families
    assert "Inter" in QFontDatabase.families()
    assert "JetBrains Mono" in QFontDatabase.families()
