"""The small file that remembers the window layout between sessions (D-150, refines D-105).

The window keeps no Qt settings file on purpose (`privacy.py`): Qt's file dialogs would write the
folders the user opened, which is project content, into `~/.config`. The layout is different: the
position and size of the window, the state of its docks, the widths of table columns and the
theme. None of it names a project, a file or a value. It is kept in **one file of our own**, and
only keys of four fixed groups can be written to it, so project content cannot get in by mistake.

The file is `layout.ini` in the per-user application configuration folder (override with the
environment variable `BUDGET_CONFIG_DIR`; `BUDGET_NO_LAYOUT=1` keeps nothing). Delete the file
to reset the layout.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QStandardPaths

FILE_NAME = "layout.ini"
GROUPS = ("window", "dock", "columns", "theme")  # the only groups of the file
MOTION = ("full", "reduced")  # the two values of the `theme/motion` word
RAIL_STATES = ("open", "folded")  # the two values of the `window/rail` word
START_STATES = ("shown", "hidden")  # the two values of the `window/start_here` word
_KEY = re.compile(r"^(window|dock|columns|theme)/[A-Za-z0-9_.-]{1,64}$")


def default_path() -> Path | None:
    """Where the layout is kept, or None when it is switched off."""
    if os.environ.get("BUDGET_NO_LAYOUT"):
        return None
    folder = os.environ.get("BUDGET_CONFIG_DIR") or QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    return Path(folder) / FILE_NAME if folder else None


class LayoutError(ValueError):
    """A key outside the four groups, or a value that is not geometry, a number or a name."""


class LayoutSettings:
    """Read and write layout values. With `path=None` nothing is read and nothing is written."""

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._settings = (
            QSettings(str(path), QSettings.Format.IniFormat) if path is not None else None
        )

    @classmethod
    def default(cls) -> LayoutSettings:
        return cls(default_path())

    @property
    def path(self) -> Path | None:
        return self._path

    @staticmethod
    def _check(key: str) -> None:
        if not _KEY.match(key):
            raise LayoutError("Only keys of the groups window, dock, columns and theme are kept.")

    def bytes_value(self, key: str) -> QByteArray | None:
        self._check(key)
        if self._settings is None:
            return None
        value = self._settings.value(key)
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_bytes(self, key: str, value: QByteArray) -> None:
        self._check(key)
        if self._settings is not None:
            self._settings.setValue(key, value)

    def int_list(self, key: str) -> list[int]:
        self._check(key)
        if self._settings is None:
            return []
        raw = self._settings.value(key)
        if isinstance(raw, str):
            raw = raw.split(",") if raw else []
        try:
            return [int(v) for v in (raw or [])]
        except (TypeError, ValueError):
            return []

    def set_int_list(self, key: str, values: list[int]) -> None:
        self._check(key)
        if self._settings is not None:
            self._settings.setValue(key, ",".join(str(int(v)) for v in values))

    def word(self, key: str, allowed: tuple[str, ...], default: str) -> str:
        """A short name chosen from `allowed` (the theme mode); anything else gives `default`."""
        self._check(key)
        if self._settings is None:
            return default
        value = str(self._settings.value(key, default))
        return value if value in allowed else default

    def set_word(self, key: str, value: str, allowed: tuple[str, ...]) -> None:
        self._check(key)
        if value not in allowed:
            raise LayoutError("That value is not one of the allowed names.")
        if self._settings is not None:
            self._settings.setValue(key, value)

    def clear_group(self, group: str) -> None:
        """Forget every key of one group (for example `dock` and `window` on Reset layout)."""
        if group not in GROUPS:
            raise LayoutError("Only the groups window, dock, columns and theme are kept.")
        if self._settings is not None:
            self._settings.remove(group)

    def sync(self) -> None:
        if self._settings is not None:
            self._settings.sync()

    def clear(self) -> None:
        if self._settings is not None:
            self._settings.clear()
            self._settings.sync()
