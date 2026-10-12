"""Neutral report model: every renderer (XLSX, PDF, later DOCX) draws the same document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from budget_core.provenance import Provenance
from budget_core.reports import numfmt

Cell = str | float | None  # None renders as "n/a"
ColumnKind = Literal["text", "number", "percent"]
NA = "n/a"


@dataclass(frozen=True)
class Column:
    """`decimals` is the number of places shown; a negative value means "general": up to ten
    significant digits, nothing lost (configuration numbers)."""

    header: str
    kind: ColumnKind = "text"
    decimals: int = 3
    unit: str = ""


@dataclass(frozen=True)
class Table:
    title: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...]
    note: str = ""
    emphasise_last_row: bool = False
    # Columns that identify a row (a comparison pairs rows by them): the first column unless the
    # first column repeats, as the link id does when a link has several points.
    key_columns: tuple[int, ...] = (0,)


@dataclass(frozen=True)
class Figure:
    """A picture (PNG bytes) with a title; `alt` describes it for readers who cannot see it."""

    title: str
    png: bytes
    alt: str = ""


@dataclass(frozen=True)
class Section:
    title: str
    sheet_name: str  # short unique name for spreadsheet tabs (max 31 characters)
    paragraphs: tuple[str, ...] = ()
    tables: tuple[Table, ...] = ()
    figures: tuple[Figure, ...] = ()


@dataclass(frozen=True)
class ReportDocument:
    title: str
    provenance: Provenance
    sections: tuple[Section, ...] = field(default_factory=tuple)
    banner: str = ""  # shown first when results are incomplete


def format_cell(value: Cell, column: Column) -> str:
    """The text of a cell in every format. Numbers are rounded half up on their decimal value (as
    a spreadsheet shows them), never show a negative zero, and a number that is not finite is
    n/a."""
    if value is None:
        return NA
    if isinstance(value, str):
        return value
    if column.kind == "percent":
        text = numfmt.percent(value, max(column.decimals - 2, 0))
        return f"{text} %" if text else NA
    text = numfmt.general(value) if column.decimals < 0 else numfmt.fixed(value, column.decimals)
    return text or NA
