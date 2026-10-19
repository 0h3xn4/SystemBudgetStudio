"""The first screen and the command palette (UX step 6, D-166)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent, QKeySequence
from PySide6.QtTest import QTest

from budget_gui.command_palette import Command, CommandPalette, rank
from budget_gui.main_window import MainWindow
from budget_gui.welcome import WelcomePage

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


# ---- the first screen -----------------------------------------------------------------------
def test_the_welcome_page_shows_until_a_project_is_open(window: MainWindow, project: Path) -> None:
    window.show()
    assert window.welcome.isVisible() and not window.workspace.isVisible()
    assert not window.top_bar.isVisible()
    window.open_project(project)
    assert not window.welcome.isVisible() and window.workspace.isVisible()
    assert window.top_bar.isVisible()


def test_the_welcome_buttons_open_and_start_a_project(qtbot) -> None:  # type: ignore[no-untyped-def]
    page = WelcomePage()  # on its own: in the window the buttons open dialogs
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.open_requested, timeout=500):
        page.open_button.click()
    with qtbot.waitSignal(page.new_requested, timeout=500):
        page.new_button.click()


def test_there_is_no_list_of_recent_projects(window: MainWindow) -> None:
    labels = [b.text() for b in window.welcome.findChildren(type(window.welcome.open_button))]
    assert labels == ["Open a project folder…", "New project (guided)…"]


def test_a_dropped_folder_is_a_project_and_a_file_is_not(
    window: MainWindow, project: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    def mime(*paths: Path) -> QMimeData:
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        return data

    assert window._dropped_folder(mime(project)) == project
    assert window._dropped_folder(mime(project / "project.yaml")) is None
    assert window._dropped_folder(mime(project, project)) is None
    assert window._dropped_folder(QMimeData()) is None
    opened: list[Path] = []
    monkeypatch.setattr(window, "open_project", lambda path, **_k: opened.append(path) or True)
    data = mime(project)
    event = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(event)
    assert opened == [project]


# ---- the palette ----------------------------------------------------------------------------
def test_rank_wants_every_word_in_any_order_and_puts_the_nearest_to_the_start_first() -> None:
    commands = [
        Command("File > Open project", lambda: None, "Ctrl+O"),
        Command("Open unit Radio (radio)", lambda: None, "unit"),
        Command("Run > Run all", lambda: None, "Ctrl+R"),
        Command("Open file units/radio.yaml", lambda: None, "file"),
    ]
    assert [c.text for c in rank("run", commands)] == ["Run > Run all"]
    assert [c.text for c in rank("radio open", commands)] == [
        "Open unit Radio (radio)",
        "Open file units/radio.yaml",
    ]
    assert [c.text for c in rank("CTRL+O", commands)] == ["File > Open project"]  # the hint too
    assert rank("", commands) == commands and rank("zzz", commands) == []


def test_the_palette_filters_moves_and_runs_with_the_keyboard(qtbot) -> None:  # type: ignore[no-untyped-def]
    ran: list[str] = []
    commands = [
        Command("Alpha", lambda: ran.append("alpha")),
        Command("Beta one", lambda: ran.append("beta1")),
        Command("Beta two", lambda: ran.append("beta2")),
    ]
    palette = CommandPalette(commands)
    qtbot.addWidget(palette)
    palette.show()
    assert palette.shown() == ["Alpha", "Beta one", "Beta two"]
    QTest.keyClicks(palette.field, "beta")
    assert palette.shown() == ["Beta one", "Beta two"]
    QTest.keyClick(palette, Qt.Key.Key_Down)
    QTest.keyClick(palette, Qt.Key.Key_Return)
    assert ran == ["beta2"] and not palette.isVisible()


def test_the_palette_says_when_nothing_matches(qtbot) -> None:  # type: ignore[no-untyped-def]
    palette = CommandPalette([Command("Alpha", lambda: None)])
    qtbot.addWidget(palette)
    palette.show()
    QTest.keyClicks(palette.field, "zzz")
    assert palette.shown() == [] and palette.empty.isVisible()


def test_ctrl_k_is_in_the_view_menu(window: MainWindow) -> None:
    actions = {a.text().replace("&", ""): a for a in window.view_menu.actions()}
    assert actions["Find a command…"].shortcut() == QKeySequence("Ctrl+K")


def test_the_palette_offers_commands_units_files_scenarios_and_problems(
    window: MainWindow, project: Path
) -> None:
    window.open_project(project)
    texts = [c.text for c in window.palette_commands()]
    assert "File > Open project" in texts and "Run > Run all" in texts
    assert "View > Go to Reports" in texts and "View > Theme > Dark" in texts
    assert any(t.startswith("Open unit S-band transceiver") for t in texts)
    assert "Select scenario one_day" in texts
    assert "Open file config/power_system.yaml" in texts
    assert any(t.startswith("Go to problem:") for t in texts)
    kinds = {c.hint for c in window.palette_commands()}
    assert {"unit", "scenario", "file", "problem", "Ctrl+R"} <= kinds


def test_a_palette_command_does_what_the_menu_does(window: MainWindow, project: Path) -> None:
    window.open_project(project)
    commands = {c.text: c for c in window.palette_commands()}
    commands["View > Go to Reports"].run()
    assert window.workspace.top_title() == "Reports"
    commands["Open file config/power_system.yaml"].run()
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "config/power_system.yaml"


# ---- the Inspector follows the cell ---------------------------------------------------------
def column_of(page, key: str) -> int:  # type: ignore[no-untyped-def]
    return next(i for i, c in enumerate(page.table.model.columns) if c.key == key)


def test_the_inspector_shows_the_cell_that_has_the_cursor(
    window: MainWindow, project: Path
) -> None:
    window.open_project(project)
    window.show_unit("radio")
    page = window.modes_page
    row = page.table.model.rows_of("radio")[0]
    assert page.table.select_cell(row, column_of(page, "avg_power_w"))
    inspector = window.inspector
    assert "S-band transceiver" in inspector.title.text() or "radio" in inspector.title.text()
    assert "avg_power_w" in inspector.kind_label.text()
    assert "units/radio.yaml" in inspector.file_label.text()
    assert "modes" in inspector.field_label.text() and "avg_power_w" in inspector.field_label.text()
    assert "Value:" in inspector.counts_label.text()
    assert (
        inspector.open_button.text() == "Open the file" and not inspector.modes_button.isVisible()
    )


def test_a_refused_value_is_explained_in_the_inspector(window: MainWindow, project: Path) -> None:
    window.open_project(project)
    window.show_unit("radio")
    page = window.modes_page
    row = page.table.model.rows_of("radio")[-1]  # the downlink mode: 28 W on average
    column = column_of(page, "peak_power_w")
    rel, path = page.table.model.cell(row, column)  # type: ignore[misc]
    window.document.set_value(rel, path, 10.0, "Edit")  # below the average: refused
    page.table.select_cell(row, 0)
    page.table.select_cell(row, column)
    inspector = window.inspector
    assert inspector.problems.count() == 1 and "peak" in inspector.problems.item(0).text().lower()
    assert "Limit broken" in inspector.counts_label.text()


def test_the_tree_takes_the_inspector_back(window: MainWindow, project: Path) -> None:
    window.open_project(project)
    window.show_unit("radio")
    page = window.modes_page
    page.table.select_cell(page.table.model.rows_of("radio")[0], column_of(page, "avg_power_w"))
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    assert window.inspector.open_button.text() == "Open"
    assert window.inspector._cell_rel == ""
