"""The seven areas of the main area: Model, Power, Mass, Thermal, Link, Compare, Reports (D-151).

*Model* holds the editors (the scenario, the files and the unit tables, opened from the tree).
*Power* and *Link* hold two pages each: the budget tables and the time-domain or pass results.
The areas are fixed; nothing opens or closes one here except the editors inside *Model*. The
navigation rail chooses the area (D-173), so the tab bar of the workspace is hidden; the pages
inside an area are chosen with a segmented control (the `SubTabs` pills).
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QTabWidget, QWidget

TABS = ("Model", "Power", "Mass", "Thermal", "Link", "Compare", "Reports")


def segmented_tabs(tabs: QTabWidget) -> None:
    """Show the tabs of `tabs` as a segmented control (pills), not as a row of tabs."""
    tabs.setDocumentMode(True)
    bar = tabs.tabBar()
    if bar is not None:
        bar.setProperty("role", "segmented")
        bar.setExpanding(False)
        bar.setDrawBase(False)


class SubTabs(QTabWidget):
    """Two or three pages inside one area (for example Power: budget and timeline)."""

    def __init__(self, pages: Sequence[tuple[str, QWidget]]) -> None:
        super().__init__()
        segmented_tabs(self)
        for title, widget in pages:
            self.addTab(widget, title)


class Workspace(QTabWidget):
    """The main area. `show_view` finds a view wherever it sits and brings it to the front."""

    def __init__(self) -> None:
        super().__init__()
        self.setDocumentMode(True)
        bar = self.tabBar()
        if bar is not None:
            bar.hide()  # the rail chooses the area
        # its hidden tab bar is its focus proxy: a Tab that reached it would go nowhere
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _without_bar(self, size: QSize) -> QSize:
        """The hidden tab bar takes no room, though QTabWidget still counts it."""
        bar = self.tabBar()
        if bar is not None and bar.isHidden():
            size.setHeight(max(size.height() - bar.sizeHint().height(), 0))
        return size

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return self._without_bar(super().minimumSizeHint())

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return self._without_bar(super().sizeHint())

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
