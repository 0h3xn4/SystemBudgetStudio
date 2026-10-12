"""Number text for reports: one rule for every format.

A number is rounded half up (ties away from zero) on its shortest decimal representation, which
is what a spreadsheet shows for the same cell: 0.125 is 0.13, and 2.675 is 2.68 although the binary
value is slightly below. Negative zero never appears: a value that rounds to zero is written
without a sign. A negative number that shows as zero is a rounding artefact, not a result.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Context, Decimal
from numbers import Integral
from typing import Any

_CONTEXT = Context(prec=450, rounding=ROUND_HALF_UP)  # a double has at most 309 integer digits
GENERAL_DIGITS = 10  # significant digits of a "general" column


def exact(value: float) -> Decimal:
    """The shortest decimal representation of `value` (what a person reads off the number)."""
    return _decimal(value)


def signed_change(a: float, b: float, decimals: int, scale: int = 0) -> str:
    """`b - a` (times 10^scale) with a sign and `decimals` places, from the exact decimal values.
    A change that would show as zero is written with its significant digits instead of hiding."""
    delta = _CONTEXT.subtract(_decimal(b), _decimal(a)).scaleb(scale, context=_CONTEXT)
    return _signed(delta, decimals)


def relative_percent(a: float, b: float, decimals: int = 1) -> str:
    """The change from `a` to `b` in percent of |a| (signed); empty when `a` is zero."""
    if a == 0.0:
        return ""
    ratio = _CONTEXT.divide(_CONTEXT.subtract(_decimal(b), _decimal(a)), abs(_decimal(a)))
    return _signed(ratio.scaleb(2, context=_CONTEXT), decimals)


def _signed(delta: Decimal, decimals: int) -> str:
    sign = "-" if delta < 0 else "+"
    text = _fixed(abs(delta), decimals)
    if delta != 0 and not Decimal(text):
        text = f"{abs(float(delta)):.{GENERAL_DIGITS}g}"
    return sign + text


def _decimal(value: float) -> Decimal:
    if isinstance(value, Integral):
        return Decimal(int(value))
    return Decimal(repr(float(value)))  # also for numpy floats, whose repr is not a number


def fixed(value: float, decimals: int) -> str:
    """`value` with `decimals` places, rounded half up on the decimal value; no negative zero.
    Not finite: an empty string (callers show n/a)."""
    if not math.isfinite(value):
        return ""
    return _fixed(_decimal(value), decimals)


def _fixed(exact: Decimal, decimals: int) -> str:
    places = Decimal(1).scaleb(-decimals)
    rounded = exact.quantize(places, rounding=ROUND_HALF_UP, context=_CONTEXT)
    text = format(rounded, "f")
    return text[1:] if text.startswith("-") and not rounded else text


def percent(value: float, decimals: int) -> str:
    """`value` x 100 with `decimals` places, rounded on the exact decimal product."""
    if not math.isfinite(value):
        return ""
    return _fixed(_decimal(value).scaleb(2, context=_CONTEXT), decimals)


def general(value: float) -> str:
    """At most GENERAL_DIGITS significant digits, no trailing zeros ('-0.00041234', '3e-09')."""
    if not math.isfinite(value):
        return ""
    text = f"{value:.{GENERAL_DIGITS}g}"
    return "0" if float(text) == 0.0 else text


def no_negative_zero(value: float) -> float:
    return value + 0.0 if value == 0.0 else value


def clean_numbers(data: Any) -> Any:
    """`data` (nested dicts, lists, tuples) with every -0.0 replaced by 0.0, for JSON text."""
    if isinstance(data, float):
        return no_negative_zero(data)
    if isinstance(data, dict):
        return {k: clean_numbers(v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [clean_numbers(v) for v in data]
    return data
