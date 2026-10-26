"""Open and edit with a single click (D-195): a setting for people who do not want to double-click.
Off by default (a double-click or Enter opens a node of the project tree; a double-click, F2 or a
key edits a cell); on, a click on a node opens it and a click on a selected cell edits it."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from budget_gui.layout_settings import LayoutSettings
from budget_gui.main_window import MainWindow
from budget_gui.project_tree import FILE_ROLE

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
SELECTED_CLICKED = QAbstractItemView.EditTrigger.SelectedClicked


def _window(qtbot, path: Path | None = None) -> MainWindow:  # type: ignore[no-untyped-def]
    window = MainWindow(LayoutSettings(path) if path else None)
    qtbot.addWidget(window, before_close_func=lambda w: w.editors.discard_all_changes())
    window.resize(1500, 900)
    window.show()
    window.open_project(EXAMPLES / "microsat_250kg_eps")
    return window


def _file_node(window: MainWindow):  # type: ignore[no-untyped-def]
    tree = window.tree
    for index in range(tree.topLevelItemCount()):
        stack = [tree.topLevelItem(index)]
        while stack:
            item = stack.pop()
            if item.data(0, FILE_ROLE) and item.childCount() == 0:  # a node with a file
                return item
            stack.extend(item.child(i) for i in range(item.childCount()))
    raise AssertionError("no file node in the tree")


def test_a_click_opens_nothing_by_default(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    assert not window.single_click_action.isChecked()
    opened: list[str] = []
    window.tree.file_requested.connect(opened.append)
    item = _file_node(window)
    window.tree.itemClicked.emit(item, 0)
    assert opened == []


def test_a_click_on_a_node_opens_it_when_the_setting_is_on(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    window.set_single_click(True)
    opened: list[str] = []
    window.tree.file_requested.connect(opened.append)
    window.tree.itemClicked.emit(_file_node(window), 0)
    assert len(opened) == 1


def test_a_click_on_a_selected_cell_edits_it_when_the_setting_is_on(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    views = [page.table.view for page in window.grid_pages()]
    assert all(not v.editTriggers() & SELECTED_CLICKED for v in views)
    window.set_single_click(True)
    assert all(v.editTriggers() & SELECTED_CLICKED for v in views)
    window.set_single_click(False)
    assert all(not v.editTriggers() & SELECTED_CLICKED for v in views)


def test_the_menu_and_the_settings_card_agree_and_the_choice_is_kept(  # type: ignore[no-untyped-def]
    qtbot, tmp_path: Path
) -> None:
    path = tmp_path / "layout.ini"
    window = _window(qtbot, path)
    card = window.show_settings()
    qtbot.addWidget(card)
    assert not card.single_click_box.isChecked()
    card.single_click_box.click()
    assert window.single_click_action.isChecked() and window.single_click
    assert "open_with=single" in path.read_text(encoding="utf-8")
    window.set_single_click(False)  # from the menu: the card shows what is in force next time
    assert "open_with=double" in path.read_text(encoding="utf-8")
    again = window.show_settings()
    qtbot.addWidget(again)
    assert not again.single_click_box.isChecked()

    window.single_click_action.trigger()
    other = _window(qtbot, path)  # a new window starts as the last one was left
    assert other.single_click and other.single_click_action.isChecked()
    assert all(p.table.view.editTriggers() & SELECTED_CLICKED for p in other.grid_pages())


def test_the_setting_is_in_the_palette_and_names_its_mode(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    names = [command.text for command in window.palette_commands()]
    assert any(n.startswith("View > ") and "single click" in n.lower() for n in names)


def test_a_real_mouse_click_on_a_node_opens_its_file_only_when_the_setting_is_on(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _window(qtbot)
    tree = window.tree
    item = _file_node(window)
    parent = item.parent()
    while parent is not None:  # the node is in view
        parent.setExpanded(True)
        parent = parent.parent()
    tree.scrollToItem(item)
    opened: list[str] = []
    tree.file_requested.connect(opened.append)
    point = tree.visualItemRect(item).center()
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert opened == []
    window.set_single_click(True)
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert len(opened) == 1
