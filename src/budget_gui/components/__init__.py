"""The component library of the window (D-169): the parts every view is made of.

Views use these instead of styling their own widgets: a button has a kind, a status has a badge, a
list that is empty has an empty state, a confirmation is a toast. Their look is the style sheet's
(`budget_gui.theme.qss`); `scripts/ui_gallery.py` shows all of them in both themes.
"""

from budget_gui.components.badge import StatusBadge
from budget_gui.components.buttons import KINDS, Button, icon_button
from budget_gui.components.containers import Card, EmptyState, KeyValueList, SectionHeader
from budget_gui.components.message_dialog import MessageDialog, ask, inform
from budget_gui.components.segmented import SegmentedControl
from budget_gui.components.toast import Toast

__all__ = [
    "KINDS",
    "Button",
    "Card",
    "EmptyState",
    "KeyValueList",
    "MessageDialog",
    "SectionHeader",
    "SegmentedControl",
    "StatusBadge",
    "Toast",
    "ask",
    "icon_button",
    "inform",
]
