"""A blank project (no units, no scenario, placeholders everywhere) in the window (D-185): every
page opens, says what is missing instead of failing, and nothing raises."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QTabWidget

from budget_core.blank import BlankAnswers, create_blank_project
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    folder = create_blank_project(
        BlankAnswers(project_name="Blank", bus_voltage_v=28.0), tmp_path / "blank"
    )
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.resize(1400, 900)
    w.show()
    w.open_project(folder)
    return w


def every_page(window: MainWindow) -> list[tuple[str, object]]:
    pages: list[tuple[str, object]] = []
    for index in range(window.workspace.count()):
        top = window.workspace.widget(index)
        if isinstance(top, QTabWidget):
            for sub in range(top.count()):
                pages.append((f"{index}.{sub}", (top, sub)))
        else:
            pages.append((f"{index}", (window.workspace, index)))
    return pages


def test_the_project_is_open_and_has_no_error(window: MainWindow) -> None:
    project = window.session.project
    assert project is not None and project.meta.name == "Blank"
    assert not window.session.problems or all(
        p.severity.name != "ERROR" for p in window.session.problems
    )


def test_every_page_opens_without_raising(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    pages = every_page(window)
    assert len(pages) >= 8
    for _name, (container, index) in pages:  # type: ignore[misc]
        if container is not window.workspace:
            window.workspace.setCurrentWidget(container)
        container.setCurrentIndex(index)
        qtbot.wait(20)


def test_computing_a_timeline_without_a_scenario_does_not_start_a_run(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window.show_view(window.timeline_view)
    window.timeline_view.compute()
    qtbot.wait(200)
    assert window.timeline_view.result is None


def test_a_project_with_nothing_to_budget_opens_on_the_model_area(window: MainWindow) -> None:
    """The first step (add a unit) is on the Model area: an empty Power table is no first screen."""
    assert window.workspace.currentIndex() == 0
    assert window.rail.current() == 0 and window.rail.buttons[0].isChecked()
