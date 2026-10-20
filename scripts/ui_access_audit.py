"""List what a screen reader or a keyboard user would miss in the window (M6 accessibility pass).

    QT_QPA_PLATFORM=offscreen python scripts/ui_access_audit.py

Opens the example project, visits every area and page, and walks every widget: a control that
shows only an icon needs an accessible name and a tooltip, a view or a plot that takes the
keyboard needs a name, an input needs a name (or a tooltip that says what it is). The dialogs and
the settings card are walked too. Prints one line per finding and the count; the same walk is
`tests/gui/test_accessibility.py`, which fails on any finding.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["BUDGET_NO_LAYOUT"] = "1"
ROOT = Path(__file__).resolve().parent.parent


def _describe(widget) -> str:  # noqa: ANN001
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit

    hint = ""
    if isinstance(widget, QLineEdit):
        hint = f" [{widget.placeholderText()[:30]}]"
    elif isinstance(widget, QComboBox):
        hint = f" [{widget.currentText()[:20]}|{widget.count()}]"
    elif isinstance(widget, QAbstractButton):
        hint = f" [{widget.objectName()}]"
    chain = []
    node = widget.parent()
    while node is not None and len(chain) < 3:
        chain.append(type(node).__name__)
        node = node.parent()
    return f"{type(widget).__name__}{hint} in {' < '.join(chain) or '-'}"


def check_widget(widget) -> str | None:  # noqa: ANN001
    """What a screen reader or the keyboard would miss in `widget`, or None."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractItemView,
        QComboBox,
        QDoubleSpinBox,
        QLineEdit,
        QPlainTextEdit,
        QSpinBox,
        QTabBar,
        QTableView,
        QTextEdit,
    )

    def named() -> bool:
        return bool(widget.accessibleName().strip())

    parent = widget.parent()
    if isinstance(widget, QAbstractButton):
        if isinstance(parent, (QAbstractItemView, QTabBar)):
            return None  # the corner of a table and the scroll arrows of a tab bar are Qt's
        if widget.isEnabled() and widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
            return f"button the keyboard cannot reach: {_describe(widget)}"
        if not widget.text().strip():
            if not named():
                return f"icon-only button without a name: {_describe(widget)}"
            if not widget.toolTip().strip():
                return f"icon-only button without a tooltip: {_describe(widget)}"
    elif isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
        if isinstance(parent, (QSpinBox, QDoubleSpinBox, QComboBox)):
            return None  # the line edit inside a spin box or a combo box
        if not named() and not widget.toolTip().strip():
            return f"input without a name or a tooltip: {_describe(widget)}"
    elif isinstance(widget, (QTableView, QPlainTextEdit, QTextEdit)):
        if widget.focusPolicy() != Qt.FocusPolicy.NoFocus and not named():
            return f"focusable view without a name: {_describe(widget)}"
    elif type(widget).__name__ in ("PlotWidget", "TimelineWidget") and not named():
        return f"painted widget without a name: {type(widget).__name__}"
    return None


def walk(root, seen: set[int], findings: list[str]) -> None:  # noqa: ANN001
    from PySide6.QtWidgets import QWidget

    for widget in [root, *root.findChildren(QWidget)]:
        if id(widget) in seen or not widget.isVisibleTo(root):
            continue
        seen.add(id(widget))
        finding = check_widget(widget)
        if finding:
            findings.append(finding)


def audit(window) -> list[str]:  # noqa: ANN001
    """The pages of the window, every area and every page of an area."""
    from PySide6.QtWidgets import QApplication

    findings: list[str] = []
    seen: set[int] = set()
    work = Path(tempfile.mkdtemp(prefix="sbs-access-"))
    try:
        shutil.copytree(ROOT / "examples" / "microsat_250kg_eps", work / "p")
        window.open_project(work / "p")
        QApplication.processEvents()
        for index in range(window.workspace.count()):
            window.workspace.setCurrentIndex(index)
            QApplication.processEvents()
            page = window.workspace.widget(index)
            if hasattr(page, "count") and hasattr(page, "setCurrentIndex"):
                for sub in range(page.count()):
                    page.setCurrentIndex(sub)
                    QApplication.processEvents()
                    walk(window, seen, findings)
            walk(window, seen, findings)
        window.editors.discard_all_changes()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return sorted(set(findings))


def audit_dialogs(window) -> list[str]:  # noqa: ANN001
    """The dialogs and the settings card, which are not pages of the window."""
    from PySide6.QtWidgets import QApplication

    from budget_gui.grid_view import PastePreview
    from budget_gui.guided import GuidedWizard
    from budget_gui.help_view import GuideDialog
    from budget_gui.legend import LegendDialog

    findings: list[str] = []
    dialogs = [
        PastePreview([("Unit / mass_kg", "1.2", "1.4")], 1, window),
        LegendDialog(window),
        GuideDialog(None, window),
        GuidedWizard(Path(tempfile.gettempdir()), window),
        window.show_settings(),
    ]
    for dialog in dialogs:
        dialog.show()
        QApplication.processEvents()
        walk(dialog, set(), findings)
        dialog.close()
    return sorted(set(findings))


def main() -> int:
    from budget_gui.app import create_app
    from budget_gui.main_window import MainWindow

    app = create_app([])
    window = MainWindow()
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    findings = audit(window) + audit_dialogs(window)
    for line in findings:
        print(line)
    print(f"{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
