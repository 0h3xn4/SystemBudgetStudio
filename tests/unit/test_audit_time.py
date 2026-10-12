"""Audit MI-8: zero-padded years, supported range 1950-2100, one time notation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from budget_core.timeutil import (
    MAX_YEAR,
    MIN_YEAR,
    end_in_range,
    format_utc,
    normalise_utc,
    parse_utc,
)


def test_years_are_always_four_digits() -> None:
    assert format_utc(datetime(1, 1, 1, tzinfo=UTC)) == "0001-01-01T00:00:00Z"
    assert format_utc(datetime(999, 12, 31, 23, 59, 59, tzinfo=UTC)) == "0999-12-31T23:59:59Z"
    assert format_utc(datetime(2026, 1, 2, 3, 4, 5, 250000, tzinfo=UTC)) == (
        "2026-01-02T03:04:05.25Z"
    )


@pytest.mark.parametrize("text", ["0001-01-01T00:00:00Z", "1949-12-31T23:59:59Z", "2101-01-01Z"])
def test_years_outside_the_supported_range_are_refused(text: str) -> None:
    with pytest.raises(ValueError, match="between 1950 and 2100"):
        parse_utc(text)
    with pytest.raises(ValueError):
        normalise_utc(text)


def test_the_range_edges_are_inclusive() -> None:
    assert normalise_utc("1950-01-01T00:00:00Z") == "1950-01-01T00:00:00Z"
    assert normalise_utc("2100-12-31T23:59:59Z") == "2100-12-31T23:59:59Z"
    assert (MIN_YEAR, MAX_YEAR) == (1950, 2100)


@pytest.mark.parametrize(
    "text",
    [
        "20260102T030405",
        "2026-W01-1",
        "2026-W01-1T03:04:05",
        "2026-001",
        "٢٠٢٦-01-02T03:04:05Z",
        "2026-01-02T03:04:05+01:00",
        "2026-01-02T03:04:05-0500",
        "tomorrow",
        "",
        "2026-13-01T00:00:00Z",
        "2026-02-30T00:00:00Z",
        "2026-01-02T25:00:00Z",
    ],
)
def test_other_notations_are_refused(text: str) -> None:
    with pytest.raises(ValueError):
        parse_utc(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-01-02T03:04:05Z", "2026-01-02T03:04:05Z"),
        ("2026-01-02 03:04:05", "2026-01-02T03:04:05Z"),
        ("2026-01-02T03:04", "2026-01-02T03:04:00Z"),
        ("2026-01-02", "2026-01-02T00:00:00Z"),
        ("2026-01-02T03:04:05.5z", "2026-01-02T03:04:05.5Z"),
        ("  2026-01-02T03:04:05Z ", "2026-01-02T03:04:05Z"),
    ],
)
def test_the_documented_forms_still_work(text: str, expected: str) -> None:
    assert normalise_utc(text) == expected


def test_offset_message_is_kept() -> None:
    with pytest.raises(ValueError, match="trailing Z"):
        parse_utc("2026-01-02T03:04:05+01:00")


def test_end_in_range() -> None:
    start = parse_utc("2100-12-31T00:00:00Z")
    assert end_in_range(start, 3600.0)
    assert not end_in_range(start, 86400.0 * 2)
    assert not end_in_range(start, 1e300)
    assert end_in_range(parse_utc("2026-01-01T00:00:00Z"), 7 * 86400.0)
