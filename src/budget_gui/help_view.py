"""Help > User guide: the guide rendered inside the window (no browser, no network)."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from budget_core.guide.build import build_guide
from budget_core.guide.html import render_html
from budget_core.model import Project
from budget_gui import theme
from budget_gui.components import Button

STEM = "system-budget-studio-guide"


class GuideDialog(QDialog):
    def __init__(self, project: Project | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("User guide")
        self.resize(*theme.scaled(theme.GUIDE_SIZE))
        self.guide = build_guide(project)
        self.browser = QTextBrowser()
        self.browser.setAccessibleName("User guide")
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._anchor)
        self._page = render_html(self.guide, embed_fonts=False)
        self._show_page()
        theme.manager().changed.connect(self._show_page)
        self.status = QLabel("")
        self.status.setProperty("role", "muted")
        save = Button("Save as HTML and PDF…", icon="download")
        save.clicked.connect(lambda: self._choose_folder())
        row = QHBoxLayout()
        row.setSpacing(theme.gap(2))
        row.addWidget(save)
        row.addWidget(self.status, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*theme.inset(3))
        layout.setSpacing(theme.gap(2))
        layout.addWidget(self.browser, 1)
        layout.addLayout(row)

    def _show_page(self) -> None:
        """The guide in the colours of the theme in use (its own style sheet is for the exported
        file); the reading position stays."""
        css = theme.document_css(theme.tokens())
        bar = self.browser.verticalScrollBar()
        position = bar.value() if bar is not None else 0
        self.browser.setHtml(
            re.sub(
                r"<style>.*?</style>", lambda _m: f"<style>{css}</style>", self._page, flags=re.S
            )
        )
        if bar is not None:
            bar.setValue(position)

    def _anchor(self, url) -> None:  # type: ignore[no-untyped-def]
        if url.hasFragment():  # only in-page links; nothing is ever opened externally
            self.browser.scrollToAnchor(url.fragment())

    def save_to(self, folder: Path) -> list[Path]:
        folder.mkdir(parents=True, exist_ok=True)
        html = folder / f"{STEM}.html"
        html.write_text(render_html(self.guide), encoding="utf-8", newline="\n")
        # Imported here, not at module level: ReportLab pulls in networking modules (never used).
        from budget_core.guide.pdf import render_pdf

        pdf = folder / f"{STEM}.pdf"
        pdf.write_bytes(render_pdf(self.guide))
        self.status.setText(f"Saved {html.name} and {pdf.name}.")
        return [html, pdf]

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the guide to folder")
        if folder:
            try:
                self.save_to(Path(folder))
            except OSError:
                self.status.setText("The guide could not be saved. Check the folder.")
