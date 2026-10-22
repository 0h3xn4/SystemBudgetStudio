"""The focused view (D-191): the window opens with the counts of the problems as one line, no
Inspector and no Provenance panel and only the main columns of the grids; the full view is one
toggle away and the choice is kept."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from budget_gui import main_window
from budget_gui.layout_settings import LayoutSettings
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(autouse=True)
def _focused_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_window, "DEFAULT_VIEW", "focused")


def _window(qtbot, layout: LayoutSettings | None = None) -> MainWindow:  # type: ignore[no-untyped-def]
    window = MainWindow(layout)
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.resize(1600, 900)
    window.show()
    window.open_project(EXAMPLES / "microsat_150kg")
    QApplication.processEvents()
    return window


def _view_entry(window: MainWindow):  # type: ignore[no-untyped-def]
    return window.view_action


def test_a_new_window_starts_focused(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    assert window.view_action.isChecked() and window._focused
    assert window.inspector_dock.isHidden() and window.provenance_dock.isHidden()
    assert not window.problems_panel.is_expanded()
    assert (
        window.problems_panel.filter_box.isHidden() and window.problems_panel._stack_host.isHidden()
    )
    assert "not checked" in window.problems_panel.summary.text()  # the counts stay
    assert "problems" in window.problems_panel.toggle_button.text()
    assert not window.project_dock.isHidden()  # the project panel is navigation, it stays


def test_the_collapsed_problems_dock_is_one_line_high(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    assert window.problems_dock.height() < 140


def test_the_optional_columns_are_hidden_and_the_button_brings_them_back(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    units = window.units_page
    optional = [i for i, c in enumerate(units.model.columns) if c.optional]
    assert optional and units.columns_button.isVisible() is not None
    assert all(units.table.view.isColumnHidden(i) for i in optional)
    assert not units.columns_button.isChecked()
    units.columns_button.click()
    assert not any(units.table.view.isColumnHidden(i) for i in optional)
    units.columns_button.click()
    assert all(units.table.view.isColumnHidden(i) for i in optional)


def test_the_view_toggle_shows_everything_and_back(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    window.view_action.trigger()  # Focused view off
    QApplication.processEvents()
    assert not window._focused
    assert not window.inspector_dock.isHidden() and not window.provenance_dock.isHidden()
    assert window.problems_panel.is_expanded()
    assert window.problems_dock.height() > 140
    optional = [i for i, c in enumerate(window.units_page.model.columns) if c.optional]
    assert not any(window.units_page.table.view.isColumnHidden(i) for i in optional)
    window.view_action.trigger()
    QApplication.processEvents()
    assert window._focused and window.inspector_dock.isHidden()
    assert not window.problems_panel.is_expanded()


def test_a_jump_to_a_problem_opens_the_list(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    assert not window.problems_panel.is_expanded()
    window.show_not_checked()  # the link of the status bar
    assert window.problems_panel.is_expanded() and window.problems_panel.view.isVisible()
    window.problems_panel.set_expanded(False)
    window.next_problem()  # F8
    assert window.problems_panel.is_expanded()


def test_the_choice_is_kept_in_the_layout_file(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    layout_file = tmp_path / "config" / "layout.ini"
    window = _window(qtbot, LayoutSettings(layout_file))
    window.view_action.trigger()  # full
    window.save_layout()
    assert "view=full" in layout_file.read_text()

    again = _window(qtbot, LayoutSettings(layout_file))
    assert not again._focused and not again.view_action.isChecked()
    assert again.problems_panel.is_expanded() and not again.inspector_dock.isHidden()


def test_the_view_toggle_has_a_shortcut_and_is_in_the_palette(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    assert window.view_action.shortcut().toString() == "Ctrl+Shift+F"
    assert "View > Focused view" in [command.text for command in window.palette_commands()]


def test_reset_layout_goes_back_to_the_focused_view(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    window.view_action.trigger()
    window.reset_layout()
    QApplication.processEvents()
    assert window._focused and window.inspector_dock.isHidden()
    assert not window.problems_panel.is_expanded()


def test_the_welcome_page_gives_back_the_focused_docks(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1600, 900)
    window.show()
    window.open_project(EXAMPLES / "microsat_150kg")
    QApplication.processEvents()
    assert window.inspector_dock.isHidden()
