"""Support aids for a program that fails on a machine nobody else can see (D-257).

Two things, both opt-in and both free of project content:

* `enable_fault_log(path)`: when the process dies of a native fault (an access violation, an abort)
  Python's `faulthandler` writes the stack of every thread to `path`. The lines are the names of
  functions and files of the program itself; nothing is written while nothing goes wrong. A window
  that closes without a word on someone else's computer says nothing otherwise: the windowed
  program has no console and a native crash shows no message.
* `environment_lines()`: the facts that decide most start-up problems (the version, Python, the
  system, whether the bundled fonts and icons were found). The window adds what Qt knows
  (`budget_gui.diagnostics`).
"""

from __future__ import annotations

import faulthandler
import os
import platform
import sys
from pathlib import Path
from typing import TextIO

from budget_core import APP_NAME, __version__
from budget_core.assets import assets_dir, icon_files, ui_icon_files

_FAULT_FILE: TextIO | None = None
_FONT_FILES = ("Inter-Regular.ttf", "JetBrainsMono-Regular.ttf")


def enable_fault_log(path: Path) -> None:
    """Write the Python stack of every thread to `path` if the process dies of a native fault."""
    global _FAULT_FILE
    disable_fault_log()
    handle = Path(path).open("w", encoding="utf-8", buffering=1)  # noqa: SIM115 (kept open)
    faulthandler.enable(file=handle, all_threads=True)
    _FAULT_FILE = handle


def disable_fault_log() -> None:
    global _FAULT_FILE
    if _FAULT_FILE is not None:
        faulthandler.disable()
        _FAULT_FILE.close()
        _FAULT_FILE = None


def environment_lines() -> list[str]:
    """What the program knows about itself and its machine, without Qt and without any project."""
    kind = "bundled" if getattr(sys, "frozen", False) else "source"
    lines = [
        f"{APP_NAME} {__version__}",
        f"Python {platform.python_version()} ({kind})",
        f"System {platform.platform()}, {platform.machine()}",
    ]
    try:
        folder = assets_dir()
    except FileNotFoundError:
        lines.append("Assets folder: NOT FOUND (no bundled fonts or icons)")
    else:
        fonts = [name for name in _FONT_FILES if (folder / "fonts" / name).is_file()]
        lines.append(f"Assets folder: {folder}")
        lines.append(
            f"Bundled fonts found: {len(fonts)} of {len(_FONT_FILES)} checked; "
            f"application icons: {len(icon_files())}; "
            f"user-interface icons (book-open): {len(ui_icon_files('book-open'))} sizes"
        )
    names = sorted(k for k in os.environ if k.startswith(("QT_", "BUDGET_")))
    lines.append(
        "Environment: " + (", ".join(f"{k}={os.environ[k]}" for k in names) or "(none set)")
    )
    return lines
