"""A button that folds the lower pane of a vertical splitter away and brings it back (D-178).

The plot of a view is what the user came for and the tables under it are what they check next:
with three stacked plots the table is a row or two high, so it can be folded to give the plots
all the room, and unfolded to the height it had.
"""

from __future__ import annotations

from PySide6.QtWidgets import QSplitter

from budget_gui.components.buttons import Button


class CollapseButton(Button):
    """*Hide table* / *Show table* for the second pane of `splitter`."""

    def __init__(self, splitter: QSplitter, what: str = "table") -> None:
        super().__init__("", "ghost", icon="chevron-down", compact=True)
        self._splitter = splitter
        self._what = what
        self._kept: list[int] = []
        splitter.setCollapsible(1, True)
        splitter.splitterMoved.connect(lambda *_a: self._sync())
        self.clicked.connect(self.toggle)
        self._sync()

    def is_folded(self) -> bool:
        sizes = self._splitter.sizes()
        return len(sizes) > 1 and sizes[1] == 0

    def toggle(self) -> None:
        if self.is_folded():
            sizes = self._kept if len(self._kept) == 2 and self._kept[1] > 0 else None
            total = sum(self._splitter.sizes())
            self._splitter.setSizes(sizes or [total * 3 // 5, total - total * 3 // 5])
        else:
            self._kept = self._splitter.sizes()
            self._splitter.setSizes([sum(self._kept), 0])
        self._sync()

    def _sync(self) -> None:
        folded = self.is_folded()
        self.setText(f"Show {self._what}" if folded else f"Hide {self._what}")
        self._icon_name = "chevron-up" if folded else "chevron-down"
        self._retint()
        self.set_tip(f"{'Show' if folded else 'Hide'} the {self._what} under the plot")
