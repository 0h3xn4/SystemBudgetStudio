"""Show every component and every token of the window, in both themes.

    QT_QPA_PLATFORM=offscreen python scripts/ui_gallery.py docs/ui/screenshots/m1

writes `gallery-light.png` and `gallery-dark.png` into the folder. Without an argument the gallery
opens in a window (for a developer's screen). The same `build_gallery` is used by the tests, so a
component that cannot be built in a theme fails a test, not only this script.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from budget_gui import theme
from budget_gui.app import create_app
from budget_gui.components import (
    Button,
    Card,
    EmptyState,
    KeyValueList,
    SectionHeader,
    SegmentedControl,
    StatusBadge,
    Toast,
    icon_button,
)
from budget_gui.theme import Level


def _row(*widgets: QWidget) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(theme.gap(1))
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return holder


class _Swatch(QWidget):
    """A square of one colour; painted, because the style sheet gives every widget a background."""

    def __init__(self, colour: str) -> None:
        super().__init__()
        self._colour = QColor(colour)
        self.setFixedSize(theme.px(theme.SPACE[5]), theme.px(theme.SPACE[4]))

    def paintEvent(self, _event: object) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setPen(QColor(theme.tokens().border_strong))
        painter.setBrush(self._colour)
        painter.drawRoundedRect(
            self.rect().adjusted(0, 0, -1, -1), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL
        )


def _swatches(names: list[tuple[str, str]]) -> QWidget:
    holder = QWidget()
    grid = QGridLayout(holder)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(theme.gap(0))
    for i, (name, colour) in enumerate(names):
        chip = _Swatch(colour)
        chip.setToolTip(f"{name} {colour}")
        label = QLabel(name)
        label.setProperty("role", "caption")
        grid.addWidget(chip, 0, i)
        grid.addWidget(label, 1, i)
    return holder


def build_gallery() -> QWidget:
    """A page with every component, the type scale and the token swatches of the theme in use."""
    t = theme.tokens()
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(*theme.inset(3))
    layout.setSpacing(theme.gap(3))

    heading = QLabel(f"Gallery: {t.name} theme, UI scale {theme.scale_percent()} %")
    heading.setProperty("role", "heading")
    layout.addWidget(heading)

    layout.addWidget(SectionHeader("Type"))
    for role, text in (
        ("display", "Display 22"),
        ("heading", "Page title 18"),
        ("title", "Section title 15"),
        (None, "Body 13: the quick brown fox jumps over the lazy dog 0123456789"),
        ("small", "Small and table 12"),
        ("caption", "Caption 11"),
    ):
        label = QLabel(text)
        if role:
            label.setProperty("role", role)
        layout.addWidget(label)
    mono = QLabel("JetBrains Mono: 1 234.567 kg  -0.0185 m  0x1F  mass_kg")
    mono.setFont(theme.mono_font())
    layout.addWidget(mono)

    layout.addWidget(SectionHeader("Buttons"))
    disabled = Button("Disabled", "secondary")
    disabled.setEnabled(False)
    layout.addWidget(
        _row(
            Button("Primary", "primary", icon="play"),
            Button("Secondary", "secondary"),
            Button("Ghost", "ghost"),
            Button("Danger", "danger", icon="trash-2"),
            disabled,
            Button("Compact", "secondary", compact=True),
            icon_button("search", "Find", shortcut="Ctrl+K"),
        )
    )

    layout.addWidget(SectionHeader("Inputs"))
    field = QLineEdit("one_day")
    combo = QComboBox()
    combo.addItems(["nominal", "imaging", "downlink"])
    check = QCheckBox("Shade eclipses")
    check.setChecked(True)
    segmented = SegmentedControl([("bol", "BOL"), ("eol", "EOL")])
    layout.addWidget(_row(field, combo, check, segmented))

    layout.addWidget(SectionHeader("Status (an icon and a word, never colour alone)"))
    layout.addWidget(
        _row(*(StatusBadge(level, level.value.capitalize()) for level in Level)),
    )

    layout.addWidget(SectionHeader("Card, key and value, progress"))
    card = Card()
    pairs = KeyValueList()
    pairs.set_items([("Tool", "System Budget Studio"), ("Scenario", "one_day"), ("Steps", "8640")])
    card.body.addWidget(pairs)
    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(60)
    card.body.addWidget(progress)
    layout.addWidget(card)

    layout.addWidget(SectionHeader("Tabs and a table"))
    tabs = QTabWidget()
    table = QTableWidget(3, 3)
    table.setHorizontalHeaderLabels(["Unit", "Mass (kg)", "Margin (kg)"])
    for r, row in enumerate((("adcs", "3.000", "0.450"), ("battery", "14.000", "2.100"))):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
    tabs.addTab(table, "Summary")
    tabs.addTab(QWidget(), "Violations")
    tabs.setMinimumHeight(theme.px(theme.PLOT_MIN_HEIGHT) // 2)
    layout.addWidget(tabs)

    layout.addWidget(SectionHeader("Empty state"))
    layout.addWidget(EmptyState("No violations. Compute the timeline first.", "Compute"))

    layout.addWidget(SectionHeader("Colour tokens"))
    layout.addWidget(
        _swatches(
            [
                ("canvas", t.canvas),
                ("surface", t.surface),
                ("raised", t.raised),
                ("hover", t.hover),
                ("selected", t.selected),
                ("border", t.border_subtle),
                ("strong", t.border_strong),
                ("accent", t.accent),
                ("text", t.text),
                ("secondary", t.text_secondary),
                ("muted", t.text_muted),
            ]
        )
    )
    layout.addWidget(_swatches([(level.value, t.level(level).fg) for level in Level]))
    layout.addWidget(_swatches([(f"s{i}", c) for i, c in enumerate(t.series)]))
    toast = Toast(page)
    page.toast = toast  # type: ignore[attr-defined]
    layout.addStretch(1)
    return page


def main(out: Path | None) -> int:
    app = create_app([])
    for mode in (theme.Mode.LIGHT, theme.Mode.DARK):
        theme.manager().set_mode(mode, app)
        page = build_gallery()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll.resize(1000, 1500)
        scroll.show()
        app.processEvents()
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            page.grab().save(str(out / f"gallery-{mode.value}.png"))
            scroll.close()
    if out is None:
        return app.exec()
    print(f"gallery in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
