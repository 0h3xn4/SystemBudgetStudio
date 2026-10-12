"""Opening and reloading a project must not freeze the window (audit GUI-14): the load runs in a
thread, the window thread only shows the result, and requests that overlap are answered once."""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from budget_core.io import project_loader
from budget_gui import session as session_module
from budget_gui import widgets
from budget_gui.main_window import MainWindow
from budget_gui.widgets import COLUMN_WIDTH_ROWS, DocTableModel

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(autouse=True)
def _synchronous_loading(monkeypatch: pytest.MonkeyPatch) -> None:  # replaces the conftest one
    monkeypatch.setattr(session_module, "BACKGROUND_LOADING", True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


class SlowLoad:
    """Replaces `load_project` in the session: waits for a release, counts the calls, and records
    the thread it ran in."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, delay_s: float = 0.0) -> None:
        self.calls = 0
        self.threads: list[int] = []
        self.release = threading.Event()
        self.delay_s = delay_s
        self.real = project_loader.load_project
        monkeypatch.setattr(session_module, "load_project", self)

    def __call__(self, path: Path):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.threads.append(threading.get_ident())
        self.release.wait(10)
        if self.delay_s:
            time.sleep(self.delay_s)
        return self.real(path)


def test_opening_in_the_background_returns_at_once_and_keeps_the_event_loop_alive(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    slow = SlowLoad(monkeypatch)
    ticks: list[int] = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(10)
    started = time.monotonic()
    assert window.open_project(project, background=True)
    assert time.monotonic() - started < 0.5  # it did not wait for the load
    assert window.session.loading and window.session.project is None
    qtbot.wait(300)  # the load is held; the window thread keeps running
    assert len(ticks) >= 10
    assert "Loading" in window.statusBar().currentMessage()
    slow.release.set()
    qtbot.waitUntil(lambda: not window.session.loading, timeout=20000)
    timer.stop()
    assert window.session.project is not None
    assert window.tree.topLevelItemCount() > 0
    assert slow.threads and slow.threads[0] != threading.get_ident()  # not the window thread


def test_the_result_arrives_with_one_changed_signal(
    window: MainWindow, project: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.session.changed, timeout=20000):
        window.open_project(project, background=True)
    assert not window.session.loading
    assert window.session.document is not None and window.session.outputs


def test_requests_that_overlap_are_answered_by_one_more_load_and_one_change(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    slow = SlowLoad(monkeypatch)
    changes: list[int] = []
    window.session.changed.connect(lambda: changes.append(1))
    window.open_project(project, background=True)
    window.reload_project()
    window.reload_project()  # three requests, the first load is running
    slow.release.set()
    qtbot.waitUntil(lambda: not window.session.loading, timeout=30000)
    qtbot.wait(100)
    assert slow.calls == 2  # the running one (dropped) and one more for the later requests
    assert len(changes) == 1


def test_a_waiting_reload_beats_a_background_load(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    slow = SlowLoad(monkeypatch)
    window.open_project(project, background=True)
    slow.release.set()
    window.session.reload()  # a program asks for the result now
    shown = window.session.load_result
    assert shown is not None
    qtbot.waitUntil(lambda: not window.session.loading, timeout=20000)
    assert window.session.load_result is shown  # the older background result did not replace it


def test_a_failure_in_the_background_is_a_plain_message(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    def broken(_path: Path):  # type: ignore[no-untyped-def]
        raise RuntimeError("secret detail")

    monkeypatch.setattr(session_module, "load_project", broken)
    with qtbot.waitSignal(window.session.changed, timeout=20000):
        window.open_project(project, background=True)
    codes = [p.code for p in window.session.problems]
    assert codes == ["INTERNAL_ERROR"]
    assert "secret" not in window.session.problems[0].message


def test_closing_while_a_project_loads_waits_for_it(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    slow = SlowLoad(monkeypatch)
    window.show()
    window.open_project(project, background=True)
    assert window.busy()
    started = time.monotonic()
    window.close()
    assert time.monotonic() - started < 0.5  # no freeze
    assert window.isVisible()  # the close waits
    slow.release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=20000)


def test_a_save_in_a_text_tab_reloads_in_the_background(
    window: MainWindow, project: Path, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(project)
    window.open_file("units/obc.yaml")
    slow = SlowLoad(monkeypatch)
    slow.release.set()
    editor = window.editors.current_editor()
    assert editor is not None
    editor.setPlainText(editor.toPlainText() + "\n")
    assert window.save_current()
    assert window.session.loading or slow.calls == 1
    qtbot.waitUntil(lambda: not window.session.loading, timeout=20000)
    assert slow.calls == 1 and slow.threads[0] != threading.get_ident()


# ---- the part of the cost that stays on the window thread: showing the tables -------------------
def test_a_table_cell_is_formatted_once_however_often_qt_asks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtCore import Qt

    from budget_core.reports.document import Column, Table

    table = Table(
        title="t",
        columns=(Column("A", "number", 2), Column("B", "text")),
        rows=((1.0, "x"), (2.0, "y")),
    )
    calls: list[int] = []
    real = widgets.format_cell
    monkeypatch.setattr(widgets, "format_cell", lambda v, c: (calls.append(1), real(v, c))[1])
    model = DocTableModel(table)
    for _ in range(3):
        for role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.TextAlignmentRole):
            for r in range(2):
                for c in range(2):
                    model.data(model.index(r, c), int(role))
    assert len(calls) == 4  # four cells, formatted once each


def test_column_widths_are_taken_from_the_first_rows_only(qtbot) -> None:  # type: ignore[no-untyped-def]
    from budget_core.examples import export_examples

    assert COLUMN_WIDTH_ROWS <= 100
    w = MainWindow()
    qtbot.addWidget(w)
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as folder:
        export_examples(Path(folder))
        w.open_project(Path(folder) / "cubesat_3u")
        view = w.power_view.tabs.widget(0).findChildren(widgets.QTableView)[0]  # type: ignore[union-attr]
        assert view.horizontalHeader().resizeContentsPrecision() == COLUMN_WIDTH_ROWS
    QApplication.processEvents()
