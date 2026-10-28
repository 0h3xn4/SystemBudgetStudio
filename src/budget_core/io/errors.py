"""Translate pydantic validation errors into located, plain-language Problems.

Messages say what is wrong, where and what to do. They never include values from the file
(only field names, units and allowed names), see spec constraints 11 and 20.
"""

from __future__ import annotations

import difflib
import types
import typing
from typing import Any

from pydantic import BaseModel, ValidationError

from budget_core.io.yamlio import LineMap, Path, format_path
from budget_core.problems import Problem, Severity
from budget_core.units.quantity import canonical_unit


def _unwrap(tp: Any) -> Any:
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        return _unwrap(args[0]) if args else tp
    if origin in (list, dict):
        return tp
    return tp


def _model_at(root: type[BaseModel], loc: Path) -> type[BaseModel] | None:
    """The model class that owns the mapping found at `loc` (used for field suggestions)."""
    current: Any = root
    for part in loc:
        current = _unwrap(current)
        origin = typing.get_origin(current)
        if origin is list and isinstance(part, int):
            current = typing.get_args(current)[0]
        elif origin is dict:
            current = typing.get_args(current)[1]
        elif isinstance(current, type) and issubclass(current, BaseModel) and isinstance(part, str):
            fld = current.model_fields.get(part)
            if fld is None:
                return None
            current = fld.annotation
        else:
            return None
    current = _unwrap(current)
    return current if isinstance(current, type) and issubclass(current, BaseModel) else None


def _unit_hint(name: str) -> str:
    unit = canonical_unit(name)
    return (
        f"Write a number in {unit}, or a value with a unit (for example '2.5 {unit}')."
        if unit
        else ""
    )


_NUMBER_KINDS = frozenset(
    {
        "float_parsing",
        "float_type",
        "int_parsing",
        "int_type",
        "int_from_float",
        "decimal_parsing",
        "decimal_type",
        "finite_number",
    }
)
_RANGE_KINDS = frozenset(
    {"greater_than", "greater_than_equal", "less_than", "less_than_equal", "multiple_of"}
)


def _field_hint(kind: str, name: str) -> str:
    """What to do about an invalid field, by the kind of the failure. Only a field that must be a
    number gets the advice to write a number; the other kinds are explained by the message."""
    unit = canonical_unit(name)
    if kind in _NUMBER_KINDS:
        return _unit_hint(name) or "Write a number."
    if kind in _RANGE_KINDS:
        return "The allowed range is in the message." + (
            f" A bare number is in {unit}." if unit else ""
        )
    if kind in ("literal_error", "enum"):
        return "Use one of the values the message lists."
    return ""


def explain(
    exc: ValidationError,
    root: type[BaseModel],
    file: str,
    lines: LineMap,
) -> list[Problem]:
    problems: list[Problem] = []
    for err in exc.errors(include_url=False, include_context=True, include_input=False):
        loc: Path = tuple(err["loc"])
        ctx: dict[str, Any] = err.get("ctx") or {}
        kind = err["type"]
        if "field" in ctx:
            loc = loc + (str(ctx["field"]),)
        name = str(loc[-1]) if loc and isinstance(loc[-1], str) else ""
        code, message, hint = "FIELD_INVALID", str(err["msg"]), _field_hint(kind, name)

        if kind == "missing":
            code = "FIELD_MISSING"
            message = f"Required field '{name}' is missing."
            unit = canonical_unit(name)
            hint = f"Add '{name}: <value>'" + (f" (unit: {unit})." if unit else ".")
        elif kind == "extra_forbidden":
            code = "FIELD_UNKNOWN"
            message = f"Unknown field '{name}'."
            owner = _model_at(root, loc[:-1])
            allowed = sorted(owner.model_fields) if owner else []
            close = difflib.get_close_matches(name, allowed, n=1)
            if close:
                hint = f"Did you mean '{close[0]}'?"
            elif allowed:
                hint = "Allowed fields: " + ", ".join(allowed) + "."
        elif kind == "unit_invalid":
            code = "UNIT_INVALID"
            message = f"Field '{name}': {err['msg']}."
        elif kind == "duplicate_name":
            code = "DUPLICATE_NAME"
            hint = "Rename one of the entries."
        elif kind == "string_too_short" and name == "source":
            code = "SOURCE_MISSING"
            message = "Every configuration number needs a non-empty 'source'."
            hint = "Cite the standard or data sheet, or write 'TBD' to mark a placeholder."
        elif kind in ("peak_below_average", "duration_order"):
            message = f"Field '{name}': {err['msg']}."
        elif kind in ("value_error", "assertion_error"):
            # raised by a plain ValueError or assert inside a validator: its text may quote the
            # offending value (int('x') says so), and that value comes from the file
            message = (
                f"Field '{name}' has a value that cannot be used."
                if name
                else "A value cannot be used."
            )
            hint = hint or "Check the value, its unit and its format against the documentation."

        problems.append(
            Problem(
                Severity.ERROR,
                code,
                message,
                file=file,
                path=format_path(loc),
                line=lines.lookup(loc),
                hint=hint,
            )
        )
    return problems
