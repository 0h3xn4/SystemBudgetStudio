"""Keep Qt from writing settings outside the project (decision D-105).

Qt's own file dialog remembers the folders it was last used in. It stores them in
`~/.config/QtProject.conf` (Linux, macOS) or the registry (Windows): state outside the project
folder that names folders of the user's projects. The tool keeps no such state, so the place Qt
writes its settings to is moved to a path that cannot exist and the registry format is not used.
Qt then fails to write quietly; the dialogs just do not remember the last folder.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

# Below the null device on every platform: no folder can be created there ("nul" is a reserved name
# on Windows, "/dev/null" is a file elsewhere), and the angle brackets are invalid in Windows paths.
UNWRITABLE_SETTINGS_PATH = os.devnull + "/<settings disabled>"


def disable_settings_files() -> None:
    """Point every QSettings location at a path that cannot be written. Safe to call repeatedly."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)  # never the Windows registry
    for format_ in (QSettings.Format.IniFormat, QSettings.Format.NativeFormat):
        for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
            QSettings.setPath(format_, scope, UNWRITABLE_SETTINGS_PATH)
