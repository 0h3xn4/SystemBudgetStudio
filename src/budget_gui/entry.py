"""Reading what the user types into a table cell."""

from __future__ import annotations

import re
from typing import Any

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_DECIMAL_COMMA = re.compile(r"[+-]?\d+,\d+(?:\s+\S.*)?")


def cell_value(text: str) -> Any:
    """A plain decimal number means the canonical unit; anything else (a number with a unit, or
    something that is not a number) goes to the unit parser as text. Python's own float() also
    accepts "1_0", "nan" and "inf", which are not numbers here."""
    stripped = text.strip()
    if _NUMBER.fullmatch(stripped):
        return float(stripped)
    return stripped


def has_decimal_comma(text: str) -> bool:
    """'1,5' or '1,5 W': a decimal comma, which the unit parser does not read."""
    return _DECIMAL_COMMA.fullmatch(text.strip()) is not None
