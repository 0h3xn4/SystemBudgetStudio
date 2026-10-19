"""The accessibility pass (M6, D-181): names for what a screen reader reads, a focus ring on
everything the keyboard reaches, and no control the keyboard cannot reach."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from budget_gui import theme
from budget_gui.main_window import MainWindow
from budget_gui.theme import DARK, LIGHT, Mode

pytestmark = pytest.mark.gui
ROOT = Path(__file__).resolve().parents[2]


def _audit_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "ui_access_audit", ROOT / "scripts" / "ui_access_audit.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1600, 900)
    w.show()
    QApplication.processEvents()
    return w


@pytest.mark.parametrize("mode", [Mode.LIGHT, Mode.DARK], ids=["light", "dark"])
def test_every_control_of_the_window_and_its_dialogs_has_what_a_screen_reader_needs(
    window: MainWindow, mode: Mode
) -> None:
    theme.manager().set_mode(mode)
    try:
        audit = _audit_module()
        findings = audit.audit(window) + audit.audit_dialogs(window)
        assert findings == []
    finally:
        theme.manager().set_mode(Mode.LIGHT)


def test_the_style_sheet_draws_a_focus_ring_for_every_kind_of_control() -> None:
    for tokens in (LIGHT, DARK):
        sheet = theme.stylesheet(tokens)
        for selector in (
            "QPushButton:focus",
            "QToolButton:focus",
            "QLineEdit:focus",
            "QComboBox:focus",
            "QTableView:focus",
            "QPlainTextEdit:focus",
            "QCheckBox:focus",
            "QTabBar::tab:focus",
        ):
            assert selector in sheet, selector
        assert tokens.focus in sheet


def test_a_plot_that_has_the_keyboard_draws_the_focus_ring(  # type: ignore[no-untyped-def]
    window: MainWindow, qtbot, tmp_path: Path
) -> None:
    import shutil

    shutil.copytree(ROOT / "examples" / "microsat_250kg_eps", tmp_path / "p")
    window.open_project(tmp_path / "p")
    window.show_view(window.timeline_view)
    with qtbot.waitSignal(window.timeline_view.computed, timeout=120000):
        window.timeline_view.compute()
    plot = window.timeline_view.plot
    QApplication.processEvents()
    without = plot.grab().toImage()
    plot.setFocus()
    QApplication.processEvents()
    if not plot.hasFocus():
        pytest.skip("the offscreen window does not give the plot the keyboard")
    focused = plot.grab().toImage()
    corner = (1, plot.height() // 2)
    assert focused.pixelColor(*corner).name() == theme.tokens().focus.lower()
    assert without.pixelColor(*corner).name() != theme.tokens().focus.lower()
