"""UTC time strings: ISO 8601 without a UTC offset other than Z (project files use UTC only).

Times are accepted between the years 1950 and 2100 (decision D-103): the Sun and Earth models and
the TLE epoch convention are meant for that range, and a year outside it only ever came from a typo.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

MIN_YEAR = 1950
MAX_YEAR = 2100

# The extended ISO form only: 2026-01-02, 2026-01-02T03:04, 2026-01-02T03:04:05.25Z. The basic
# form (20260102T030405), week dates (2026-W01-1) and non-ASCII digits are not times of this tool.
_FORM = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?)?"
    r"([Zz])?$",
    re.ASCII,
)


def check_range(moment: datetime) -> datetime:
    """`moment` itself when its year is within the supported range, else ValueError."""
    if not MIN_YEAR <= moment.year <= MAX_YEAR:
        raise ValueError(f"the year must be between {MIN_YEAR} and {MAX_YEAR}")
    return moment


def end_in_range(start: datetime, duration_s: float) -> bool:
    """True when `start` plus `duration_s` stays inside the supported years (and does not
    overflow): a scenario that would end in the year 40000 cannot be written out."""
    try:
        end = start + timedelta(seconds=duration_s)
    except (OverflowError, ValueError):
        return False
    return MIN_YEAR <= end.year <= MAX_YEAR


def parse_utc(text: str) -> datetime:
    """Parse "2026-01-02T03:04:05Z" (also with a space instead of T, or fractional seconds)."""
    cleaned = text.strip()
    match = _FORM.match(cleaned)
    if match is None:
        try:
            parsed_other = datetime.fromisoformat(cleaned)
        except ValueError:
            parsed_other = None
        if parsed_other is not None and parsed_other.tzinfo is not None:
            raise ValueError("times are UTC; write them with a trailing Z and no offset")
        if re.search(r"[0-9][+-][0-9]{2}(?::?[0-9]{2})?$", cleaned):
            raise ValueError("times are UTC; write them with a trailing Z and no offset")
        raise ValueError("expected a UTC time such as 2026-01-02T03:04:05Z")
    year, month, day, hour, minute, second, fraction, _z = match.groups()
    try:
        parsed = datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            int((fraction or "0").ljust(6, "0")[:6]),
            tzinfo=UTC,
        )
    except ValueError:
        raise ValueError("expected a UTC time such as 2026-01-02T03:04:05Z") from None
    return check_range(parsed)


def format_utc(moment: datetime) -> str:
    utc = moment.astimezone(UTC)
    # strftime("%Y") is not zero-padded on every platform: year 1 would print as "1"
    text = (
        f"{utc.year:04d}-{utc.month:02d}-{utc.day:02d}T"
        f"{utc.hour:02d}:{utc.minute:02d}:{utc.second:02d}"
    )
    if utc.microsecond:
        text += f".{utc.microsecond:06d}".rstrip("0")
    return text + "Z"


def normalise_utc(text: str) -> str:
    return format_utc(parse_utc(text))
