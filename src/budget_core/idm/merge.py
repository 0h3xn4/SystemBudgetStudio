"""Three-way merge of imported data with what the user may have changed (decision D-241).

For every value there are three versions: `old`, what the importer wrote last time; `new`, what
the model gives now; `cur`, what the file holds now. The rules, applied value by value:

* the file still holds what was imported (`cur == old`): take `new`;
* the model did not change (`new == old`): keep `cur`, the user's edit;
* both changed and differ: keep `cur` and report it as kept (the user's value wins);
* a mapping is merged key by key, and a list of mappings that have a `name` item by item, so that
  a mode added by the user next to imported modes stays and an imported mode that the model no
  longer has is dropped only when the user did not touch it.

Nothing the importer never wrote is lost: a key only `cur` has is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ABSENT: Any = object()


@dataclass
class MergeLog:
    kept: list[str] = field(default_factory=list)  # paths where the user's value was kept


def _named(items: Any) -> bool:
    return (
        isinstance(items, list)
        and bool(items)
        and all(isinstance(i, dict) and isinstance(i.get("name"), str) for i in items)
    )


def _by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {i["name"]: i for i in items}


def merge3(old: Any, new: Any, cur: Any, log: MergeLog, path: str = "") -> Any:
    """The merged value, or ABSENT when the value should not exist."""
    if new == cur:
        return cur
    if cur == old:
        return new
    if new == old:
        return cur
    if new is ABSENT or cur is ABSENT:  # one side dropped it, the other changed it: keep the file
        log.kept.append(path)
        return cur
    present = [v for v in (old, new, cur) if v is not ABSENT]
    if present and all(isinstance(v, dict) for v in present):
        return _merge_dicts(old, new, cur, log, path)
    if present and all(_named(v) or v == [] for v in present) and any(_named(v) for v in present):
        return _merge_named(
            [] if old is ABSENT else old,
            [] if new is ABSENT else new,
            [] if cur is ABSENT else cur,
            log,
            path,
        )
    log.kept.append(path)
    return cur


def _merge_dicts(old: Any, new: Any, cur: Any, log: MergeLog, path: str) -> Any:
    o = {} if old is ABSENT else old
    n = {} if new is ABSENT else new
    c = {} if cur is ABSENT else cur
    out: dict[str, Any] = {}
    for key in [*n, *(k for k in c if k not in n), *(k for k in o if k not in n and k not in c)]:
        merged = merge3(
            o.get(key, ABSENT), n.get(key, ABSENT), c.get(key, ABSENT), log, _join(path, key)
        )
        if merged is not ABSENT:
            out[key] = merged
    return out


def _merge_named(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    cur: list[dict[str, Any]],
    log: MergeLog,
    path: str,
) -> list[dict[str, Any]]:
    o, n, c = _by_name(old), _by_name(new), _by_name(cur)
    out: list[dict[str, Any]] = []
    for name in [*n, *(k for k in c if k not in n)]:
        merged = merge3(
            o.get(name, ABSENT), n.get(name, ABSENT), c.get(name, ABSENT), log, f"{path}[{name}]"
        )
        if merged is not ABSENT:
            out.append(merged)
    return out


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def changed_paths(before: Any, after: Any, path: str = "") -> list[str]:
    """The paths of the values that differ between two pieces of data, for a summary."""
    if isinstance(before, dict) and isinstance(after, dict):
        out: list[str] = []
        for key in sorted({*before, *after}):
            out += changed_paths(before.get(key, ABSENT), after.get(key, ABSENT), _join(path, key))
        return out
    if _named(before) and _named(after):
        b, a = _by_name(before), _by_name(after)
        out = []
        for name in sorted({*b, *a}):
            out += changed_paths(b.get(name, ABSENT), a.get(name, ABSENT), f"{path}[{name}]")
        return out
    return [] if before == after else [path]
