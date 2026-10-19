"""The shell: the navigation rail, the panels, the first screen, narrow windows, the settings card
and the palette overlay (D-173)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QStyle, QToolButton

from budget_gui import theme
from budget_gui.command_palette import Command, display_parts
from budget_gui.layout_settings import LayoutSettings
from budget_gui.main_window import LAYOUT_VERSION, MainWindow
from budget_gui.rail import DESTINATIONS
from budget_gui.settings_popover import SettingsPopover
from budget_gui.theme import Mode
from budget_gui.workspace import TABS

pytestmark = pytest.mark.gui
EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1600, 900)
    w.show()
    w.open_project(EXAMPLE)
    QApplication.processEvents()
    return w


def settle(window: MainWindow, width: int, height: int = 800) -> None:
    window.resize(width, height)
    QApplication.processEvents()


# ---- the rail ----------------------------------------------------------------------------------
def test_the_rail_has_the_seven_areas_in_the_order_of_the_workspace(window: MainWindow) -> None:
    assert tuple(d.title for d in DESTINATIONS) == TABS
    assert [b.title for b in window.rail.buttons] == list(TABS)
    for index, button in enumerate(window.rail.buttons):
        assert f"Ctrl+{index + 1}" in button.toolTip()  # keyboard first: the tooltip names the key
        assert button.accessibleName() == TABS[index]


def test_the_rail_chooses_the_area_and_follows_it(window: MainWindow) -> None:
    window.rail.buttons[4].click()
    assert window.workspace.currentIndex() == 4 and window.rail.current() == 4
    window.workspace.setCurrentIndex(2)  # changed from somewhere else (Ctrl+3, a jump)
    assert window.rail.current() == 2 and window.rail.buttons[2].isChecked()
    assert window.workspace.tabBar().isHidden()  # the rail is the navigation


def test_a_page_of_an_area_is_chosen_with_a_segmented_control(window: MainWindow) -> None:
    for pages in (window.power_pages, window.link_pages):
        assert pages.tabBar().property("role") == "segmented"
    assert window.mass_view.tabs.tabBar().property("role") == "segmented"


def test_the_workspace_does_not_take_the_keyboard(window: MainWindow) -> None:
    assert window.workspace.focusPolicy() == Qt.FocusPolicy.NoFocus  # its tab bar is hidden


def test_the_rail_folds_to_icons_and_keeps_the_names(window: MainWindow) -> None:
    wide = window.rail.width()
    window.rail.fold_button.click()
    assert window.rail.folded and window.rail.width() < wide
    assert window.rail.width() == theme.px(theme.RAIL_COLLAPSED)
    for button in window.rail.buttons:
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.title in button.toolTip() and button.accessibleName() == button.title
    window.rail.fold_button.click()
    assert not window.rail.folded and window.rail.width() == wide


def test_the_rail_fold_is_kept_between_two_windows(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "layout.ini"
    first = MainWindow(LayoutSettings(path))
    qtbot.addWidget(first)
    first.show()
    first.rail.set_folded(True)
    first.close()
    second = MainWindow(LayoutSettings(path))
    qtbot.addWidget(second)
    second.show()
    assert second.rail.folded


def test_the_find_help_and_settings_buttons_are_there_and_named(window: MainWindow) -> None:
    for button in (window.rail.find_button, window.rail.settings_button, window.rail.help_button):
        assert isinstance(button, QToolButton) and button.toolTip() and button.accessibleName()
    assert "Ctrl+K" in window.rail.find_button.toolTip()
    assert "F1" in window.rail.help_button.toolTip()


# ---- the panels --------------------------------------------------------------------------------
def test_the_project_panel_follows_its_rail_button_and_ctrl_b(window: MainWindow) -> None:
    assert window.project_dock.isVisible() and window.rail.project_button.isChecked()
    window.rail.project_button.click()
    assert window.project_dock.isHidden() and not window.rail.project_button.isChecked()
    window.project_dock.show()  # shown from the View menu
    assert window.rail.project_button.isChecked()
    assert window.project_dock.toggleViewAction().shortcut().toString() == "Ctrl+B"


def test_the_problems_panel_shows_every_column_along_the_bottom(window: MainWindow) -> None:
    panel = window.problems_panel
    assert panel.column_widths().count(0) == 0  # nothing hidden: there is room
    assert window.problems_dock.geometry().bottom() > window.project_dock.geometry().bottom()
    assert (
        window.problems_dock.width() > window.project_dock.width() + window.inspector_dock.width()
    )


def test_the_first_screen_has_no_panels_and_the_areas_wait(qtbot) -> None:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1600, 900)
    w.show()
    for dock in (w.project_dock, w.inspector_dock, w.problems_dock, w.provenance_dock):
        assert dock.isHidden()
    assert not any(b.isEnabled() for b in w.rail.buttons)
    assert w.rail.find_button.isEnabled() and w.rail.settings_button.isEnabled()
    w.open_project(EXAMPLE)
    assert w.project_dock.isVisible() and w.problems_dock.isVisible()
    assert all(b.isEnabled() for b in w.rail.buttons)


def test_the_status_bar_says_it_is_offline(window: MainWindow) -> None:
    assert window.status_bar.offline.text().strip() == "Offline"
    assert "no network" in window.status_bar.offline.toolTip()


# ---- narrow windows ----------------------------------------------------------------------------
def test_a_narrower_window_gives_up_the_inspector_then_the_labels_then_the_project(
    window: MainWindow,
) -> None:
    window.inspector_dock.show()
    settle(window, 1600)
    assert window.inspector_dock.isVisible() and not window.rail.folded
    settle(window, 1400)  # below 1520 px: no inspector
    assert window.inspector_dock.isHidden() and window.provenance_dock.isHidden()
    assert window.project_dock.isVisible() and not window.rail.folded
    settle(window, 1200)  # below 1280 px: icons only
    assert window.rail.folded and window.project_dock.isVisible()
    settle(window, 1000)  # below 1100 px: no project panel
    assert window.project_dock.isHidden() and window.rail.folded
    settle(window, 1600)  # room again: all back
    assert window.inspector_dock.isVisible() and window.project_dock.isVisible()
    assert not window.rail.folded


def test_a_panel_the_user_closed_stays_closed_when_the_window_grows(window: MainWindow) -> None:
    window.provenance_dock.hide()
    settle(window, 1300)
    settle(window, 1700)
    assert window.provenance_dock.isHidden()


def test_a_rail_the_user_folded_stays_folded_when_the_window_grows(window: MainWindow) -> None:
    window.rail.set_folded(True)
    settle(window, 1100)
    settle(window, 1700)
    assert window.rail.folded


def test_the_saved_layout_holds_what_the_user_chose_not_what_the_size_did(
    window: MainWindow,
) -> None:
    settle(window, 1300)
    assert window.inspector_dock.isHidden()  # hidden by the size
    with window._docks_as_the_user_left_them():
        assert not window.inspector_dock.isHidden()  # what a saved layout is made from
    assert window.inspector_dock.isHidden()


def test_a_layout_of_another_version_is_ignored(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    other = QMainWindow()
    qtbot.addWidget(other)
    settings = LayoutSettings(tmp_path / "layout.ini")
    settings.set_bytes("dock/state", QByteArray(other.saveState(LAYOUT_VERSION + 1)))
    settings.sync()
    w = MainWindow(LayoutSettings(tmp_path / "layout.ini"))
    qtbot.addWidget(w)
    assert w.dockWidgetArea(w.problems_dock) is Qt.DockWidgetArea.BottomDockWidgetArea


# ---- the settings card -------------------------------------------------------------------------
def test_the_settings_card_changes_theme_size_and_motion_and_keeps_them(  # type: ignore[no-untyped-def]
    qtbot, tmp_path: Path
) -> None:
    path = tmp_path / "layout.ini"
    w = MainWindow(LayoutSettings(path))
    qtbot.addWidget(w)
    w.show()
    card = w.show_settings()
    qtbot.addWidget(card)
    assert isinstance(card, SettingsPopover) and card.isVisible()
    card.theme_control.button("dark").click()
    assert theme.manager().mode is Mode.DARK and w.theme_actions[Mode.DARK].isChecked()
    card.scale_control.button("110").click()
    assert theme.scale_percent() == 110 and w.scale_actions[110].isChecked()
    card.motion_box.click()
    assert theme.manager().reduce_motion_setting and w.motion_action.isChecked()
    text = path.read_text(encoding="utf-8")
    assert "mode=dark" in text and "scale=110" in text and "motion=reduced" in text
    # the card shows what is in force, also when the menu changed it
    w.set_theme(Mode.LIGHT)
    again = w.show_settings()
    qtbot.addWidget(again)
    assert again.theme_control.current() == "light" and again.scale_control.current() == "110"
    theme.manager().set_scale(100)


# ---- the palette overlay and the boxes ---------------------------------------------------------
def test_the_palette_shows_the_menu_the_command_and_its_key_apart() -> None:
    assert display_parts(Command("File > Save", lambda: None, "Ctrl+S")) == (
        "File",
        "Save",
        "Ctrl+S",
    )
    assert display_parts(Command("View > Theme > Dark", lambda: None, "menu")) == (
        "View",
        "Theme > Dark",
        "",
    )
    assert display_parts(Command("Open unit Radio (radio)", lambda: None, "unit")) == (
        "Unit",
        "Radio (radio)",
        "",
    )
    assert display_parts(Command("Open file units/a.yaml", lambda: None, "file"))[0] == "File"
    assert display_parts(Command("Plain", lambda: None)) == ("", "Plain", "")


def test_the_boxes_qt_makes_use_the_icons_of_the_window(qtbot) -> None:  # type: ignore[no-untyped-def]
    style = QApplication.style()
    assert style is not None
    tokens = theme.tokens()
    for kind, level in (
        (QStyle.StandardPixmap.SP_MessageBoxQuestion, tokens.standby),
        (QStyle.StandardPixmap.SP_MessageBoxInformation, tokens.standby),
        (QStyle.StandardPixmap.SP_MessageBoxWarning, tokens.caution),
        (QStyle.StandardPixmap.SP_MessageBoxCritical, tokens.critical),
    ):
        image = style.standardIcon(kind).pixmap(48, 48).toImage()
        opaque = {
            image.pixelColor(x, y).name()
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).alpha() == 255
        }
        assert opaque == {QColor(level.fg).name()}, kind
