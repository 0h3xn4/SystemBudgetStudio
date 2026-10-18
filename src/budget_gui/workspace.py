"""The seven tabs of the main area: Model, Power, Mass, Thermal, Link, Compare, Reports (D-151).

*Model* holds the editors (the scenario, the files and the unit tables, opened from the tree).
*Power* and *Link* hold two pages each: the budget tables and the time-domain or pass results.
The tabs are fixed; nothing opens or closes a tab here except the editors inside *Model*.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QTabWidget, QWidget

TABS = ("Model", "Power", "Mass", "Thermal", "Link", "Compare", "Reports")


class SubTabs(QTabWidget):
    """Two or three pages inside one top tab (for example Power: budget and timeline)."""

    def __init__(self, pages: Sequence[tuple[str, QWidget]]) -> None:
        super().__init__()
        self.setDocumentMode(True)
        for title, widget in pages:
            self.addTab(widget, title)


class Workspace(QTabWidget):
    """The main area. `show_view` finds a view wherever it sits and brings it to the front."""

    def __init__(self) -> None:
        super().__init__()
        self.setDocumentMode(True)

    def add_page(self, title: str, widget: QWidget) -> int:
        return self.addTab(widget, title)

    def show_view(self, widget: QWidget) -> bool:
        """Bring `widget` to the front, in its top tab and in the page of that tab. False when it
        is not in the workspace."""
        for index in range(self.count()):
            page = self.widget(index)
            if page is widget:
                self.setCurrentIndex(index)
                return True
            if isinstance(page, QTabWidget) and page.indexOf(widget) >= 0:
                self.setCurrentIndex(index)
                page.setCurrentWidget(widget)
                return True
        return False

    def top_title(self) -> str:
        return self.tabText(self.currentIndex())

    def current_view(self) -> QWidget | None:
        """What the user is looking at: the page of the front tab when it has pages."""
        page = self.currentWidget()
        if isinstance(page, QTabWidget):
            return page.currentWidget()
        return page

    def is_showing(self, widget: QWidget) -> bool:
        """True when `widget` is the front view (or the front tab holding it)."""
        return self.currentWidget() is widget or self.current_view() is widget
