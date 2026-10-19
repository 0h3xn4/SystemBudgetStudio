"""Screenshots of the main pages at every UI size (90, 100, 110, 125 %) in both themes, and the
smallest window each size allows (M6).

    QT_QPA_PLATFORM=offscreen python scripts/ui_scale_shots.py docs/ui/screenshots/m6

The window is 1366 x 768, the smallest screen the brief names. Prints, for each size, the
minimum size of the window and whether every page fits in 1366 x 768 without a sideways scroll
bar; the screenshots are for a person to look at (labels cut off, controls overlapping).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["BUDGET_NO_LAYOUT"] = "1"
ROOT = Path(__file__).resolve().parent.parent
SIZE = (1366, 768)


def main(out: Path) -> int:
    from PySide6.QtCore import QEventLoop, QTimer

    from budget_gui import theme
    from budget_gui.app import create_app
    from budget_gui.main_window import MainWindow

    create_app([])
    out.mkdir(parents=True, exist_ok=True)

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    work = Path(tempfile.mkdtemp(prefix="sbs-scale-"))
    status = 0
    try:
        shutil.copytree(ROOT / "examples" / "microsat_250kg_eps", work / "project")
        window = MainWindow()
        window.resize(*SIZE)
        window.show()
        window.open_project(work / "project")
        wait(300)
        window.run_all()
        deadline = 120.0
        while window.busy() and deadline > 0:
            wait(100)
            deadline -= 0.1
        for percent in theme.SCALES:
            theme.manager().set_scale(percent)
            wait(200)
            window.resize(*SIZE)
            wait(200)
            minimum = window.minimumSizeHint()
            fits = minimum.width() <= SIZE[0] and minimum.height() <= SIZE[1]
            print(
                f"{percent:>3} %: minimum window {minimum.width()} x {minimum.height()}  "
                f"{'fits' if fits else 'DOES NOT FIT'} in {SIZE[0]} x {SIZE[1]}"
            )
            status |= 0 if fits else 1
            for mode in (theme.Mode.LIGHT, theme.Mode.DARK):
                window.set_theme(mode)
                wait(150)
                for index in range(window.workspace.count()):
                    window.workspace.setCurrentIndex(index)
                    wait(120)
                    name = window.workspace.tabText(index).lower()
                    window.grab().save(str(out / f"scale{percent}-{mode.value}-{name}.png"))
        theme.manager().set_scale(100)
        window.editors.discard_all_changes()
        window.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return status


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/ui/screenshots/m6")))
