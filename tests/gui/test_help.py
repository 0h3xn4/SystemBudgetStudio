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


def test_third_party_licences_dialog_shows_the_notices_or_says_where_they_are(
    window: MainWindow,
    qtbot,
    tmp_path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    from budget_core import about

    # a copy that is not installed: the text says where the licences are
    dialog = window.open_notices()
    qtbot.addWidget(dialog)
    assert about.NOT_INSTALLED_TEXT in dialog.view.toPlainText()
    assert dialog.view.isReadOnly()
    # an installed copy: the file next to the program
    notices = tmp_path / about.NOTICES_FILE
    notices.write_text("THIRD-PARTY NOTICES\nzlib licence text\n", encoding="utf-8")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(tmp_path / "system-budget-studio"))
    assert about.third_party_text().startswith("THIRD-PARTY NOTICES")
    shown = window.open_notices()
    qtbot.addWidget(shown)
    assert "zlib licence text" in shown.view.toPlainText()
    from PySide6.QtGui import QAction

    titles = [a.text().replace("&", "") for a in window.findChildren(QAction)]
    assert "Third-party licences…" in titles


def test_the_report_name_setting_is_kept_and_used(window: MainWindow, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from budget_core import provenance
    from budget_gui.layout_settings import LayoutSettings

    window.layout_settings = LayoutSettings(tmp_path / "layout.ini")
    popover = window.show_settings()
    qtbot.addWidget(popover)
    assert popover.report_name_edit.text() == provenance.default_user() == ""
    popover.report_name_edit.setText("A. Engineer")
    popover.report_name_edit.editingFinished.emit()
    assert provenance.default_user() == "A. Engineer"
    assert window.layout_settings.text("reports/name") == "A. Engineer"
    assert provenance.resolve_user() == "A. Engineer"
    popover.report_name_edit.setText("")
    popover.report_name_edit.editingFinished.emit()
    assert provenance.resolve_user() == "unknown"


def test_the_first_screen_shows_the_disclaimer(window: MainWindow) -> None:
    from budget_core import disclaimer

    assert window.welcome.disclaimer.text() == disclaimer.DISCLAIMER
