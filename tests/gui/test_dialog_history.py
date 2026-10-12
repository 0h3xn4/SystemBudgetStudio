"""GUI-8 (decision D-105): using a Qt file dialog must not write settings outside the project."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import budget_gui

pytestmark = pytest.mark.gui

SRC = str(Path(budget_gui.__file__).resolve().parents[1])

SCRIPT = """
import os, sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog

if sys.argv[2] == "app":
    from budget_gui.app import create_app
    app = create_app(["x"])
else:
    app = QApplication(["x"])  # a plain Qt application: Qt's own behaviour
folder = Path(sys.argv[1]) / "somewhere"
folder.mkdir()
QTimer.singleShot(300, lambda: app.activeModalWidget() and app.activeModalWidget().accept())
QFileDialog.getExistingDirectory(None, "Pick", str(folder))
dialog = QFileDialog()
dialog.setFileMode(QFileDialog.FileMode.Directory)
dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
dialog.setDirectory(str(folder))
dialog.show()
app.processEvents()
dialog.accept()
dialog.deleteLater()
app.processEvents()
del dialog
"""


def run_dialog(home: Path, mode: str) -> list[str]:
    """Use a file dialog in a fresh process whose home folder is `home`; the files it left."""
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData"),
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": SRC,
    }
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        env.pop(name, None)
    done = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(home), mode],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return sorted(str(p.relative_to(home)) for p in home.rglob("*") if p.name != "somewhere")


def test_qt_alone_writes_the_dialog_history_into_the_profile(tmp_path: Path) -> None:
    """The control: without our setting Qt does write QtProject.conf (so the next test means
    something)."""
    assert any("QtProject" in name for name in run_dialog(tmp_path / "plain", "plain"))


def test_a_file_dialog_leaves_nothing_in_the_profile(tmp_path: Path) -> None:
    assert run_dialog(tmp_path / "home", "app") == []


def test_the_window_alone_also_keeps_settings_out_of_the_profile(tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    from budget_gui.main_window import MainWindow

    window = MainWindow()
    try:
        assert QSettings.defaultFormat() == QSettings.Format.IniFormat
    finally:
        window.close()
