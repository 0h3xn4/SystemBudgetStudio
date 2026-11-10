# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Write the eleven screenshots of `docs/images/ui-overhaul/` (light theme) from the current window.

    QT_QPA_PLATFORM=offscreen python scripts/ui_doc_shots.py docs/images/ui-overhaul

It opens `examples/microsat_250kg_eps` from a temporary copy, runs the budgets once and saves one
PNG per image the documentation shows (focused view, power budget with the Problems list, Explain,
power timeline, the Model pages, the scenario statistics) and, from a blank project made with
`budget new`, the Start here card, and the landing page (a folder offered at start, the list of
recent projects switched on, kept in the temporary folder). Nothing is written outside the
output folder and the temporary copies. Run it after a change of the window that the pages
show, and read each image before you commit it.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["BUDGET_NO_LAYOUT"] = "1"  # the harness keeps no layout file

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QTableView, QTabWidget  # noqa: E402

from budget_cli.main import main as cli_main  # noqa: E402
from budget_gui import theme  # noqa: E402
from budget_gui.app import create_app  # noqa: E402
from budget_gui.layout_settings import LayoutSettings  # noqa: E402
from budget_gui.main_window import MainWindow  # noqa: E402
from budget_gui.workspace import SubTabs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "microsat_250kg_eps"
SIZE = (1400, 860)
TALL = (1400, 1000)


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_for(condition: Callable[[], bool], timeout_s: float = 120.0) -> None:
    end = time.monotonic() + timeout_s
    while not condition() and time.monotonic() < end:
        wait(50)


def shot(window: MainWindow, out: Path, name: str) -> None:
    QApplication.processEvents()
    wait(120)
    window.grab().save(str(out / f"{name}-light.png"))
    print("wrote", name)


def page(window: MainWindow, area: int, index: int) -> None:
    window.workspace.setCurrentIndex(area)
    sub_tabs = window.workspace.widget(area)
    assert isinstance(sub_tabs, SubTabs)
    sub_tabs.setCurrentIndex(index)


def open_example(work: Path) -> MainWindow:
    project = work / "example"
    shutil.copytree(EXAMPLE, project)
    window = MainWindow()
    window.resize(*SIZE)
    window.show()
    window.set_theme(theme.Mode.LIGHT)
    window.open_project(project)
    wait_for(lambda: window.session.project is not None)
    window.run_all()
    wait(300)
    wait_for(lambda: not window.run_controller.is_running())
    wait(500)
    window.tree.setCurrentItem(window.tree.topLevelItem(0).child(1).child(0))  # a unit
    return window


def explain_shot(window: MainWindow, out: Path) -> None:
    window.power_view.build_pages()
    for view in window.power_view.findChildren(QTableView):
        model = view.model()
        table = getattr(model, "table", None)
        if table is None or table.explain_id != "power:summary":
            continue
        page(window, 1, 0)
        window.power_view.tabs.setCurrentIndex(0)
        column = next(
            i
            for i, c in enumerate(table.columns)
            if c.header == "Average at source, with margins (W)"
        )
        view.setCurrentIndex(model.index(3, column))
        window.explain_action.trigger()
        shot(window, out, "explain")
        window.explain_dock.hide()
        return
    raise RuntimeError("the power summary table was not found")


def model_shots(window: MainWindow, out: Path) -> None:
    window.workspace.setCurrentIndex(0)
    for index in range(window.editors.count()):
        name = window.editors.tabText(index).lower().replace(" ", "-")
        window.editors.setCurrentIndex(index)
        if name in ("units", "assumptions"):
            shot(window, out, f"model-{name}")
        elif name == "power-modes":
            window.resize(*TALL)
            shot(window, out, "model-power-modes")
            window.resize(*SIZE)
        elif name == "scenario":
            window.resize(*TALL)
            shot(window, out, "model-scenario")
            for tabs in window.scenario_view.findChildren(QTabWidget):
                for i in range(tabs.count()):
                    if tabs.tabText(i) == "Statistics":
                        tabs.setCurrentIndex(i)
            shot(window, out, "scenario-statistics")
            window.resize(*SIZE)


def landing_page_shot(work: Path, out: Path) -> None:
    """The landing page with a folder offered at start and two recent projects."""
    folders = []
    for name in ("microsat_150kg", "microsat_250kg_eps"):
        folder = work / "projects" / name
        shutil.copytree(ROOT / "examples" / name, folder)
        folders.append(folder)
    window = MainWindow(LayoutSettings(work / "config" / "layout.ini"))  # the list needs a file
    window.resize(*SIZE)
    window.show()
    window.set_theme(theme.Mode.LIGHT)
    window.set_remember_recent(True)
    for folder in folders:
        window.open_project(folder)
        wait_for(lambda: window.session.project is not None)
    window.close_project()
    window.offer_launch_folder(folders[-1])
    wait(300)
    shot(window, out, "landing-page")
    window.close()


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    create_app([])
    work = Path(tempfile.mkdtemp(prefix="sbs-docshots-"))
    try:
        window = open_example(work)
        page(window, 1, 0)
        shot(window, out, "focused-view")  # the default view
        window.set_view_mode(False)  # the full view: the Problems list, the Explain panel
        window.reveal_problems()
        shot(window, out, "power-budget")
        explain_shot(window, out)
        window.set_view_mode(True)
        page(window, 1, 1)
        shot(window, out, "power-timeline")
        model_shots(window, out)
        window.editors.discard_all_changes()
        window.close()

        blank = work / "my_satellite"
        if cli_main(["new", str(blank), "--bus-voltage-v", "28"]) != 0:
            raise RuntimeError("budget new failed")
        fresh = MainWindow()
        fresh.resize(*SIZE)
        fresh.show()
        fresh.set_theme(theme.Mode.LIGHT)
        fresh.open_project(blank)
        wait_for(lambda: fresh.session.project is not None)
        fresh.workspace.setCurrentIndex(0)
        wait(500)
        shot(fresh, out, "start-here")
        fresh.editors.discard_all_changes()
        fresh.close()

        landing_page_shot(work, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/images/ui-overhaul")))
