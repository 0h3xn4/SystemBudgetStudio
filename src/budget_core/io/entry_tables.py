"""The Eb/N0 table, the attenuation table and the margin policy as spreadsheets (2.2.0, D-231;
the margin policy 2.6.0, D-249).

Export the table as a .csv or .xlsx, fill it with the values *and the sources* of a standard or a
data sheet, and import it back. An import is planned first (`plan_entry_import` lists every change
and every problem and writes nothing); `apply_entry_plan` then edits the file in place, keeping its
comments. Rules, in the spirit of the unit tables (D-102):

* a row is found by its key (modulation and coding; name, kind, frequency and elevation); a row
  with a new key adds an entry, a row with a known key changes it; entries are never deleted;
* an empty cell means "unchanged", never zero; a new row with only its key is a placeholder
  (`source: TBD`), as the *Add Eb/N0 entry* form writes it;
* a number needs its source: a value that is new or changed without a `source` in the same row is
  refused (the tool never attributes a number to the source of another one);
* values may carry a unit, a spreadsheet formula is never evaluated, and no message carries a value
  read from a file.
"""

from __future__ import annotations

import io
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from budget_core.io.paths import resolve_inside
from budget_core.io.unit_table import (
    MAX_COLUMNS,
    MAX_FILE_BYTES,
    Cell,
    TableRead,
    TableRow,
    _csv_rows,
    _detect_indent,
    _error,
    _number,
    _too_large,
    _unreadable,
    _xlsx_rows,
)
from budget_core.io.yamlio import YamlSyntaxError, load_yaml_text
from budget_core.model import (
    CURRENT_VERSIONS,
    AttenuationTable,
    BudgetModel,
    Ebn0Table,
    MarginPolicy,
    Project,
    Sourced,
)
from budget_core.problems import Problem, Severity
from budget_core.reports.csvutil import csv_writer, defuse
from budget_core.reports.files import OutputError, write_file
from budget_core.units.quantity import UnitError

STATUSES = ("sourced", "estimate", "illustrative")
KINDS = ("rain", "gas", "cloud", "scintillation", "other")


@dataclass(frozen=True)
class TableSpec:
    name: str
    file: str  # relative to the project
    kind: str  # the `kind:` of the file
    key: tuple[str, ...]  # the columns that find a row
    texts: tuple[str, ...]  # text columns among the key and the plain fields
    numbers: tuple[str, ...]  # plain number columns (not the sourced one)
    value: str  # the column of the sourced number
    columns: tuple[str, ...]
    title: str


TABLES: dict[str, TableSpec] = {
    "ebn0": TableSpec(
        "ebn0",
        "config/ebn0_table.yaml",
        "ebn0_table",
        ("modulation", "coding"),
        ("modulation", "coding"),
        ("target_ber", "target_fer"),
        "required_ebn0_db",
        (
            "modulation",
            "coding",
            "required_ebn0_db",
            "source",
            "status",
            "note",
            "target_ber",
            "target_fer",
        ),
        "Eb-N0 table",
    ),
    "attenuation": TableSpec(
        "attenuation",
        "config/attenuation_table.yaml",
        "attenuation_table",
        ("name", "attenuation_kind", "freq_hz", "elevation_deg"),
        ("name", "attenuation_kind"),
        ("freq_hz", "elevation_deg"),
        "loss_db",
        (
            "name",
            "attenuation_kind",
            "freq_hz",
            "elevation_deg",
            "loss_db",
            "source",
            "status",
            "note",
        ),
        "Attenuation table",
    ),
    # one row for each margin of the policy: a class and its power or mass margin, or the system
    # margin (item "system"); the same columns and rules as the other tables (D-249)
    "margins": TableSpec(
        "margins",
        "config/margin_policy.yaml",
        "margin_policy",
        ("item", "quantity"),
        ("item", "quantity"),
        (),
        "margin_ratio",
        ("item", "quantity", "margin_ratio", "source", "status", "note"),
        "Margin policy",
    ),
}
_OPTIONAL_KEY = {"elevation_deg"}
MARGIN_QUANTITIES = ("power_margin_ratio", "mass_margin_ratio")
SYSTEM_ITEM = "system"
MARGIN_RATIO_MAX = 10.0  # the upper end of the range that `budget validate` accepts


def _spec(name: str) -> TableSpec:
    return TABLES[name]  # a KeyError for a name that is not a table


# ---- export -----------------------------------------------------------------------------------


def _margin_entries(project: Project) -> list[dict[str, Any]]:
    """The margins of the policy, one row each: every class, then the system."""
    policy = project.config.margin_policy
    out: list[dict[str, Any]] = []

    def row(item: str, quantity: str, sourced: Sourced) -> None:
        out.append(
            {
                "item": item,
                "quantity": quantity,
                "margin_ratio": sourced.value,
                "source": sourced.source,
                "status": sourced.status,
                "note": sourced.note,
            }
        )

    if policy is not None:
        for name, cls in policy.classes.items():
            for quantity in MARGIN_QUANTITIES:
                row(name, quantity, getattr(cls, quantity))
        for quantity in MARGIN_QUANTITIES:
            row(SYSTEM_ITEM, quantity, getattr(policy, f"system_{quantity}"))
    return out


def _entries(project: Project, spec: TableSpec) -> list[dict[str, Any]]:
    if spec.name == "margins":
        return _margin_entries(project)
    table = project.config.ebn0_table if spec.name == "ebn0" else project.config.attenuation_table
    out: list[dict[str, Any]] = []
    for entry in table.entries if table else []:
        sourced: Sourced = getattr(entry, spec.value)
        row: dict[str, Any] = {
            name: getattr(entry, name)
            for name in (*spec.key, *spec.numbers)
            if hasattr(entry, name)
        }
        row.update(
            {
                spec.value: sourced.value,
                "source": sourced.source,
                "status": sourced.status,
                "note": sourced.note,
            }
        )
        out.append(row)
    return out


def _rows(project: Project, spec: TableSpec) -> list[list[Any]]:
    return [
        ["" if row.get(c) is None else row.get(c) for c in spec.columns]
        for row in _entries(project, spec)
    ]


def table_csv(project: Project, name: str) -> str:
    spec = _spec(name)
    handle = io.StringIO()
    writer = csv_writer(handle)
    writer.writerow(spec.columns)
    writer.writerows(_rows(project, spec))
    return handle.getvalue()


def table_xlsx(project: Project, name: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    spec = _spec(name)
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = spec.title
    sheet.append(list(spec.columns))
    for row in _rows(project, spec):
        sheet.append([defuse(v) if isinstance(v, str) else v for v in row])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    for index, column in enumerate(spec.columns, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = max(
            14, len(column) + 2
        )
    notes = book.create_sheet("How to use")
    for line in (
        f"One row per entry of the {spec.title.lower()}. Fill in or change values, save, import.",
        "Give the value together with its source (a standard, a data sheet): a number without "
        "a source is refused.",
        "An empty cell means: leave this as it is. It does not mean zero.",
        "A row with a new key adds an entry; a row with only its key adds a placeholder.",
        "status is sourced, estimate or illustrative. Entries are never deleted by an import.",
    ):
        notes.append([line])
    notes.column_dimensions["A"].width = 100
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


# ---- reading ----------------------------------------------------------------------------------


def read_entry_table(path: Path, name: str) -> TableRead:
    """Read a .csv or .xlsx table of the columns of `name`. Nothing from the file is in a
    message."""
    spec = _spec(name)
    path = Path(path)
    file = path.name
    suffix = path.suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        return _unreadable(file, "Only .csv and .xlsx files are read.")
    try:
        size = path.stat().st_size
    except OSError:
        return _unreadable(file, "The file does not exist or may not be read.")
    if size > MAX_FILE_BYTES:
        return _too_large(file)
    try:
        raw = _csv_rows(path.read_bytes()) if suffix == ".csv" else _xlsx_rows(path)
    except OverflowError:
        return _too_large(file)
    except OSError:
        return _unreadable(file, "The file does not exist or may not be read.")
    if raw is None:
        return _unreadable(file)
    if not raw:
        return TableRead((), (), (_error("IMPORT_FILE_UNREADABLE", "The table is empty.", file),))
    _, header_cells = raw[0]
    if len(header_cells) > MAX_COLUMNS:
        return _too_large(file)
    names = [str(c).strip().lower() if c is not None else "" for c in header_cells]
    problems: list[Problem] = []
    known = set(spec.columns)
    for position, column in enumerate(names, start=1):
        if column and column not in known:
            problems.append(
                Problem(
                    Severity.WARNING,
                    "IMPORT_COLUMN_IGNORED",
                    f"Column {position} is not a column of the table and is ignored.",
                    file=file,
                    line=1,
                    hint="Columns of the table: " + ", ".join(spec.columns) + ".",
                )
            )
    rows: list[TableRow] = []
    for line, cells in raw[1:]:
        values = {
            column: (cells[i] if i < len(cells) else None)
            for i, column in enumerate(names)
            if column in known
        }
        if any(v is not None for v in values.values()):
            rows.append(TableRow(line, values))
    return TableRead(tuple(rows), tuple(n for n in names if n in known), tuple(problems))


# ---- planning ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class EntryChange:
    key: str  # the row, as the user wrote it
    field: str
    old: str | float | None
    new: str | float | None
    kind: Literal["changed", "added"]
    line: int


@dataclass(frozen=True)
class _EntryEdit:
    key: tuple[Any, ...]
    values: dict[str, Any]  # plain fields, by column name
    sourced: dict[str, Any]  # value, source, status, note (only what is to be set)
    is_new: bool


@dataclass(frozen=True)
class EntryPlan:
    changes: tuple[EntryChange, ...]
    unchanged: int
    problems: tuple[Problem, ...]
    edits: tuple[_EntryEdit, ...] = field(default=(), repr=False)

    @property
    def ok(self) -> bool:
        return not any(p.severity is Severity.ERROR for p in self.problems)


def _text(cell: Cell) -> str | None:
    if cell is None:
        return None
    text = (f"{cell:g}" if isinstance(cell, float) else str(cell)).strip()
    return text or None


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, float | int) and isinstance(b, float | int):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-18)
    return bool(a == b)


def _key_of(spec: TableSpec, source: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(source.get(c) for c in spec.key)


def _same_key(a: tuple[Any, ...], b: tuple[Any, ...]) -> bool:
    return all(_same(x, y) for x, y in zip(a, b, strict=True))


def _label(spec: TableSpec, key: tuple[Any, ...]) -> str:
    return " / ".join(
        "" if k is None else f"{k:g}" if isinstance(k, float) else str(k) for k in key
    )


def plan_entry_import(project: Project, name: str, table: TableRead, file: str) -> EntryPlan:
    """What importing `table` would change. Writes nothing."""
    spec = _spec(name)
    problems: list[Problem] = list(table.problems)
    existing = _entries(project, spec)
    changes: list[EntryChange] = []
    edits: list[_EntryEdit] = []
    seen: list[tuple[Any, ...]] = []
    unchanged = 0

    def error(code: str, message: str, line: int, hint: str = "") -> None:
        problems.append(_error(code, message, file, hint, line))

    for row in table.rows:
        line = row.line
        bad = False
        key: list[Any] = []
        for column in spec.key:
            cell = row.cells.get(column)
            if column in spec.texts:
                text = _text(cell)
                if text is None:
                    error("IMPORT_FIELD_MISSING", f"The cell of column '{column}' is empty.", line)
                    bad = True
                key.append(text)
            elif cell is None or _text(cell) is None:
                if column in _OPTIONAL_KEY:
                    key.append(None)
                else:
                    error("IMPORT_FIELD_MISSING", f"The cell of column '{column}' is empty.", line)
                    bad = True
                    key.append(None)
            else:
                try:
                    key.append(_number(cell, column))
                except UnitError:
                    error(
                        "IMPORT_VALUE_INVALID",
                        f"The value in column '{column}' is not valid.",
                        line,
                    )
                    bad = True
                    key.append(None)
        if bad:
            continue
        key_t = tuple(key)
        if any(_same_key(key_t, earlier) for earlier in seen):
            error(
                "IMPORT_DUPLICATE_ROW",
                "Another row has the same key.",
                line,
                "A key appears once in a table: merge the rows.",
            )
            continue
        seen.append(key_t)
        match = next((e for e in existing if _same_key(_key_of(spec, e), key_t)), None)
        label = _label(spec, key_t)

        # the plain number columns, the sourced value and its text columns
        updates: dict[str, Any] = {}
        sourced: dict[str, Any] = {}
        for column in spec.numbers:
            if column in spec.key:
                continue
            cell = row.cells.get(column)
            if _text(cell) is not None:
                try:
                    updates[column] = _number(cell, column)
                except UnitError:
                    error(
                        "IMPORT_VALUE_INVALID",
                        f"The value in column '{column}' is not valid.",
                        line,
                    )
                    bad = True
        cell = row.cells.get(spec.value)
        if _text(cell) is not None:
            try:
                sourced["value"] = _number(cell, spec.value)
            except UnitError:
                error(
                    "IMPORT_VALUE_INVALID",
                    f"The value in column '{spec.value}' is not valid.",
                    line,
                )
                bad = True
        for column in ("source", "status", "note"):
            text = _text(row.cells.get(column))
            if text is not None:
                sourced[column] = text
        if "status" in sourced and sourced["status"] not in STATUSES:
            error(
                "IMPORT_VALUE_INVALID",
                "The value in column 'status' is not valid.",
                line,
                "Use " + ", ".join(STATUSES) + ".",
            )
            bad = True
        if "attenuation_kind" in updates or (
            spec.name == "attenuation"
            and _text(row.cells.get("attenuation_kind")) not in (None, *KINDS)
        ):
            error(
                "IMPORT_VALUE_INVALID",
                "The value in column 'attenuation_kind' is not valid.",
                line,
                "Use " + ", ".join(KINDS) + ".",
            )
            bad = True
        if bad:
            continue

        # a number needs its source
        old_value = None if match is None else match.get(spec.value)
        value_given = "value" in sourced and not (
            match is not None and _same(old_value, sourced["value"])
        )
        if value_given and "source" not in sourced:
            error(
                "IMPORT_SOURCE_MISSING",
                f"A value in column '{spec.value}' needs its source in the same row.",
                line,
                "Name the standard or data sheet in the 'source' column; the tool never attributes "
                "a number to the source of another one.",
            )
            continue

        if match is None:
            built = _build(spec, key_t, updates, sourced)
            if isinstance(built, str):
                error("IMPORT_VALUE_INVALID", built, line)
                continue
            for column, value in {**dict(zip(spec.key, key_t, strict=True)), **updates}.items():
                if value is not None and column in spec.key + spec.numbers:
                    changes.append(EntryChange(label, column, None, value, "added", line))
            if "value" in sourced:
                changes.append(
                    EntryChange(label, spec.value, None, sourced["value"], "added", line)
                )
            for column in ("source", "status", "note"):
                if column in sourced:
                    changes.append(EntryChange(label, column, None, sourced[column], "added", line))
            edits.append(_EntryEdit(key_t, updates, sourced, True))
            continue

        row_changes: list[EntryChange] = []
        for column, value in updates.items():
            if not _same(match.get(column), value):
                row_changes.append(
                    EntryChange(label, column, match.get(column), value, "changed", line)
                )
        for column in ("value", "source", "status", "note"):
            if column in sourced:
                old = match.get(spec.value if column == "value" else column)
                if not _same(old, sourced[column]):
                    shown = spec.value if column == "value" else column
                    row_changes.append(
                        EntryChange(label, shown, old, sourced[column], "changed", line)
                    )
        if not row_changes:
            unchanged += 1
            continue
        built = _build(
            spec,
            key_t,
            {**{c: match.get(c) for c in spec.numbers if match.get(c) is not None}, **updates},
            {
                "value": match.get(spec.value),
                "source": match.get("source"),
                "status": match.get("status"),
                "note": match.get("note") or "",
                **sourced,
            },
        )
        if isinstance(built, str):
            error("IMPORT_VALUE_INVALID", built, line)
            continue
        changes.extend(row_changes)
        edits.append(_EntryEdit(key_t, updates, sourced, False))
    return EntryPlan(tuple(changes), unchanged, tuple(problems), tuple(edits))


def _build(
    spec: TableSpec, key: tuple[Any, ...], plain: dict[str, Any], sourced: dict[str, Any]
) -> str | None:
    """None if the entry the plan makes is valid, else a message naming the column."""
    data: dict[str, Any] = dict(zip(spec.key, key, strict=True))
    data.update(plain)
    value = sourced.get("value")
    data[spec.value] = {
        "value": value,
        "source": sourced.get("source") or "TBD",
        "status": sourced.get("status") or "sourced",
        "note": sourced.get("note")
        or ("" if value is not None else "Placeholder: supply the project's value."),
    }
    if spec.name == "margins":
        return _build_margin(key, data[spec.value])
    model = Ebn0Table if spec.name == "ebn0" else AttenuationTable
    try:
        model.model_validate({"entries": [_without_none(data)]})
    except ValidationError as exc:
        columns = sorted({str(e["loc"][2]) for e in exc.errors() if len(e["loc"]) > 2})
        which = ", ".join(f"'{c}'" for c in columns) or "a column"
        return f"The value of {which} is not valid or is outside its range."
    return None


def _build_margin(key: tuple[Any, ...], sourced: dict[str, Any]) -> str | None:
    """None if the margin the plan makes is valid, else a message naming the column."""
    _item, quantity = key
    if quantity not in MARGIN_QUANTITIES:
        return "The value of 'quantity' is not valid; use " + " or ".join(MARGIN_QUANTITIES) + "."
    value = sourced.get("value")
    if value is not None and not 0.0 <= value <= MARGIN_RATIO_MAX:
        return "The value of 'margin_ratio' is not valid or is outside its range."
    try:
        Sourced.model_validate(sourced)
    except ValidationError:
        return "The value of 'margin_ratio' is not valid or is outside its range."
    return None


def _without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


# ---- applying ---------------------------------------------------------------------------------


def _find(entries: CommentedSeq, spec: TableSpec, key: tuple[Any, ...]) -> CommentedMap | None:
    for candidate in entries:
        found = tuple(candidate.get(c) for c in spec.key)
        if _same_key(found, key):
            return candidate  # type: ignore[no-any-return]
    return None


def _set_sourced(target: CommentedMap, field_name: str, sourced: dict[str, Any], new: bool) -> None:
    node = target.get(field_name)
    if not isinstance(node, CommentedMap):
        node = CommentedMap()
        target[field_name] = node
    if new:
        node["value"] = sourced.get("value")
        node["source"] = sourced.get("source") or "TBD"
        if sourced.get("note") or sourced.get("value") is None:
            node["note"] = sourced.get("note") or "Placeholder: supply the project's value."
        status = sourced.get("status")
        if status and status != "sourced":
            node["status"] = status
        return
    if "value" in sourced:
        node["value"] = sourced["value"]
    for column in ("source", "note"):
        if column in sourced:
            node[column] = sourced[column]
    if "status" in sourced:
        if sourced["status"] == "sourced":
            node.pop("status", None)
        else:
            node["status"] = sourced["status"]


def _placeholder() -> CommentedMap:
    node = CommentedMap()
    node["value"] = None
    node["source"] = "TBD"
    node["note"] = "Placeholder: supply the project's value."
    return node


def _edited_margin_text(text: str, yaml: YAML, edits: Iterable[_EntryEdit]) -> str:
    """The margin policy with the planned edits: a class is a mapping of its two margins (a new
    one gets the other margin as a placeholder), the system margins are two top-level fields."""
    if text.strip():
        document = yaml.load(text)
    else:
        document = CommentedMap()
        document["schema_version"] = CURRENT_VERSIONS["margin_policy"]
        document["kind"] = "margin_policy"
    classes = document.get("classes")
    if not isinstance(classes, CommentedMap):
        classes = CommentedMap()
        document["classes"] = classes
    for quantity in MARGIN_QUANTITIES:
        if f"system_{quantity}" not in document:
            document[f"system_{quantity}"] = _placeholder()
    for edit in edits:
        item, quantity = edit.key
        if item == SYSTEM_ITEM:
            parent, name = document, f"system_{quantity}"
        else:
            parent = classes.get(item)
            if not isinstance(parent, CommentedMap):
                if not edit.is_new:
                    raise OutputError(
                        "The table file no longer matches the plan; plan the import again."
                    )
                parent = CommentedMap()
                for other in MARGIN_QUANTITIES:
                    parent[other] = _placeholder()
                classes[item] = parent
            name = quantity
        # a margin that already stands in the file (a placeholder too) is edited, never replaced
        _set_sourced(parent, name, edit.sourced, edit.is_new and name not in parent)
    buffer = io.StringIO()
    yaml.dump(document, buffer)
    return buffer.getvalue()


def _edited_text(text: str, spec: TableSpec, edits: Iterable[_EntryEdit]) -> str:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    mapping, sequence, offset = _detect_indent(text)
    yaml.indent(mapping=mapping, sequence=sequence, offset=offset)
    yaml.width = 4096
    if spec.name == "margins":
        return _edited_margin_text(text, yaml, edits)
    if text.strip():
        document = yaml.load(text)
    else:
        document = CommentedMap()
        document["schema_version"] = CURRENT_VERSIONS[spec.kind]
        document["kind"] = spec.kind
    entries = document.get("entries")
    if not isinstance(entries, CommentedSeq):
        entries = CommentedSeq()
        document["entries"] = entries
    for edit in edits:
        target = _find(entries, spec, edit.key)
        if target is None:
            if not edit.is_new:
                raise OutputError(
                    "The table file no longer matches the plan; plan the import again."
                )
            target = CommentedMap()
            for column, value in zip(spec.key, edit.key, strict=True):
                if value is not None:
                    target[column] = value
            entries.append(target)
        for column, value in edit.values.items():
            target[column] = value
        _set_sourced(target, spec.value, edit.sourced, edit.is_new)
    buffer = io.StringIO()
    yaml.dump(document, buffer)
    return buffer.getvalue()


def apply_entry_plan(root: Path, name: str, plan: EntryPlan) -> list[Path]:
    """Write the planned changes into the table file, a minimal edit that keeps comments and
    order; a missing file is created. A plan with an error writes nothing."""
    if not plan.ok or not plan.edits:
        return []
    spec = _spec(name)
    root = Path(root)
    target = resolve_inside(root, spec.file)
    if target is None:
        raise OutputError("The table file could not be found; plan the import again.")
    try:
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        if text:
            load_yaml_text(text)
        new_text = _edited_text(text, spec, plan.edits)
        loaded = load_yaml_text(new_text).data
        models: dict[str, type[BudgetModel]] = {
            "ebn0": Ebn0Table,
            "attenuation": AttenuationTable,
            "margins": MarginPolicy,
        }
        models[name].model_validate(_plain(loaded))
    except (
        OSError,
        UnicodeDecodeError,
        YamlSyntaxError,
        KeyError,
        TypeError,
        ValidationError,
    ) as exc:
        raise OutputError("The table file could not be edited; it was not changed.") from exc
    return [write_file(target.parent, target.name, new_text, sanitise=False)]


def _plain(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): _plain(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_plain(v) for v in data]
    return data
