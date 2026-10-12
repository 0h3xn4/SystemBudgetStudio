"""CSV writing that cannot be turned into a formula when opened in a spreadsheet."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from budget_core.provenance import Provenance

DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")
# After a leading "+" or "-", plain words ("-Müller", "+Anna-Lisa Smith") cannot run anything in a
# spreadsheet: a formula needs a digit, a bracket, an operator or a reference separator.
_PLAIN_WORDS = re.compile(r"^[+-][^\W\d_][\w \-.]*$")
# "-0.5", "+3", "1e-9", and a number with a short unit as the tool writes it: "+2.500 W", "+20.0 %"
_NUMBER = re.compile(
    r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?(?: ?[A-Za-z%][A-Za-z%/^0-9.]{0,11})?$"
)


def _is_number(text: str) -> bool:
    return _NUMBER.match(text) is not None


def defuse(value: Any) -> Any:
    """Prefix text that a spreadsheet would run as a formula with one apostrophe and change nothing
    else. Text is prefixed when it starts with "=", "@", a tab or a carriage return, or with "+" or
    "-" unless that is a number ("-0.5", "+3", "1e-9", "+2.500 W") or plain words ("-Müller"). A
    value that starts with anything else, including every provenance item the tool writes itself,
    is never changed."""
    if (
        isinstance(value, str)
        and value.startswith(DANGEROUS_START)
        and not _is_number(value)
        and not (value[0] in "+-" and _PLAIN_WORDS.match(value))
    ):
        return "'" + value
    return value


class _Writer:
    def __init__(self, handle: Any) -> None:
        self._writer = csv.writer(handle, lineterminator="\n")

    def writerow(self, row: Iterable[Any]) -> None:
        self._writer.writerow([defuse(v) for v in row])

    def writerows(self, rows: Iterable[Iterable[Any]]) -> None:
        for row in rows:
            self.writerow(row)


def csv_field(value: Any) -> str:
    """One value as it would be written in a CSV row: defused, and quoted when it holds a comma, a
    quote or a line break (for files that are assembled row by row for speed)."""
    handle = io.StringIO()
    csv_writer(handle).writerow([value])
    return handle.getvalue()[:-1]  # the line terminator


def csv_writer(handle: Any) -> _Writer:
    return _Writer(handle)


def provenance_csv(provenance: Provenance, *, incomplete: bool | None = None) -> str:
    """The provenance block as a two-column CSV (`item,value`), written beside every set of CSV
    files, which have no room for a header block of their own. `incomplete` (when known) adds the
    row `Incomplete` with `yes` or `no`: the report carries the INCOMPLETE banner."""
    handle = io.StringIO()
    writer = csv_writer(handle)
    writer.writerow(["item", "value"])
    writer.writerows(provenance.rows())
    if incomplete is not None:
        writer.writerow(["Incomplete", "yes" if incomplete else "no"])
    return handle.getvalue()
