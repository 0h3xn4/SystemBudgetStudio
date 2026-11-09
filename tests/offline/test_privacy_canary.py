# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""No project content outside the project and the output folder (a canary test).

A project whose folder, name, unit name and source texts carry a unique marker is run through the
command line and the window, in a sandbox whose home, configuration, cache, data and temporary
folders are empty and are the only ones the program can use. Afterwards no file in the sandbox may
contain the marker, in UTF-8 or in UTF-16, and the project folder gets no new file. The only file
the window may keep is its layout file, which holds geometry and the theme, never a name or a path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

CANARY = "CANARY-QX7-d41e"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
SOURCE_TEXT = "Synthetic example value; not from a data sheet or a standard."


def _marked_project(root: Path) -> Path:
    project = root / f"{CANARY}-folder" / "satellite"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", project)
    for relative, old, new in (
        ("project.yaml", "name: ", f"name: {CANARY} "),
        ("units/radio.yaml", "name: ", f"name: {CANARY} "),
        ("config/power_system.yaml", SOURCE_TEXT, f"{CANARY} source text"),
    ):
        path = project / relative
        text = path.read_text(encoding="utf-8")
        assert old in text, relative
        path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    return project


def _sandbox(root: Path) -> tuple[Path, dict[str, str]]:
    box = root / "sandbox"
    folders = {
        name: box / name for name in ("home", "config", "cache", "data", "tmp", "roaming", "local")
    }
    for folder in folders.values():
        folder.mkdir(parents=True)
    env = dict(os.environ)
    for key in ("BUDGET_CONFIG_DIR", "BUDGET_NO_LAYOUT", "BUDGET_USER"):
        env.pop(key, None)
    env.update(
        HOME=str(folders["home"]),
        USERPROFILE=str(folders["home"]),
        APPDATA=str(folders["roaming"]),
        LOCALAPPDATA=str(folders["local"]),
        XDG_CONFIG_HOME=str(folders["config"]),
        XDG_CACHE_HOME=str(folders["cache"]),
        XDG_DATA_HOME=str(folders["data"]),
        TMPDIR=str(folders["tmp"]),
        TEMP=str(folders["tmp"]),
        TMP=str(folders["tmp"]),
        QT_QPA_PLATFORM="offscreen",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return box, env


CLI = """
import sys
from budget_cli.main import main
sys.exit(main(sys.argv[1:]))
"""

WINDOW = """
import sys, time
from pathlib import Path
from PySide6.QtCore import QEventLoop, QTimer
from budget_gui.app import create_app
from budget_gui.main_window import MainWindow

def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def wait_for(condition, seconds=120.0):
    end = time.monotonic() + seconds
    while not condition() and time.monotonic() < end:
        wait(50)

app = create_app(["x"])
window = MainWindow()
window.resize(1400, 860)
window.show()
window.open_project(Path(sys.argv[1]))
wait_for(lambda: window.session.project is not None)
window.run_all()
wait(300)
wait_for(lambda: not window.run_controller.is_running())
for area in range(window.workspace.count()):
    window.workspace.setCurrentIndex(area)
    wait(100)
window.editors.discard_all_changes()
window.close()
"""


def _run(env: dict[str, str], code: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(code), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert result.returncode in (0, 1), result.stderr[-800:]  # 1: a finding of the example


def _files(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if path.is_file())


def _contains_canary(path: Path) -> bool:
    data = path.read_bytes()
    return any(marker in data for marker in (CANARY.encode(), CANARY.encode("utf-16-le")))


def test_no_project_content_reaches_the_sandbox(tmp_path: Path) -> None:
    project = _marked_project(tmp_path)
    before = {p.relative_to(project) for p in _files(project)}
    box, env = _sandbox(tmp_path)
    out = tmp_path / "out"  # the outputs may name the project: this folder is not scanned
    for command in (
        ["validate", str(project)],
        ["run", str(project), "--budget", "all", "--out", str(out)],
        ["scenario", str(project), "--out", str(out)],
        ["power-timeline", str(project), "--out", str(out)],
    ):
        _run(env, CLI, *command)
    _run(env, WINDOW, str(project))

    kept = _files(box)
    leaked = [str(p.relative_to(box)) for p in kept if _contains_canary(p)]
    assert leaked == [], f"project content in: {leaked}"
    assert not list((tmp_path / "out").rglob("nothing")), "sanity: the output folder is not scanned"
    assert any(_contains_canary(p) for p in _files(out)), "sanity: the outputs do name the project"
    after = {p.relative_to(project) for p in _files(project)}
    assert after == before, f"new files in the project folder: {sorted(after - before)}"
    layout = [p for p in kept if p.name == "layout.ini"]
    assert len(layout) <= 1
    unexpected = [str(p.relative_to(box)) for p in kept if p.name != "layout.ini"]
    assert unexpected == [], f"other files kept outside the project: {unexpected}"
