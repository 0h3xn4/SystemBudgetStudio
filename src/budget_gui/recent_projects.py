# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The list of recently opened project folders, kept only when the user switches it on (D-269).

The window keeps no path of the user's projects by default (D-150): the layout file holds geometry,
the theme and a few words, never a folder. This list is the one exception, and only on request:
it is **off** until *Settings → Remember recent projects* is ticked; ticking it off deletes the
file at once, and *Clear* on the landing page empties it. It lives in its own file
(`recent-projects.txt`, one absolute folder path per line) next to the layout file, so the layout
keeps its rule, and nothing is written when the layout is switched off (`BUDGET_NO_LAYOUT=1`).
Whether the list is on is a word of the layout file (`window/recent`), which names no folder.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

FILE_NAME = "recent-projects.txt"
LIMIT = 8  # folders shown on the landing page
RECENT_STATES = ("off", "on")  # the two values of the `window/recent` word


class RecentProjects:
    """Read and update the list. With `path=None` (layout switched off) it is always empty."""

    def __init__(self, path: Path | None, *, enabled: bool) -> None:
        self._path = path
        self._enabled = enabled and path is not None

    @classmethod
    def beside(cls, layout_path: Path | None, *, enabled: bool) -> RecentProjects:
        """The list in the folder of the layout file (no layout file: no list)."""
        return cls(layout_path.parent / FILE_NAME if layout_path else None, enabled=enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def available(self) -> bool:
        """False when the layout is switched off: the list can then not be switched on."""
        return self._path is not None

    def folders(self) -> list[Path]:
        """The remembered folders that still exist, newest first."""
        if not self._enabled or self._path is None:
            return []
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        seen: list[Path] = []
        for line in lines:
            text = line.strip()
            if not text:
                continue
            folder = Path(text)
            if folder.is_absolute() and folder.is_dir() and folder not in seen:
                seen.append(folder)
        return seen[:LIMIT]

    def add(self, folder: Path) -> None:
        """Put an opened folder at the top (only when the list is on)."""
        if not self._enabled or self._path is None:
            return
        folder = Path(folder).resolve()
        kept = [f for f in self.folders() if f != folder]
        self._write([folder, *kept][:LIMIT])

    def clear(self) -> None:
        """Forget every folder: the file is deleted."""
        if self._path is not None:
            with contextlib.suppress(FileNotFoundError):
                self._path.unlink()

    def set_enabled(self, enabled: bool) -> None:
        """Switch the list on or off; off deletes the file."""
        self._enabled = enabled and self._path is not None
        if not self._enabled:
            self.clear()

    def _write(self, folders: list[Path]) -> None:
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(f"{folder}\n" for folder in folders)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self._path)
