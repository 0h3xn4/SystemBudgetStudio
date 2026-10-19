"""Every screen and dialog opens with the example project in both themes and at other UI scales,
without an exception and without a message from Qt about the style sheet (D-169)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QMessageBox

from budget_gui import theme
from budget_gui.command_palette import CommandPalette
from budget_gui.grid_view import PastePreview
from budget_gui.help_view import GuideDialog
from budget_gui.legend import LegendDialog
from budget_gui.main_window import MainWindow
from budget_gui.theme import Mode
from budget_gui.workspace import SubTabs

pytestmark = pytest.mark.gui
EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps"
COMPLAINT = ("tylesheet", "Unknown property", "Could not parse", "unknown property")


@pytest.mark.parametrize(
    ("mode", "percent"),
    [(Mode.LIGHT, 100), (Mode.DARK, 100), (Mode.LIGHT, 125), (Mode.DARK, 90)],
    ids=["light", "dark", "light-125", "dark-90"],
)
def test_every_screen_and_dialog_opens(  # type: ignore[no-untyped-def]
    qtbot, mode: Mode, percent: int
) -> None:
    seen: list[str] = []

    def handler(kind: QtMsgType, _context: object, text: str) -> None:
        if kind != QtMsgType.QtDebugMsg:
            seen.append(text)

    previous = qInstallMessageHandler(handler)
    try:
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        theme.set_scale_percent(percent)
        theme.manager().set_mode(mode, app)
        window = MainWindow()
        qtbot.addWidget(window)
        window.resize(*theme.WINDOW_DEFAULT)
        window.show()
        assert window.welcome.isVisibleTo(window)  # the first screen
        assert not window.grab().isNull()
        window.open_project(EXAMPLE)
        window.run_all()
        qtbot.waitUntil(lambda: not window.run_controller.is_running(), timeout=120000)
        shots = 0
        for index in range(window.workspace.count()):
            window.workspace.setCurrentIndex(index)
            page = window.workspace.widget(index)
            if isinstance(page, SubTabs):
                for sub in range(page.count()):
                    page.setCurrentIndex(sub)
                    assert not window.grab().isNull()
                    shots += 1
            else:
                assert not window.grab().isNull()
                shots += 1
        for sub in range(window.editors.count()):  # the Model tab's grids and the scenario
            window.workspace.setCurrentIndex(0)
            window.editors.setCurrentIndex(sub)
            assert not window.grab().isNull()
        assert shots >= 7
        for dock in (window.inspector_dock, window.problems_dock, window.provenance_dock):
            dock.show()
            dock.raise_()
            assert not window.grab().isNull()
        for action in window.menuBar().actions():
            menu = action.menu()
            assert menu is not None and menu.actions()
        dialogs = [
            CommandPalette(window.palette_commands(), window),
            LegendDialog(window),
            GuideDialog(window.session.project, window),
            PastePreview([("Unit / mass_kg", "1.2", "1.4")], 1, window),
            QMessageBox(QMessageBox.Icon.Question, "Title", "Text", parent=window),
        ]
        for dialog in dialogs:
            qtbot.addWidget(dialog)
            dialog.show()
            assert not dialog.grab().isNull()
            dialog.close()
        wizard = window.open_guided_wizard(Path("."))
        qtbot.addWidget(wizard)
        assert not wizard.grab().isNull()
        wizard.close()
        window.editors.discard_all_changes()
        window.close()
    finally:
        qInstallMessageHandler(previous)
        theme.manager().set_scale(theme.DEFAULT_SCALE)
    assert [m for m in seen if any(c in m for c in COMPLAINT)] == []
