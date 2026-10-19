"""Save a PNG of every window, tab, sub-tab, panel and dialog, in both themes.

    QT_QPA_PLATFORM=offscreen python scripts/ui_screenshots.py docs/ui/screenshots/before

It opens `examples/microsat_250kg_eps` from a temporary copy, runs the budgets once so every page
has content, and writes `<NN>-<name>-<theme>.png`. Nothing is written outside the output folder
and the temporary copy. Used for the UI overhaul (docs/ui/UI_OVERHAUL.md) to compare before and
after.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["BUDGET_NO_LAYOUT"] = "1"  # the harness keeps no layout file

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget  # noqa: E402

from budget_gui import theme  # noqa: E402
from budget_gui.app import create_app  # noqa: E402
from budget_gui.command_palette import CommandPalette  # noqa: E402
from budget_gui.grid_view import PastePreview  # noqa: E402
from budget_gui.help_view import GuideDialog  # noqa: E402
from budget_gui.legend import LegendDialog  # noqa: E402
from budget_gui.main_window import MainWindow  # noqa: E402
from budget_gui.workspace import SubTabs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "microsat_250kg_eps"
SIZE = (1400, 860)


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_for(condition, timeout_s: float = 120.0) -> None:  # noqa: ANN001
    end = time.monotonic() + timeout_s
    while not condition() and time.monotonic() < end:
        wait(50)


class Shots:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.count = 0
        self.names: list[str] = []
        out.mkdir(parents=True, exist_ok=True)

    def save(self, widget: QWidget, name: str, mode: str) -> None:
        QApplication.processEvents()
        wait(60)
        self.count += 1
        file = f"{self.count:02d}-{name}-{mode}.png"
        widget.grab().save(str(self.out / file))
        self.names.append(file)


def tour(window: MainWindow, shots: Shots, mode: str, project) -> None:  # noqa: ANN001
    snap = lambda widget, name: shots.save(widget, name, mode)  # noqa: E731
    window.resize(*SIZE)
    # the whole window, one shot per workspace tab and sub-tab
    for index in range(window.workspace.count()):
        window.workspace.setCurrentIndex(index)
        title = window.workspace.tabText(index).lower()
        page = window.workspace.widget(index)
        if title == "model":
            for sub in range(window.editors.count()):
                window.editors.setCurrentIndex(sub)
                snap(window, f"model-{window.editors.tabText(sub).lower().replace(' ', '-')}")
            window.open_file("scenarios/one_day.yaml")
            snap(window, "model-yaml-editor")
            window.editors._close_tab(window.editors.currentIndex())  # keeps the tour repeatable
            window.editors.setCurrentIndex(0)
        elif isinstance(page, SubTabs):
            for sub in range(page.count()):
                page.setCurrentIndex(sub)
                snap(window, f"{title}-{page.tabText(sub).lower()}")
        else:
            snap(window, title)
    # the shell at other widths: wide (the inspector and provenance panels), narrow, tiny
    window.workspace.setCurrentIndex(1)
    window.resize(1600, 900)
    for dock in (window.inspector_dock, window.provenance_dock):
        dock.show()
        dock.raise_()
        snap(window, f"shell-wide-{dock.objectName().removeprefix('dock-')}")
    window.resize(1200, 720)
    snap(window, "shell-narrow-1200")
    window.resize(1000, 680)
    snap(window, "shell-tiny-1000")
    window.resize(*SIZE)
    window.rail.set_folded(True)
    snap(window, "shell-rail-folded")
    window.rail.set_folded(False)
    popover = window.show_settings()
    snap(popover, "dialog-settings-popover")
    popover.close()
    # the menus
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        menu.popup(window.mapToGlobal(window.menuBar().actionGeometry(action).bottomLeft()))
        snap(menu, f"menu-{action.text().replace('&', '').lower()}")
        menu.close()
    # the dialogs
    palette = CommandPalette(window.palette_commands(), window)
    palette.show()
    snap(palette, "dialog-command-palette")
    palette.close()
    legend = LegendDialog(window)
    legend.show()
    snap(legend, "dialog-cell-styles")
    legend.close()
    guide = GuideDialog(project, window)
    guide.show()
    snap(guide, "dialog-user-guide")
    guide.close()
    paste = PastePreview(
        [("Reaction wheel / mass_kg", "1.2", "1.4"), ("Battery / capacity_wh", "800", "900")],
        2,
        window,
    )
    paste.show()
    snap(paste, "dialog-paste-preview")
    paste.close()
    box = QMessageBox(
        QMessageBox.Icon.Question,
        "System Budget Studio",
        "This file has unsaved changes.",
        QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        window,
    )
    box.show()
    snap(box, "dialog-message-box")
    box.close()
    wizard = window.open_guided_wizard(Path(tempfile.gettempdir()) / "sbs-wizard")
    snap(wizard, "dialog-wizard-1")
    wizard.close()


def main(out: Path) -> int:
    create_app([])
    shots = Shots(out)
    work = Path(tempfile.mkdtemp(prefix="sbs-shots-"))
    try:
        project_dir = work / "project"
        shutil.copytree(EXAMPLE, project_dir)
        window = MainWindow()
        window.resize(*SIZE)
        t0 = time.perf_counter()
        window.show()
        window.set_theme(theme.Mode.LIGHT)
        shots.save(window, "welcome", "light")
        window.set_theme(theme.Mode.DARK)
        shots.save(window, "welcome", "dark")
        window.open_project(project_dir)
        wait_for(lambda: window.session.project is not None)
        window.run_all()
        wait(300)
        wait_for(lambda: not window.run_controller.is_running())
        wait(500)
        print(f"open and run: {time.perf_counter() - t0:.1f} s")
        other = work / "other"
        shutil.copytree(ROOT / "examples" / "microsat_150kg", other)
        window.compare_view.set_other_folder(other)
        window.compare_view.compare_button.click()
        wait(300)
        wait_for(lambda: window.compare_view._worker is None)
        wait(300)
        window.tree.setCurrentItem(window.tree.topLevelItem(0).child(1).child(0))  # a unit
        project = window.session.project
        for mode in (theme.Mode.LIGHT, theme.Mode.DARK):
            window.set_theme(mode)
            tour(window, shots, mode.value, project)
        window.editors.discard_all_changes()
        window.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"{shots.count} screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/ui/screenshots/before")))
