"""The Assumptions page of the Model area (D-218): everything that is active for the project."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_core.assumptions_view import CHOICES, CONFIGURATION, CREATION, SETTINGS, assumptions
from budget_core.io.project_loader import load_project
from budget_gui.assumptions_page import file_of
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path):  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def test_the_page_is_a_tab_of_the_model_area_and_lists_every_row(
    window: MainWindow, project: Path
) -> None:
    tabs = [window.editors.tabText(i) for i in range(window.editors.count())]
    assert "Assumptions" in tabs
    loaded = load_project(project).project
    assert loaded is not None
    page = window.assumptions_page
    assert page.model.rowCount() == len(assumptions(loaded))
    assert page.table.isVisibleTo(window) or not page.empty.isVisibleTo(window)
    assert "rows" in page.count_label.text()


def test_the_command_and_the_menu_bring_the_page_to_the_front(window: MainWindow) -> None:
    window.editors.setCurrentWidget(window.units_page)
    window.assumptions_action.trigger()
    assert window.editors.currentWidget() is window.assumptions_page
    commands = [c.text for c in window.palette_commands()]
    assert any(text.endswith("Show the assumptions") for text in commands)
    assert window.assumptions_action.shortcut().toString() == "Ctrl+Shift+A"


def test_the_section_control_and_the_filter_narrow_the_list(window: MainWindow) -> None:
    page = window.assumptions_page
    total = page.proxy.rowCount()
    page.sections.set_current(SETTINGS)
    settings_rows = page.visible_rows()
    assert 0 < len(settings_rows) < total and {r.section for r in settings_rows} == {SETTINGS}
    page.sections.set_current(CREATION)
    assert {r.section for r in page.visible_rows()} == {CREATION}
    page.sections.set_current("all")
    assert page.proxy.rowCount() == total
    page.filter_edit.setText("WGS-72")
    rows = page.visible_rows()
    assert rows and all("wgs-72" in (r.name + r.value + r.source).lower() for r in rows)
    assert rows[0].section == CHOICES
    page.filter_edit.setText("zzzzzz")
    assert page.proxy.rowCount() == 0 and page.count_label.text().startswith("0 of ")
    page.filter_edit.clear()
    assert page.proxy.rowCount() == total


def test_the_filter_needs_every_word_in_any_order(window: MainWindow) -> None:
    page = window.assumptions_page
    page.filter_edit.setText("placeholder margin")
    rows = page.visible_rows()
    assert rows and all(r.status == "placeholder" and "margin" in r.name for r in rows)
    page.filter_edit.setText("margin placeholder")
    assert len(page.visible_rows()) == len(rows)


def test_numbers_are_in_the_monospace_face_and_values_are_right_aligned(window: MainWindow) -> None:
    from budget_gui import theme

    page = window.assumptions_page
    index = page.proxy.index(0, 1)
    assert page.proxy.data(index, Qt.ItemDataRole.FontRole) == theme.mono_font()
    align = page.proxy.data(index, Qt.ItemDataRole.TextAlignmentRole)
    assert align & int(Qt.AlignmentFlag.AlignRight)


def test_a_row_that_names_a_file_opens_it_at_the_field(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, int | None]] = []
    monkeypatch.setattr(window, "open_file", lambda rel, line=None: opened.append((rel, line)))
    page = window.assumptions_page
    page.sections.set_current(CONFIGURATION)
    index = page.proxy.index(0, 0)
    page.table.doubleClicked.emit(index)
    assert opened and opened[0][0].startswith(("config/", "links/")) and opened[0][1] is not None


def test_a_row_without_a_file_opens_nothing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(window, "open_file", lambda rel, line=None: opened.append(rel))
    page = window.assumptions_page
    page.sections.set_current(SETTINGS)
    page.table.doubleClicked.emit(page.proxy.index(0, 0))
    assert opened == []


def test_file_of_splits_the_where_text() -> None:
    from budget_core.assumptions_view import Row

    row = Row("s", "n", "1", "", "", "sourced", "config/a.yaml classes.x.y")
    assert file_of(row) == ("config/a.yaml", "classes.x.y")
    assert file_of(Row("s", "n", "1", "", "", "fixed", "Not selectable in this version")) == (
        "",
        "",
    )


def test_without_a_project_the_page_says_what_it_is_for(qtbot) -> None:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w)
    page = w.assumptions_page
    assert page.model.rowCount() == 0 and not page.empty.isHidden()
    assert not page.filter_edit.isEnabled()


def test_the_page_follows_the_project_when_it_is_reloaded(
    window: MainWindow, project: Path
) -> None:
    before = window.assumptions_page.model.rowCount()
    path = project / "config" / "margin_policy.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("system_power_margin_ratio", "system_power_margin_ratio"))
    window.open_project(project)
    assert window.assumptions_page.model.rowCount() == before
