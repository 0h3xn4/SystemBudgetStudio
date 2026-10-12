"""PDF renderer (ReportLab, bundled IBM Plex fonts); identical documents give identical bytes."""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import TimeStamp, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import LayoutError

from budget_core.assets import font_path
from budget_core.plots.render import image_size
from budget_core.reports.document import (
    Column,
    Figure,
    ReportDocument,
    banner_headline,
    format_cell,
)
from budget_core.reports.document import Table as DocTable
from budget_core.reports.textsafe import clean_document, xml_safe

# ReportLab can fetch images from URLs (and imports urllib.request/ssl for it, unconditionally).
# This tool never loads remote resources (constraint 1). ReportLab only checks URLs when
# `trustedHosts` is a non-empty list, so set a host that cannot exist (RFC 2606 ".invalid") and
# allow only local file and data schemes.
rl_config.trustedHosts = ["localhost.invalid"]
rl_config.trustedSchemes = ["file", "data"]

REGULAR, BOLD = "IBMPlexSans", "IBMPlexSans-SemiBold"
CELL_LIMIT = 400  # characters in a table cell; a longer text would make a row taller than a page
INK, GREY, RED = colors.HexColor("#161616"), colors.HexColor("#e0e0e0"), colors.HexColor("#da1e28")


def _register_fonts() -> None:
    if REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(REGULAR, str(font_path("IBMPlexSans-Regular.ttf"))))
        pdfmetrics.registerFont(TTFont(BOLD, str(font_path("IBMPlexSans-SemiBold.ttf"))))


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=REGULAR, fontSize=8, leading=10, textColor=INK)
    return {
        "title": ParagraphStyle("title", parent=base, fontName=BOLD, fontSize=16, leading=20),
        "h1": ParagraphStyle(
            "h1", parent=base, fontName=BOLD, fontSize=12, leading=15, spaceBefore=8
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName=BOLD, fontSize=9, leading=12, spaceBefore=6
        ),
        "banner": ParagraphStyle("banner", parent=base, fontName=BOLD, textColor=RED, fontSize=9),
        "cell": base,
        "cell_right": ParagraphStyle("cell_right", parent=base, alignment=TA_RIGHT),
        "head": ParagraphStyle("head", parent=base, fontName=BOLD),
        "note": ParagraphStyle("note", parent=base, textColor=colors.HexColor("#525252")),
    }


def _col_widths(table: DocTable, total: float) -> list[float]:
    weights = []
    for i, column in enumerate(table.columns):
        longest = max(
            [len(column.header) // 2 + 1] + [len(format_cell(r[i], column)) for r in table.rows]
        )
        weights.append(float(min(max(longest, 6), 48)))
    scale = total / sum(weights)
    widths = [w * scale for w in weights]
    # a header word that does not fit would be broken in the middle ("Subsyste/m"): widen that
    # column at the expense of the others
    needed = [
        max((pdfmetrics.stringWidth(w, BOLD, 8) for w in c.header.split()), default=0.0) + 14.0
        for c in table.columns
    ]
    deficit = sum(max(n - w, 0.0) for n, w in zip(needed, widths, strict=True))
    if deficit > 0.0:
        spare = sum(max(w - n, 0.0) for n, w in zip(needed, widths, strict=True))
        give = min(deficit / spare, 1.0) if spare > 0.0 else 0.0
        widths = [
            max(n, w) if w < n else w - (w - n) * give for n, w in zip(needed, widths, strict=True)
        ]
    return widths


def _flowable(table: DocTable, styles: dict[str, ParagraphStyle], width: float) -> list[object]:
    def style_for(column: Column) -> ParagraphStyle:
        return styles["cell"] if column.kind == "text" else styles["cell_right"]

    head = [Paragraph(escape(c.header), styles["head"]) for c in table.columns]
    data: list[list[Paragraph]] = [head]
    for values in table.rows:
        data.append(
            [
                Paragraph(escape(format_cell(v, c)), style_for(c))
                for v, c in zip(values, table.columns, strict=True)
            ]
        )
    t = Table(data, colWidths=_col_widths(table, width), repeatRows=1)
    commands: list[tuple[object, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), GREY),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#c6c6c6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if table.emphasise_last_row and table.rows:
        commands.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f4f4f4")))
    t.setStyle(TableStyle(commands))
    out: list[object] = [Paragraph(escape(table.title), styles["h2"]), t]
    if table.note:
        out.append(Paragraph(escape(table.note), styles["note"]))
    out.append(Spacer(1, 4 * mm))
    return out


def _figure_flowable(
    figure: Figure,
    styles: dict[str, ParagraphStyle],
    width: float,
    height: float,
    lead: list[object],
) -> list[object]:
    w_px, h_px = image_size(figure.png)
    scale = min(width / w_px, (height - 12 * mm) / h_px)
    image = Image(io.BytesIO(figure.png), width=w_px * scale, height=h_px * scale)
    parts: list[object] = [*lead, Paragraph(escape(figure.title), styles["h2"]), image]
    if figure.alt:
        parts.append(Paragraph(escape(figure.alt), styles["note"]))
    return [KeepTogether(parts), Spacer(1, 4 * mm)]


def _timestamp(generated: str) -> TimeStamp:
    """ReportLab's time stamp object for the provenance time (UTC); `invariant=1` alone would give
    every PDF the date 2000-01-01."""
    moment = datetime.strptime(generated, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    stamp = TimeStamp(invariant=True)
    stamp.t = moment.timestamp()
    stamp.lt = moment.timetuple()
    stamp.YMDhms = tuple(stamp.lt)[:6]
    stamp.dhh = stamp.dmm = 0
    return stamp


def _footer_lines(footer: str, width: float) -> list[str]:
    """The footer in at most two lines that fit `width` (a long project name or user name wraps,
    and what still does not fit ends in an ellipsis), clear of the page number."""
    lines: list[str] = simpleSplit(footer, REGULAR, 7, width)
    if len(lines) > 2:
        lines = [lines[0], lines[1].rstrip() + "…"]
    clipped = []
    for line in lines:  # a word without spaces can still be wider than the line
        while pdfmetrics.stringWidth(line, REGULAR, 7) > width and len(line) > 1:
            line = line[:-2] + "…"
        clipped.append(line)
    return clipped


def _supported(text: str, glyphs: set[int]) -> tuple[str, int]:
    """`text` with every character the PDF fonts lack replaced by '?', and how many were."""
    out, missing = [], 0
    for ch in text:
        if ch.isspace() or ord(ch) in glyphs:
            out.append(ch)
        else:
            out.append("?")
            missing += 1
    return "".join(out), missing


def _prepare(doc: ReportDocument, cell_limit: int) -> tuple[ReportDocument, list[str]]:
    """The document as the PDF can show it, and the notes that say what was changed: characters
    the font lacks become '?', and a table cell above `cell_limit` characters is shortened (a
    row taller than a page cannot be laid out)."""
    glyphs = set(pdfmetrics.getFont(REGULAR).face.charToGlyph) & set(
        pdfmetrics.getFont(BOLD).face.charToGlyph
    )
    counts = {"glyphs": 0, "cells": 0}

    def text(value: str) -> str:
        shown, missing = _supported(xml_safe(value), glyphs)
        counts["glyphs"] += missing
        return shown

    cleaned = clean_document(doc, text)

    def shorten(table: DocTable) -> DocTable:
        rows = []
        for row in table.rows:
            new = []
            for value in row:
                if isinstance(value, str) and len(value) > cell_limit:
                    value = value[: cell_limit - 3] + "..."
                    counts["cells"] += 1
                new.append(value)
            rows.append(tuple(new))
        return replace(table, rows=tuple(rows))

    cleaned = replace(
        cleaned,
        sections=tuple(
            replace(s, tables=tuple(shorten(t) for t in s.tables)) for s in cleaned.sections
        ),
    )
    notes = []
    if counts["glyphs"]:
        notes.append(
            f"{counts['glyphs']} character(s) are not available in the PDF font and are shown as "
            "'?'. The XLSX, DOCX and JSON files hold the original text."
        )
    if counts["cells"]:
        notes.append(
            f"{counts['cells']} table cell(s) were shortened because they are longer than a page "
            "can hold. The XLSX, DOCX and JSON files hold the full text."
        )
    return cleaned, notes


def render_pdf(doc: ReportDocument) -> bytes:
    _register_fonts()
    try:
        return _render(*_prepare(doc, CELL_LIMIT))
    except LayoutError:  # many long cells in one row: shorten harder
        return _render(*_prepare(doc, 60))


def _render(doc: ReportDocument, notes: list[str]) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    page = landscape(A4)
    margin = 12 * mm
    prov = doc.provenance
    template = SimpleDocTemplate(
        buffer,
        pagesize=page,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=16 * mm,
        title=doc.title,
        author=prov.user,
        subject=prov.project_name,
        creator=f"{prov.tool} {prov.tool_version}",
        invariant=1,
    )
    width = page[0] - 2 * margin
    story: list[object] = [Paragraph(escape(doc.title), styles["title"])]
    if doc.banner:
        story += [Spacer(1, 2 * mm), Paragraph(escape(doc.banner), styles["banner"])]
    story += [Paragraph(escape(n), styles["note"]) for n in notes]
    for section in doc.sections:
        lead: list[object] = [Paragraph(escape(section.title), styles["h1"])]
        lead += [Paragraph(escape(t), styles["cell"]) for t in section.paragraphs]
        if section.tables or not section.figures:
            story += lead
            lead = []
        for table in section.tables:
            story += _flowable(table, styles, width)
        for figure in section.figures:
            height = page[1] - margin - 16 * mm - 14 * mm
            story += _figure_flowable(figure, styles, width, height, lead)
            lead = []

    footer = (
        f"{prov.tool} {prov.tool_version} | {prov.project_name} rev {prov.project_revision} | "
        f"{prov.scenario} | {prov.generated} | {prov.user}"
    )

    stamp = _timestamp(prov.generated)

    footer_lines = _footer_lines(footer, page[0] - 2 * margin - 30 * mm)
    headline = banner_headline(doc.banner)

    def draw(canvas, d) -> None:  # type: ignore[no-untyped-def]
        canvas._doc._timeStamp = stamp  # the document dates (creation, modification) are ours
        canvas.saveState()
        if headline:  # every page says the report is incomplete, not only the first
            canvas.setFont(BOLD, 7)
            canvas.setFillColor(RED)
            canvas.drawString(margin, page[1] - 7 * mm, headline)
        canvas.setFont(REGULAR, 7)
        canvas.setFillColor(colors.HexColor("#525252"))
        for i, line in enumerate(footer_lines):
            canvas.drawString(margin, 8 * mm + (len(footer_lines) - 1 - i) * 3.2 * mm, line)
        canvas.drawRightString(page[0] - margin, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    template.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()
