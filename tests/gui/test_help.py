# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Help > User guide: the offline guide inside the window."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def test_guide_opens_without_a_project(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = window.open_guide()
    qtbot.addWidget(dialog)
    text = dialog.browser.toPlainText()
    assert "Quick start" in text and "Equations and sources" in text
    assert "Numbers in the configuration of" not in text


def test_guide_lists_the_open_projects_numbers(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "microsat_250kg")
    dialog = window.open_guide()
    qtbot.addWidget(dialog)
    assert "Numbers in the configuration of" in dialog.browser.toPlainText()


def test_guide_can_be_saved(window: MainWindow, tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = window.open_guide()
    qtbot.addWidget(dialog)
    paths = dialog.save_to(tmp_path)
    assert sorted(p.name for p in paths) == [
        "system-budget-studio-guide.html",
        "system-budget-studio-guide.pdf",
    ]
    assert all(p.stat().st_size > 10000 for p in paths)


def test_about_dialog_names_the_owner_statement_and_the_licence(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    from budget_core import about

    dialog = window.open_about()
    qtbot.addWidget(dialog)
    text = dialog.text_label.text()
    assert about.OWNERSHIP_STATEMENT in text and about.PROJECT_LICENCE_SPDX in text
    assert "About" in dialog.windowTitle()
    from PySide6.QtGui import QAction

    titles = [a.text().replace("&", "") for a in window.findChildren(QAction)]
    assert any(t.startswith("About ") for t in titles)
