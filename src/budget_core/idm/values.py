"""Explicit parsing of the three value formats of the model file (no locale, no guessing).

Numbers use a comma as the decimal separator and may carry an exponent (`15,54`, `0,1554E3`,
`1554E-2`); there is no thousands separator. Dates are `dd/mm/yyyy hh:mm:ss`. A yes/no value is
`True` or `False`. Anything else is refused, so a dot decimal or a thousands separator can never
be misread as a different number.
"""

from __future__ import annotations

import math
import re
from datetime import datetime

_NUMBER = re.compile(r"[+-]?(?:\d+(?:,\d*)?|,\d+)(?:[eE][+-]?\d+)?")
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})")


class IdmValueError(ValueError):
    """A value is not in the format of the model file. The text is not echoed."""


def parse_float(text: str) -> float:
    cleaned = text.strip()
    if not _NUMBER.fullmatch(cleaned):
        raise IdmValueError("number")
    value = float(cleaned.replace(",", "."))
    if not math.isfinite(value):
        raise IdmValueError("number")
    return value


def parse_bool(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise IdmValueError("yes/no value")


def parse_datetime(text: str) -> datetime:
    match = _DATE.fullmatch(text.strip())
    if match is None:
        raise IdmValueError("date")
    day, month, year, hour, minute, second = (int(g) for g in match.groups())
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        raise IdmValueError("date") from None
