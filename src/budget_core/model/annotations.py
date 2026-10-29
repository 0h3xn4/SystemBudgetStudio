"""Where a plain input came from: the `provenance:` mapping of an entity file (D-213).

A number in `config/` carries its own `source`. A plain input (a mass, a power, an orbit element)
does not change shape; the file may instead hold a `provenance:` mapping from the path of the
input to its source. It is read and carried, never used by an equation, and it is not part of the
model digest.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, NamedTuple

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from budget_core.model.base import BudgetModel

InputStatus = Literal["sourced", "estimate", "illustrative", "tbd"]
INPUT_STATUSES: tuple[str, ...] = ("sourced", "estimate", "illustrative", "tbd")

DEFAULT_KEY = "*"  # applies to every plain input of the file that has no entry of its own

_SEGMENT = r"[^.\[\]\s][^.\[\]]*(?:\[[^\[\]\s][^\[\]]*\])*"
_PATH = re.compile(rf"{_SEGMENT}(?:\.{_SEGMENT})*")
_TOKEN = re.compile(r"([^.\[\]]+)|\[([^\[\]]+)\]")


class Selector(NamedTuple):
    """`[imaging]`: the item of a list whose `name` is `imaging`."""

    name: str


Token = str | int | Selector


class ProvenanceEntry(BudgetModel):
    """The source of one input (or, under `*`, of every input without an entry of its own)."""

    source: str = Field(min_length=1)
    note: str = ""
    status: InputStatus = "sourced"


class ProvenancedModel(BudgetModel):
    """A file of an entity that may say where its plain inputs came from."""

    provenance: dict[str, ProvenanceEntry] = Field(default_factory=dict)

    @field_validator("provenance")
    @classmethod
    def _paths(cls, value: dict[str, ProvenanceEntry]) -> dict[str, ProvenanceEntry]:
        for key in value:
            if key != DEFAULT_KEY and parse_path(key) is None:
                raise PydanticCustomError(
                    "provenance_path",
                    "a provenance key is the path of an input (modes[imaging].avg_power_w) or '*'",
                )
        return value


def parse_path(text: str) -> tuple[Token, ...] | None:
    """The tokens of a path like `modes[imaging].avg_power_w`, or None when it is not one. A
    number in brackets is an index, any other text selects a list item by its `name`."""
    if not _PATH.fullmatch(text):
        return None
    tokens: list[Token] = []
    for key, bracket in _TOKEN.findall(text):
        if key:
            tokens.append(key)
        elif bracket.isdecimal():
            tokens.append(int(bracket))
        else:
            tokens.append(Selector(bracket))
    return tuple(tokens)


def resolve_path(data: Any, tokens: tuple[Token, ...]) -> tuple[str | int, ...] | None:
    """The keys and indices that reach the input in `data` (a file as plain data), or None when
    the file has no such input. A selector becomes the index of the item it names, so two
    spellings of one input resolve to the same result."""
    out: list[str | int] = []
    node = data
    for token in tokens:
        if isinstance(token, str):
            if not isinstance(node, dict) or token not in node:
                return None
            node = node[token]
            out.append(token)
        elif isinstance(token, int):
            if not isinstance(node, list) or token >= len(node):
                return None
            node = node[token]
            out.append(token)
        else:
            if not isinstance(node, list):
                return None
            matches = [
                i
                for i, item in enumerate(node)
                if isinstance(item, dict) and item.get("name") == token.name
            ]
            if len(matches) != 1:
                return None
            node = node[matches[0]]
            out.append(matches[0])
    return tuple(out)


def unknown_paths(data: dict[str, Any]) -> list[str]:
    """The keys of the `provenance` mapping of a file that point at no input of the file."""
    entries = data.get("provenance")
    if not isinstance(entries, dict):
        return []
    body = {k: v for k, v in data.items() if k != "provenance"}
    missing = []
    for key in entries:
        if key == DEFAULT_KEY or not isinstance(key, str):
            continue
        tokens = parse_path(key)
        if tokens is not None and resolve_path(body, tokens) is None:
            missing.append(key)
    return sorted(missing)


def own_key(data: dict[str, Any], keys: Iterable[str], path: str) -> str | None:
    """The key of the entry that is written for exactly the input at `path` (not `*`)."""
    body = {k: v for k, v in data.items() if k != "provenance"}
    wanted_tokens = parse_path(path)
    wanted = resolve_path(body, wanted_tokens) if wanted_tokens is not None else None
    if wanted is None:
        return None
    for key in keys:
        tokens = parse_path(key) if key != DEFAULT_KEY else None
        if tokens is not None and resolve_path(body, tokens) == wanted:
            return key
    return None


def find_key(data: dict[str, Any], keys: Iterable[str], path: str) -> str | None:
    """The key of the entry that covers the input at `path` (as the Problems panel and Explain
    write it): the key that reaches the same input, else `*`, else None. `data` is the file as
    plain data."""
    body = {k: v for k, v in data.items() if k != "provenance"}
    wanted_tokens = parse_path(path)
    wanted = resolve_path(body, wanted_tokens) if wanted_tokens is not None else None
    keys = list(keys)
    if wanted is not None:
        for key in keys:
            tokens = parse_path(key) if key != DEFAULT_KEY else None
            if tokens is not None and resolve_path(body, tokens) == wanted:
                return key
    return DEFAULT_KEY if DEFAULT_KEY in keys else None


def find_entry(
    data: dict[str, Any], entries: Mapping[str, ProvenanceEntry], path: str
) -> ProvenanceEntry | None:
    """The entry that covers the input at `path`: its own, else the `*` entry, else None."""
    key = find_key(data, entries, path)
    return None if key is None else entries[key]


def stable_path(data: Any, parts: Sequence[str | int]) -> str:
    """The path of an input written to survive edits: an item of a list whose items have a unique
    `name` is selected by it (`modes[imaging].avg_power_w`), any other item by its index."""
    out = ""
    node = data
    for part in parts:
        if isinstance(part, int):
            name = None
            if isinstance(node, list) and 0 <= part < len(node) and isinstance(node[part], dict):
                name = node[part].get("name")
            shown = str(part)
            if (
                isinstance(name, str)
                and name
                and not name.isdecimal()
                and name == name.strip()
                and not any(c in name for c in "[]")
                and sum(1 for i in node if isinstance(i, dict) and i.get("name") == name) == 1
            ):
                shown = name
            out += f"[{shown}]"
            node = node[part] if isinstance(node, list) and part < len(node) else None
        else:
            out += f".{part}" if out else str(part)
            node = node.get(part) if isinstance(node, dict) else None
    return out
