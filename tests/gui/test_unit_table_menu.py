"""File menu: export the unit power modes as a table, import a filled-in one after a preview."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for menu in window.menuBar().findChildren(type(window.menuBar().actions()[0].menu())):
        for a in menu.actions():
            if a.text().replace("&", "") == text:
                return a
    raise AssertionError(f"no menu entry {text!r}")


def filled_table(project: Path, tmp_path: Path, avg: str = "2.0 W") -> Path:
    from budget_cli.main import main

    path = tmp_path / "table.csv"
    assert main(["units-export", str(project), "--out", str(path)]) == 0
    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    head = rows[0]
    for r in rows[1:]:
        if r[0] == "radio" and r[head.index("power_mode")] == "downlink":
            r[head.index("avg_power_w")] = avg
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    return path


def radio_downlink_avg(window: MainWindow) -> float:
    project = window.session.project
    assert project is not None
    return next(m for m in project.units["radio"].modes if m.name == "downlink").avg_power_w


def test_the_file_menu_has_both_entries(window: MainWindow) -> None:
    action(window, "Export unit table…")
    action(window, "Import unit table…")


def test_export_writes_the_chosen_file(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "chosen.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    action(window, "Export unit table…").trigger()
    assert target.is_file() and target.stat().st_size > 1000


def test_import_previews_then_applies_and_reloads(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_table(project, tmp_path)
    shown: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))

    def yes(parent, title, text, *a, **k):  # type: ignore[no-untyped-def]
        shown.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", yes)
    assert radio_downlink_avg(window) == pytest.approx(1.8)
    action(window, "Import unit table…").trigger()
    assert len(shown) == 1
    assert "radio" in shown[0] and "downlink" in shown[0] and "avg_power_w" in shown[0]
    assert radio_downlink_avg(window) == pytest.approx(2.0)  # written and reloaded


def test_cancelling_the_preview_writes_nothing(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_table(project, tmp_path)
    before = (project / "units" / "radio.yaml").read_bytes()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    action(window, "Import unit table…").trigger()
    assert (project / "units" / "radio.yaml").read_bytes() == before


def test_a_table_with_problems_is_explained_and_not_applied(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_table(project, tmp_path, avg="a lot")
    before = (project / "units" / "radio.yaml").read_bytes()
    warned: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, text, *a, **k: warned.append(text)
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("no confirmation"))
    action(window, "Import unit table…").trigger()
    assert len(warned) == 1 and "IMPORT_VALUE_INVALID" in warned[0] and "a lot" not in warned[0]
    assert (project / "units" / "radio.yaml").read_bytes() == before


def test_a_table_with_no_changes_says_so(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_table(project, tmp_path, avg="1.8")
    told: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))
    monkeypatch.setattr(
        QMessageBox, "information", lambda parent, title, text, *a, **k: told.append(text)
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("nothing to confirm"))
    action(window, "Import unit table…").trigger()
    assert len(told) == 1 and "No change" in told[0]


def test_unsaved_edits_block_the_import(
    window: MainWindow, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = filled_table(project, tmp_path)
    window.open_file("units/radio.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    editor.textCursor().insertText("# unsaved\n")
    assert window.editors.has_unsaved_changes()
    told: list[str] = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(table), ""))
    monkeypatch.setattr(
        QMessageBox, "information", lambda parent, title, text, *a, **k: told.append(text)
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("must not ask"))
    action(window, "Import unit table…").trigger()
    assert len(told) == 1 and "unsaved" in told[0].lower()
    window.editors.discard_all_changes()
