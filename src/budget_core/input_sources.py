"""Where the inputs of a project came from: reading and setting the sources (D-213).

An input is a number in an entity file (a mass, a power, an orbit element) or a sourced number of
`config/`. The entity files record its source in their `provenance:` mapping, the sourced numbers
carry their own. Nothing here is used by an equation.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from budget_core.io.project_loader import CONFIG_FILES, load_project, model_to_data
from budget_core.io.roundtrip import SavePlan, plan_save, save_edited_data
from budget_core.io.yamlio import format_path, load_yaml_text, read_limited
from budget_core.model import BudgetModel, Project
from budget_core.model.annotations import (
    DEFAULT_KEY,
    INPUT_STATUSES,
    ProvenancedModel,
    ProvenanceEntry,
    Token,
    find_entry,
    find_key,
    own_key,
    parse_path,
    resolve_path,
)

NO_SOURCE = ""  # the status of an input that has no recorded source

_ENTITY_FOLDERS = (
    ("units", "units"),
    ("modes", "modes"),
    ("expendables", "expendables"),
    ("orbits", "orbits"),
    ("ground_stations", "ground_stations"),
    ("targets", "targets"),
    ("scenarios", "scenarios"),
    ("links", "links"),
)


@dataclass(frozen=True)
class InputSource:
    """One input and what the project says about where it came from. `status` is empty when no
    source is recorded; a sourced number with a placeholder value is `tbd`."""

    file: str
    path: str
    status: str
    source: str = ""
    note: str = ""


def project_files(project: Project) -> Iterator[tuple[str, BudgetModel]]:
    """Every model file of the project that holds inputs: its path in the project, and its model."""
    yield "spacecraft.yaml", project.spacecraft
    for attr, folder in _ENTITY_FOLDERS:
        for item_id, model in getattr(project, attr).items():
            yield f"{folder}/{item_id}.yaml", model
    for kind in CONFIG_FILES:
        model = getattr(project.config, kind, None)
        if model is not None:
            yield f"config/{kind}.yaml", model


def _numbers(node: Any, path: tuple[str | int, ...]) -> Iterator[tuple[str | int, ...]]:
    """The paths of the numbers inside plain data (not the schema version, not yes/no values)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if not path and key == "schema_version":
                continue
            yield from _numbers(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _numbers(value, (*path, index))
    elif isinstance(node, int | float) and not isinstance(node, bool):
        yield path


def _sourced(node: Any, path: tuple[str | int, ...]) -> Iterator[tuple[tuple[str | int, ...], Any]]:
    """The sourced numbers (`{value, source, ...}`) inside the plain data of a config file."""
    if isinstance(node, dict):
        if "source" in node and "value" in node:
            yield path, node
            return
        for key, value in node.items():
            yield from _sourced(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _sourced(value, (*path, index))


def entry_source(file: str, path: str, entry: ProvenanceEntry | None) -> InputSource:
    if entry is None:
        return InputSource(file, path, NO_SOURCE)
    return InputSource(file, path, entry.status, entry.source, entry.note)


def inputs_of(project: Project) -> list[InputSource]:
    """Every input of the project with its recorded source, in file order."""
    out: list[InputSource] = []
    for rel, model in project_files(project):
        data = model_to_data(model, annotations=False)
        if isinstance(model, ProvenancedModel):
            for parts in _numbers(data, ()):
                path = format_path(parts)
                out.append(entry_source(rel, path, find_entry(data, model.provenance, path)))
        else:
            for parts, node in _sourced(model_to_data(model), ()):
                placeholder = node.get("value") is None or str(node["source"]).strip() == "TBD"
                status = "tbd" if placeholder else str(node.get("status", "sourced"))
                out.append(
                    InputSource(
                        rel,
                        format_path(parts),
                        status,
                        str(node["source"]),
                        str(node.get("note", "")),
                    )
                )
    return out


def status_counts(project: Project) -> dict[str, int]:
    """How many inputs have each status (the empty status: no source recorded)."""
    counts = dict.fromkeys((NO_SOURCE, *INPUT_STATUSES), 0)
    for item in inputs_of(project):
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def illustrative_inputs(project: Project) -> int:
    """The number of inputs marked as invented sample values."""
    return sum(1 for item in inputs_of(project) if item.status == "illustrative")


class Lookup:
    """The source of an input given as Explain writes it (`units/adcs.yaml modes[0].avg_power_w`).
    The data of every file is made once."""

    def __init__(self, project: Project) -> None:
        self._files = {rel: model for rel, model in project_files(project)}
        self._data: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    def _plain(self, rel: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if rel not in self._data:
            model = self._files[rel]
            self._data[rel] = (
                model_to_data(model, annotations=False),
                model_to_data(model),
            )
        return self._data[rel]

    def find(self, origin: str) -> InputSource | None:
        """What the project says about the input at `origin`; None for an origin that is not an
        input of a project file (a computed value, a missing file)."""
        rel, _, rest = origin.partition(" ")
        model = self._files.get(rel)
        if model is None or not rest:
            return None
        path = rest.split(" ")[0] if parse_path(rest) is None else rest
        if parse_path(path) is None:
            return None
        bare, full = self._plain(rel)
        if isinstance(model, ProvenancedModel):
            entry = find_entry(bare, model.provenance, path)
            return None if entry is None else entry_source(rel, path, entry)
        tokens: tuple[Token, ...] = parse_path(path) or ()
        parts = resolve_path(full, tokens)
        node: Any = full
        for part in parts or ():
            node = node[part]
        if parts is None or not isinstance(node, dict) or "source" not in node:
            return None
        status = str(node.get("status", "sourced"))  # a placeholder shows its source, TBD
        return InputSource(rel, path, status, str(node["source"]), str(node.get("note", "")))


def has_provenance(rel: str) -> bool:
    """Whether the file `rel` of a project may hold a `provenance:` mapping (the configuration
    files keep the source in the number itself)."""
    return rel == "spacecraft.yaml" or rel.partition("/")[0] in {
        folder for _attr, folder in _ENTITY_FOLDERS
    }


def covering_entry(data: dict[str, Any], path: str) -> tuple[str, ProvenanceEntry] | None:
    """The `provenance` entry of a file's plain data that covers the input at `path`, with its
    key; None when the file records nothing for it. Entries that do not read are ignored."""
    raw = data.get("provenance")
    if not isinstance(raw, dict):
        return None
    entries: dict[str, ProvenanceEntry] = {}
    for key, item in raw.items():
        try:
            entries[str(key)] = ProvenanceEntry.model_validate(item)
        except ValueError:
            continue
    key = find_key(data, entries, path)
    return None if key is None else (key, entries[key])


def entries_for(
    data: dict[str, Any], path: str
) -> tuple[tuple[str, ProvenanceEntry] | None, ProvenanceEntry | None]:
    """What a file's plain data records for the input at `path`: the entry written for exactly
    that input (with its key) and the `*` entry of the file, each None when absent."""
    raw = data.get("provenance")
    if not isinstance(raw, dict):
        return None, None
    entries: dict[str, ProvenanceEntry] = {}
    for key, item in raw.items():
        try:
            entries[str(key)] = ProvenanceEntry.model_validate(item)
        except ValueError:
            continue
    key = own_key(data, entries, path)
    own = None if key is None else (key, entries[key])
    return own, entries.get(DEFAULT_KEY)


def set_entry(data: dict[str, Any], key: str, entry: ProvenanceEntry | None) -> None:
    """Put `entry` under `key` in the `provenance` of a file's plain data, or remove the key
    (`None`); an empty mapping is removed too."""
    entries = data.get("provenance")
    if not isinstance(entries, dict):
        entries = {}
    if entry is None:
        entries.pop(key, None)
    else:
        item: dict[str, str] = {"source": entry.source}
        if entry.note:
            item["note"] = entry.note
        if entry.status != "sourced":
            item["status"] = entry.status
        entries[key] = item
    if entries:
        data["provenance"] = entries
    else:
        data.pop("provenance", None)


class SourceError(ValueError):
    """The source cannot be set as asked; the text says why (no project value in it)."""


@dataclass(frozen=True)
class SourceEdit:
    path: Path
    plan: SavePlan


def set_source(
    root: Path,
    rel: str,
    path: str,
    *,
    source: str | None,
    note: str | None = None,
    status: str | None = None,
    rewrite: bool = False,
) -> SourceEdit:
    """Record the source of the input at `path` of the file `rel` of the project in `root`, in
    place, keeping the comments of the file.

    In an entity file this writes the `provenance:` entry (`source=None` removes it); `path` may
    be `*` for the whole file. In a configuration file `path` is the path of a sourced number and
    its `source`, `note` and `status` are set. A file whose edit cannot be made in place, and has
    comments, is refused unless `rewrite` is True."""
    root = Path(root)
    loaded = load_project(root)
    if loaded.project is None:
        raise SourceError("The project has errors; run 'budget validate' and fix them first.")
    files = dict(project_files(loaded.project))
    model = files.get(rel)
    if model is None:
        raise SourceError("The project has no such file (give its path, for example units/a.yaml).")
    if status is not None and status not in INPUT_STATUSES:
        raise SourceError("The status is one of: " + ", ".join(INPUT_STATUSES) + ".")
    current = model_to_data(model)
    new = _edited(model, current, path, source, note, status)
    raw = _raw_version(root / rel)
    # a file of an earlier version is written in the current one: the version changes in place
    old = current if raw is None else {**current, "schema_version": raw}
    cls = type(model)

    def check(data: Any) -> dict[str, Any]:
        return model_to_data(cls.model_validate(data))

    target = root / rel
    plan = plan_save(target, old, new, check)
    if plan.drops_comments and not rewrite:
        raise SourceError(
            "The file cannot be edited in place and has comments that a rewrite would not keep; "
            "use --rewrite to write it whole."
        )
    save_edited_data(target, old, new, check)
    return SourceEdit(target, plan)


def _raw_version(path: Path) -> int | None:
    try:
        data = load_yaml_text(read_limited(path, 1_000_000).decode("utf-8")).data
    except Exception:
        return None
    version = data.get("schema_version") if isinstance(data, dict) else None
    return version if isinstance(version, int) and not isinstance(version, bool) else None


def _edited(
    model: BudgetModel,
    old: dict[str, Any],
    path: str,
    source: str | None,
    note: str | None,
    status: str | None,
) -> dict[str, Any]:
    cls = type(model)
    if isinstance(model, ProvenancedModel):
        if path != DEFAULT_KEY:
            tokens = parse_path(path)
            body = model_to_data(model, annotations=False)
            if tokens is None or resolve_path(body, tokens) is None:
                raise SourceError("The file has no such input (write the path as Explain does).")
        entries = dict(model.provenance)
        if source is None:
            if status is not None or note is not None:
                raise SourceError("Give --source, or --clear to remove the entry.")
            entries.pop(path, None)
        else:
            previous = entries.get(path)
            entries[path] = ProvenanceEntry(
                source=source,
                note=previous.note if note is None and previous else (note or ""),
                status=status or (previous.status if previous else "sourced"),  # type: ignore[arg-type]
            )
        return model_to_data(cls.model_validate({**old, "provenance": _entries(entries)}))
    tokens = parse_path(path)
    if tokens is None:
        raise SourceError("The path of a sourced number is written as in the Problems panel.")
    new = _copy(old)
    parts = resolve_path(new, tokens)
    node: Any = new
    for part in parts or ():
        node = node[part]
    if parts is None or not isinstance(node, dict) or "source" not in node:
        raise SourceError("The file has no sourced number at that path.")
    if source is None:
        raise SourceError("Give --source: a sourced number always has one.")
    node["source"] = source
    if note is not None:
        node["note"] = note
    if status is not None:
        if status == "tbd":
            raise SourceError("Mark a placeholder with the source TBD, not with a status.")
        node["status"] = status
    return model_to_data(cls.model_validate(new))


def _entries(entries: dict[str, ProvenanceEntry]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for key, entry in entries.items():
        item = {"source": entry.source}
        if entry.note:
            item["note"] = entry.note
        if entry.status != "sourced":
            item["status"] = entry.status
        out[key] = item
    return out


def _copy(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _copy(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_copy(v) for v in node]
    return node
