# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The landing page, the start with a folder, Close project and closing while a job runs (D-269)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_gui import main_window as main_window_module
from budget_gui.layout_settings import LayoutSettings
from budget_gui.main_window import MainWindow
from budget_gui.recent_projects import FILE_NAME, LIMIT, RecentProjects
from budget_gui.welcome import EXAMPLE_TITLES

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


def make_window(qtbot, layout: LayoutSettings | None = None) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow(layout)
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    return make_window(qtbot)


# ---- the landing page --------------------------------------------------------------------------
def test_the_landing_page_offers_every_way_to_start(window: MainWindow) -> None:
    page = window.welcome
    labels = [b.text() for b in (page.open_button, page.new_button, page.example_button)]
    labels += [page.import_button.text(), page.guide_button.text()]
    assert labels == [
        "Open a project folder…",
        "New project (guided)…",
        "Open an example…",
        "Import IDM-CIC model…",
        "User guide",
    ]
    assert page.open_button.property("kind") == "primary"  # one primary action per view
    assert [a.data() for a in page.example_menu.actions()] == list(EXAMPLE_TITLES)
    assert page.launch_card.isHidden() and page.recent_card.isHidden()


def test_a_folder_given_at_start_is_offered_not_opened(
    window: MainWindow, project: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.show()
    window.offer_launch_folder(project)
    assert window.session.path is None  # nothing opened by itself
    assert window.welcome.isVisible() and window.welcome.launch_card.isVisible()
    assert project.name in window.welcome.launch_label.text()
    window.welcome.launch_button.click()
    qtbot.waitUntil(lambda: window.session.project is not None, timeout=20000)
    assert window.session.path == project and not window.welcome.isVisible()


def test_the_program_no_longer_opens_its_argument(
    project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    from budget_gui import app

    made: list[MainWindow] = []

    class Spy(MainWindow):
        def __init__(self) -> None:
            super().__init__()
            made.append(self)

    monkeypatch.setattr(app, "MainWindow", Spy)
    monkeypatch.setattr(app.sys, "argv", ["system-budget-studio", str(project)])
    monkeypatch.setattr(type(app.create_app(["x"])), "exec", lambda _self: 0)
    assert app.main() == 0
    window = made[0]
    qtbot.addWidget(window)
    assert window.session.path is None
    assert window.welcome.launch_folder == project


def test_an_example_is_copied_into_the_chosen_folder_and_opened(
    window: MainWindow, tmp_path: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    assert window.open_example("microsat_250kg_eps", parent_folder=tmp_path)
    qtbot.waitUntil(lambda: window.session.project is not None, timeout=20000)
    assert window.session.path == tmp_path / "microsat_250kg_eps"
    assert (tmp_path / "microsat_250kg_eps" / "project.yaml").is_file()


def test_an_existing_example_copy_is_not_overwritten(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "microsat_150kg"
    target.mkdir()
    (target / "mine.txt").write_text("my notes", encoding="utf-8")
    asked: list[str] = []
    monkeypatch.setattr(
        main_window_module, "ask", lambda _p, title, *_a, **_k: asked.append(title) or False
    )
    assert not window.open_example("microsat_150kg", parent_folder=tmp_path)
    assert asked and (target / "mine.txt").read_text(encoding="utf-8") == "my notes"
    assert not (target / "project.yaml").exists()


# ---- Close project -----------------------------------------------------------------------------
def test_close_project_goes_back_to_the_landing_page(window: MainWindow, project: Path) -> None:
    window.show()
    assert not window.close_project_action.isEnabled()
    assert window.close_project_action.shortcut().toString() == "Ctrl+W"  # on every system
    window.open_project(project)
    assert window.close_project_action.isEnabled() and not window.welcome.isVisible()
    assert window.close_project()
    assert window.session.path is None and window.session.project is None
    assert window.welcome.isVisible() and not window.workspace.isVisible()
    assert not window.close_project_action.isEnabled()
    assert window.windowTitle() == "System Budget Studio"


def test_close_project_keeps_unsaved_edits_when_asked(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_project(project)
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    editor.textCursor().insertText("# edit\n")
    monkeypatch.setattr(window.editors, "confirm_discard", lambda *_a: False)
    assert not window.close_project()
    assert window.session.path == project and editor.document().isModified()


def test_close_project_is_in_the_file_menu_and_the_palette(
    window: MainWindow, project: Path
) -> None:
    window.open_project(project)
    names = [c.text for c in window.palette_commands()]
    assert "File > Close project" in names
    assert any(n.startswith("File > Open an example > ") for n in names)


# ---- recent projects (off by default) ----------------------------------------------------------
def test_recent_projects_are_off_by_default_and_nothing_is_written(
    qtbot, project: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    config = tmp_path / "config"
    window = make_window(qtbot, LayoutSettings(config / "layout.ini"))
    window.open_project(project)
    window.close_project()
    assert not (config / FILE_NAME).exists()
    assert window.welcome.recent_card.isHidden()


def test_recent_projects_when_switched_on(qtbot, project: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    config = tmp_path / "config"
    window = make_window(qtbot, LayoutSettings(config / "layout.ini"))
    window.show()
    window.set_remember_recent(True)
    window.open_project(project)
    assert (config / FILE_NAME).read_text(encoding="utf-8").strip() == str(project.resolve())
    window.close_project()
    assert window.welcome.recent_card.isVisible()
    assert [b.toolTip() for b in window.welcome.recent_buttons] == [str(project.resolve())]
    window.clear_recent_projects()
    assert not (config / FILE_NAME).exists() and window.welcome.recent_card.isHidden()
    window.open_project(project)
    window.set_remember_recent(False)  # off deletes the file at once
    assert not (config / FILE_NAME).exists()
    again = make_window(qtbot, LayoutSettings(config / "layout.ini"))
    assert not again.recent.enabled  # the choice is kept


def test_the_recent_list_needs_the_layout_file(window: MainWindow, project: Path) -> None:
    assert not window.recent.available  # BUDGET_NO_LAYOUT=1 in the tests: nothing can be kept
    window.set_remember_recent(True)
    window.open_project(project)
    assert window.recent.folders() == []


def test_the_recent_list_keeps_existing_folders_newest_first(tmp_path: Path) -> None:
    recent = RecentProjects(tmp_path / FILE_NAME, enabled=True)
    folders = [tmp_path / f"p{i}" for i in range(LIMIT + 2)]
    for folder in folders:
        folder.mkdir()
        recent.add(folder)
    recent.add(folders[0])
    shutil.rmtree(folders[-1])
    shown = recent.folders()
    assert shown[0] == folders[0].resolve() and folders[-1].resolve() not in shown
    assert len(shown) <= LIMIT


# ---- closing the window while a computation runs -----------------------------------------------
def test_closing_during_a_computation_can_stop_it(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(project)
    window.show()
    asked: list[str] = []
    monkeypatch.setattr(
        main_window_module, "ask", lambda _p, title, *_a, **_k: asked.append(title) or True
    )
    window.scenario_view.compute()
    assert not window.close()  # not at once: the thread stops at its next step
    assert asked == ["A computation is still running"]
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=120000)
    assert len(asked) == 1  # asked once, not at every retry


def test_a_new_recent_list_replaces_the_old_one_on_screen(
    window: MainWindow, tmp_path: Path
) -> None:
    window.show()
    first, second = tmp_path / "a", tmp_path / "b"
    window.welcome.set_recent([first, second])
    old = list(window.welcome.recent_buttons)
    window.welcome.set_recent([second])
    assert all(b.isHidden() for b in old)  # not drawn under the new list until deleted
    assert [b.text() for b in window.welcome.recent_buttons] == ["b"]


def test_after_close_project_the_status_line_names_no_project(
    window: MainWindow, project: Path
) -> None:
    window.open_project(project)
    window.close_project()
    assert window.statusBar().currentMessage() == ""
