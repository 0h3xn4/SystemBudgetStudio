# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""File menu: start or update a project from an IDM-CIC model (decisions D-240 to D-244)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from budget_core.io.project_loader import load_project
from budget_core.problems import Severity
from budget_gui import idm_import
from budget_gui.main_window import MainWindow
from tests.idm.fixtures import model_xml, write_idm

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def action(window: MainWindow, text: str):  # type: ignore[no-untyped-def]
    for menu in window.menuBar().findChildren(type(window.menuBar().actions()[0].menu())):
        for a in menu.actions():
            if a.text().replace("&", "") == text:
                return a
    raise AssertionError(f"no menu entry {text!r}")


class Answers:
    """Monkeypatched dialogs: the model file, the folder, the voltage and the margin choice."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, model: Path, folder: Path | None) -> None:
        self.shown: list[str] = []
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(model), ""))
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder) if folder else ""
        )
        monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("28", True))
        monkeypatch.setattr(
            QInputDialog, "getItem", lambda w, t, label, items, *a, **k: (items[0], True)
        )

    def box(self, monkeypatch: pytest.MonkeyPatch, answer: QMessageBox.StandardButton) -> None:
        shown = self.shown

        def fake_exec(box: QMessageBox) -> int:
            shown.append(box.detailedText())
            box.done(int(answer))
            return int(answer)

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)


def test_the_file_menu_has_the_entry(window: MainWindow) -> None:
    action(window, "Import IDM-CIC model…")


def test_a_new_project_is_created_after_the_plan_is_confirmed(
    qtbot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    model = write_idm(tmp_path / "synthetic.idm")
    answers = Answers(monkeypatch, model, tmp_path)
    answers.box(monkeypatch, QMessageBox.StandardButton.Yes)
    action(window, "Import IDM-CIC model…").trigger()
    root = tmp_path / "synthetic"
    qtbot.waitUntil(lambda: (root / "project.yaml").is_file(), timeout=20000)
    assert "Units: 5 added." in answers.shown[0]
    loaded = load_project(root)
    assert [p for p in loaded.problems if p.severity is Severity.ERROR] == []
    qtbot.waitUntil(lambda: window.session.project is not None, timeout=20000)
    assert window.session.path == root


def test_saying_no_writes_nothing(
    qtbot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    model = write_idm(tmp_path / "synthetic.idm")
    answers = Answers(monkeypatch, model, tmp_path)
    answers.box(monkeypatch, QMessageBox.StandardButton.No)
    action(window, "Import IDM-CIC model…").trigger()
    qtbot.waitUntil(lambda: bool(answers.shown), timeout=20000)
    assert not (tmp_path / "synthetic").exists()


def test_a_bad_voltage_stops_before_anything_is_read(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = write_idm(tmp_path / "synthetic.idm")
    answers = Answers(monkeypatch, model, tmp_path)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("a lot", True))
    warned: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda w, t, text, *a: warned.append(text))
    action(window, "Import IDM-CIC model…").trigger()
    assert warned and "number" in warned[0] and not answers.shown
    assert not (tmp_path / "synthetic").exists()


def test_a_file_that_is_not_a_model_is_refused_with_the_reason(
    qtbot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    bad = tmp_path / "bad.idm"
    bad.write_bytes(b"nothing")
    Answers(monkeypatch, bad, tmp_path)
    warned: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda w, t, text, *a: warned.append(text))
    action(window, "Import IDM-CIC model…").trigger()
    qtbot.waitUntil(lambda: bool(warned), timeout=20000)
    assert "IDM_FILE_UNREADABLE" in warned[0] and "nothing was written" in warned[0]


def test_work_runs_without_a_window(tmp_path: Path) -> None:
    from budget_core.idm.mapping import ImportOptions

    model = write_idm(tmp_path / "synthetic.idm")
    result = idm_import.work(idm_import.IdmRequest(model, tmp_path / "p", ImportOptions(), 28.0))
    assert result.plan is not None and result.plan.ok and not result.errors
    assert not (tmp_path / "p").exists()  # planning writes nothing


def test_an_open_project_can_be_updated(
    qtbot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    from budget_core.idm.importer import apply_plan, plan_import
    from budget_core.idm.mapping import ImportOptions
    from budget_core.idm.reader import read_idm

    model = write_idm(tmp_path / "synthetic.idm")
    read = read_idm(model)
    assert read.model is not None
    root = tmp_path / "p"
    apply_plan(plan_import(read.model, root, ImportOptions(), bus_voltage_v=28.0))
    assert window.open_project(root)
    from tests.idm.fixtures import model_xml

    newer = write_idm(
        tmp_path / "newer.idm",
        model_xml().replace("<manualMass>2,5</manualMass>", "<manualMass>3</manualMass>"),
    )
    answers = Answers(monkeypatch, newer, None)
    # the first message box asks "update the open project or create a new one"
    asked: list[int] = []

    def fake_exec(box: QMessageBox) -> int:
        if box.buttons() and any(b.text() == "Update the open project" for b in box.buttons()):
            asked.append(1)
            update = next(b for b in box.buttons() if b.text() == "Update the open project")
            update.click()
            return 0
        answers.shown.append(box.detailedText())
        box.done(int(QMessageBox.StandardButton.Yes))
        return int(QMessageBox.StandardButton.Yes)

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    action(window, "Import IDM-CIC model…").trigger()
    qtbot.waitUntil(lambda: bool(answers.shown), timeout=20000)
    assert asked and "existing" in answers.shown[0]
    assert "changed" in answers.shown[0]
    qtbot.waitUntil(
        lambda: (
            window.session.project is not None
            and window.session.project.units["el-1_ss-SS1_eqi-1-1"].mass_kg == 3.0
        ),
        timeout=20000,
    )


def test_the_plan_shows_the_components_it_proposes_and_writes_their_skeletons(
    qtbot,
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    xml = (
        model_xml()
        .replace("Subsystem SS1", "AOCS")
        .replace("<name>Widget</name>", "<name>Inertia Wheel A</name>", 1)
    )
    model = write_idm(tmp_path / "wheel.idm", xml)
    answers = Answers(monkeypatch, model, tmp_path)
    answers.box(monkeypatch, QMessageBox.StandardButton.Yes)
    action(window, "Import IDM-CIC model…").trigger()
    root = tmp_path / "wheel"
    qtbot.waitUntil(lambda: (root / "project.yaml").is_file(), timeout=20000)
    shown = answers.shown[0]
    assert "Components:" in shown and "reaction_wheel" in shown
    assert "Inertia" not in shown  # the equipment is named by its id, not by its name
    assert (root / "config" / "pointing.yaml").is_file()
    assert (root / "idm" / "components.yaml").is_file()
    loaded = load_project(root)
    assert [p for p in loaded.problems if p.severity is Severity.ERROR] == []
