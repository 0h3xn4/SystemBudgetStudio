"""File menu: export the Eb/N0 table, the attenuation table and the margin policy as spreadsheets,
import a filled-in one after a preview (D-231, D-249)."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def submenu(window: MainWindow, title: str) -> QMenu:
    for menu in window.findChildren(QMenu):
        if menu.title().replace("&", "") == title:
            return menu
    raise AssertionError(f"no submenu {title!r}")


def entry(menu: QMenu, text: str) -> QAction:
    for a in menu.actions():
        if a.text().replace("&", "") == text:
            return a
    raise AssertionError(f"no entry {text!r}")


def test_the_file_menu_has_both_submenus_with_the_three_tables(window: MainWindow) -> None:
    for title in ("Export tables", "Import tables"):
        menu = submenu(window, title)
        assert [a.text().replace("&", "") for a in menu.actions()] == [
            "Eb/N0 table…",
            "Attenuation table…",
            "Margin policy…",
        ]


def test_the_menu_letters_are_not_used_twice(window: MainWindow) -> None:
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is None:
            continue
        letters = [a.text().split("&")[1][0].lower() for a in menu.actions() if "&" in a.text()]
        assert len(letters) == len(set(letters)), (top.text(), letters)


def test_the_palette_offers_the_tables(window: MainWindow) -> None:
    names = [c.text for c in window.palette_commands()]
    assert "File > Export tables > Margin policy" in names
    assert "File > Import tables > Eb/N0 table" in names


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
@pytest.mark.parametrize("name", ["Eb/N0 table…", "Attenuation table…", "Margin policy…"])
def test_export_writes_the_chosen_file(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    suffix: str,
) -> None:
    target = tmp_path / f"chosen{suffix}"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    entry(submenu(window, "Export tables"), name).trigger()
    assert target.is_file() and target.stat().st_size > 100
    assert window.toast.text().startswith("Wrote ")


def test_a_name_that_is_not_a_table_is_refused(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "x.txt"), "")
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda p, t, text, *a, **k: warned.append(text))
    entry(submenu(window, "Export tables"), "Margin policy…").trigger()
    assert warned and ".csv or .xlsx" in warned[0]
    assert not (tmp_path / "x.txt").exists()


def filled_margins(project: Path, tmp_path: Path) -> Path:
    from budget_cli.main import main

    path = tmp_path / "margins.csv"
    assert main(["tables-export", str(project), "margins", "--out", str(path)]) == 0
    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    head = rows[0]
    for r in rows[1:]:
        if r[0] == "class_a" and r[1] == "mass_margin_ratio":
            r[head.index("margin_ratio")] = "0.1"
            r[head.index("source")] = "Margin policy rev B"
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    return path


def class_a_mass_margin(window: MainWindow) -> float | None:
    project = window.session.project
    assert project is not None and project.config.margin_policy is not None
    return project.config.margin_policy.classes["class_a"].mass_margin_ratio.value


def test_import_previews_then_applies_and_reloads(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_margins(project, tmp_path)
    shown: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))

    def yes(parent, title, text, *a, **k):  # type: ignore[no-untyped-def]
        shown.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", yes)
    assert class_a_mass_margin(window) is None
    entry(submenu(window, "Import tables"), "Margin policy…").trigger()
    assert len(shown) == 1
    assert "class_a / mass_margin_ratio" in shown[0] and "margin_policy.yaml" in shown[0]
    assert class_a_mass_margin(window) == pytest.approx(0.1)  # written and reloaded
    assert window.toast.text().startswith("Updated ")


def test_cancelling_the_preview_writes_nothing(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_margins(project, tmp_path)
    before = (project / "config" / "margin_policy.yaml").read_bytes()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    entry(submenu(window, "Import tables"), "Margin policy…").trigger()
    assert (project / "config" / "margin_policy.yaml").read_bytes() == before


def test_a_table_that_changes_nothing_says_so(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from budget_cli.main import main

    path = tmp_path / "same.csv"
    assert main(["tables-export", str(project), "ebn0", "--out", str(path)]) == 0
    told: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, text, *a, **k: told.append(text))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("no confirmation"))
    entry(submenu(window, "Import tables"), "Eb/N0 table…").trigger()
    assert told and told[0].startswith("No change")


def test_a_value_without_its_source_is_explained_and_not_applied(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_margins(project, tmp_path)
    rows = list(csv.reader(table.read_text(encoding="utf-8").splitlines()))
    head = rows[0]
    for r in rows[1:]:
        if r[0] == "class_a" and r[1] == "mass_margin_ratio":
            r[head.index("source")] = ""
    with table.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    before = (project / "config" / "margin_policy.yaml").read_bytes()
    warned: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))
    monkeypatch.setattr(QMessageBox, "warning", lambda p, t, text, *a, **k: warned.append(text))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("no confirmation"))
    entry(submenu(window, "Import tables"), "Margin policy…").trigger()
    assert len(warned) == 1 and "IMPORT_SOURCE_MISSING" in warned[0]
    assert (project / "config" / "margin_policy.yaml").read_bytes() == before


def test_unsaved_edits_stop_an_import(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    told: list[str] = []
    monkeypatch.setattr(window.editors, "has_unsaved_changes", lambda: True)
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, text, *a, **k: told.append(text))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: pytest.fail("no file dialog")
    )
    entry(submenu(window, "Import tables"), "Eb/N0 table…").trigger()
    monkeypatch.undo()  # the window must not close with "unsaved changes" asking a question
    assert told and "unsaved" in told[0]
