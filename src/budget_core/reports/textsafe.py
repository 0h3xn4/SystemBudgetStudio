"""Remove characters that XML-based formats (XLSX, DOCX) cannot hold from every string of a
report document, so project text such as a name with a control character cannot crash a renderer.
The same walk applies any other text function (the PDF renderer replaces characters its font
lacks)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace

from budget_core.provenance import Provenance
from budget_core.reports.document import Cell, Figure, ReportDocument, Section, Table

_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")

TextFunction = Callable[[str], str]


def xml_safe(text: str) -> str:
    return _ILLEGAL.sub("", text)


def _cell(value: Cell, fn: TextFunction) -> Cell:
    return fn(value) if isinstance(value, str) else value


def _table(table: Table, fn: TextFunction) -> Table:
    columns = tuple(replace(c, header=fn(c.header), unit=fn(c.unit)) for c in table.columns)
    rows = tuple(tuple(_cell(v, fn) for v in row) for row in table.rows)
    return replace(table, title=fn(table.title), columns=columns, rows=rows, note=fn(table.note))


def _figure(figure: Figure, fn: TextFunction) -> Figure:
    return replace(figure, title=fn(figure.title), alt=fn(figure.alt))


def _section(section: Section, fn: TextFunction) -> Section:
    return replace(
        section,
        title=fn(section.title),
        sheet_name=xml_safe(section.sheet_name),
        paragraphs=tuple(fn(p) for p in section.paragraphs),
        tables=tuple(_table(t, fn) for t in section.tables),
        figures=tuple(_figure(f, fn) for f in section.figures),
    )


def _provenance(prov: Provenance, fn: TextFunction) -> Provenance:
    return replace(
        prov,
        tool=fn(prov.tool),
        tool_version=fn(prov.tool_version),
        project_name=fn(prov.project_name),
        project_revision=fn(prov.project_revision),
        scenario=fn(prov.scenario),
        user=fn(prov.user),
    )


def clean_document(doc: ReportDocument, fn: TextFunction = xml_safe) -> ReportDocument:
    """`doc` with `fn` applied to every string (default: remove characters XML cannot hold)."""
    return replace(
        doc,
        title=fn(doc.title),
        provenance=_provenance(doc.provenance, fn),
        sections=tuple(_section(s, fn) for s in doc.sections),
        banner=fn(doc.banner),
    )
