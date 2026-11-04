"""The value formats of the IDM-CIC model file are parsed explicitly (D-237)."""

from __future__ import annotations

from datetime import datetime

import pytest

from budget_core.idm.values import IdmValueError, parse_bool, parse_datetime, parse_float


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("15,54", 15.54),
        ("0,1554E3", 155.4),
        ("1554E-2", 15.54),
        ("-0,5", -0.5),
        ("+2", 2.0),
        ("7", 7.0),
        (",5", 0.5),
        ("  3,25  ", 3.25),
        ("1,5e1", 15.0),
    ],
)
def test_numbers_with_a_comma_and_an_exponent(text: str, value: float) -> None:
    assert parse_float(text) == pytest.approx(value, rel=1e-15)


@pytest.mark.parametrize(
    "text",
    ["", "1.5", "1,234.5", "1 234,5", "1,2,3", "nan", "inf", "1e999", "1,5E", "abc", "--1", "0x10"],
)
def test_other_forms_are_refused_never_guessed(text: str) -> None:
    with pytest.raises(IdmValueError):
        parse_float(text)


def test_refusal_does_not_echo_the_text() -> None:
    with pytest.raises(IdmValueError) as info:
        parse_float("secret-1.5")
    assert "secret" not in str(info.value)


def test_yes_no_values() -> None:
    assert parse_bool("True") is True
    assert parse_bool("False") is False
    assert parse_bool(" true ") is True
    with pytest.raises(IdmValueError):
        parse_bool("1")


def test_dates_are_day_month_year() -> None:
    assert parse_datetime("06/09/2023 08:38:12") == datetime(2023, 9, 6, 8, 38, 12)
    assert parse_datetime("31/12/1999 23:59:59") == datetime(1999, 12, 31, 23, 59, 59)


@pytest.mark.parametrize(
    "text", ["2023-09-06 08:38:12", "32/01/2023 00:00:00", "06/13/2023 00:00:00", "06/09/2023", ""]
)
def test_other_dates_are_refused(text: str) -> None:
    with pytest.raises(IdmValueError):
        parse_datetime(text)
