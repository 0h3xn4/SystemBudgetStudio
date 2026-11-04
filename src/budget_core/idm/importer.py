"""Plan and apply the import of an IDM-CIC model into a project folder (decisions D-240 to D-243).

`plan_import` works out every file to write and writes nothing; `apply_plan` then writes them
(the state file last, so that a run that fails half-way is repaired by running it again). The
import creates a project in a folder that has none, or merges into an existing project:

* a value that came from the model is updated when the model changed it and the file still holds
  what the importer wrote; a value the user changed is kept (decision D-241);
* what the user added (units, modes, other files) is never touched or deleted;
* an object the model no longer has is flagged, not deleted;
* the state file `idm/import_state.yaml` records what the importer wrote, and the mode map
  `idm/mode_map.yaml` (small, meant to be edited) says what each system mode becomes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from budget_core.blank import BlankAnswers, build_blank
from budget_core.idm import SPEC_VERSION
from budget_core.idm.mapping import (
    CLASS_PREFIX,
    MASS_PROPERTIES,
    ImportOptions,
    Mapped,
    ModeEntry,
    finding,
    map_model,
)
from budget_core.idm.merge import ABSENT, MergeLog, changed_paths, merge3
from budget_core.idm.model import IdmModel
from budget_core.io.paths import resolve_inside
from budget_core.io.project_loader import dump_model, load_project
from budget_core.io.roundtrip import join_text, patch_yaml_text, split_text
from budget_core.io.yamlio import YamlSyntaxError, dump_yaml, load_yaml_text, read_limited
from budget_core.model import (
    Expendable,
    MarginPolicy,
    SpacecraftMode,
    ThermalModel,
    Unit,
)
from budget_core.model.base import BudgetModel, Sourced
from budget_core.model.thermal import ThermalNode
from budget_core.problems import Problem, Severity
from budget_core.reports.files import write_files

STATE_PATH = "idm/import_state.yaml"
MODE_MAP_PATH = "idm/mode_map.yaml"
MAX_STATE_BYTES = 20_000_000
STATE_VERSION = 1
MODE_MAP_VERSION = 1


@dataclass(frozen=True)
class PlannedFile:
    path: str  # relative to the project folder, with /
    data: bytes
    action: str  # "create" or "update"


@dataclass
class EntityResult:
    kind: str  # "unit", "mode", "expendable", ...
    id: str
    action: str  # "added", "changed", "unchanged", "removed", "kept"
    detail: tuple[str, ...] = ()


@dataclass
class ImportPlan:
    root: Path
    new_project: bool
    files: list[PlannedFile] = field(default_factory=list)
    results: list[EntityResult] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(p.severity is Severity.ERROR for p in self.problems)

    def count(self, kind: str, action: str) -> int:
        return sum(1 for r in self.results if r.kind == kind and r.action == action)


def _error(code: str, path: str = "") -> Problem:
    return finding(Severity.ERROR, code, path)


# ---- the small files of the import ------------------------------------------------------------


def _read_yaml(root: Path, rel: str) -> tuple[str, Any, tuple[bool, bool]] | None:
    path = root / rel
    try:
        raw = read_limited(path, MAX_STATE_BYTES)
    except OSError:
        return None
    if len(raw) > MAX_STATE_BYTES:
        return None
    text, bom, crlf = split_text(raw)
    try:
        return text, load_yaml_text(text).data, (bom, crlf)
    except YamlSyntaxError:
        return None


def read_mode_map(root: Path) -> tuple[dict[str, ModeEntry] | None, list[Problem]]:
    loaded = _read_yaml(root, MODE_MAP_PATH)
    if loaded is None:
        if (root / MODE_MAP_PATH).exists():
            return None, [_error("IDM_MODE_MAP_INVALID", MODE_MAP_PATH)]
        return None, []
    data = loaded[1]
    rows = data.get("system_modes") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("kind") != "idm_mode_map"
        or data.get("schema_version") != MODE_MAP_VERSION
        or not isinstance(rows, dict)
    ):
        return None, [_error("IDM_MODE_MAP_INVALID", MODE_MAP_PATH)]
    out: dict[str, ModeEntry] = {}
    for system_mode, row in rows.items():
        mode = row.get("mode") if isinstance(row, dict) else None
        name = row.get("name") if isinstance(row, dict) else None
        valid_id = isinstance(mode, str) and mode and _valid_id(mode)
        if (
            not isinstance(row, dict)
            or not isinstance(name, str)
            or not name.strip()
            or not (mode is None or valid_id)
        ):
            return None, [_error("IDM_MODE_MAP_INVALID", f"{MODE_MAP_PATH}: {system_mode}")]
        out[str(system_mode)] = ModeEntry(mode=mode, name=name)
    return out, []


def _valid_id(text: str) -> bool:
    return text[0].isalnum() and all(c.isascii() and (c.isalnum() or c in "-_") for c in text)


def _mode_map_data(entries: dict[str, ModeEntry]) -> dict[str, Any]:
    return {
        "schema_version": MODE_MAP_VERSION,
        "kind": "idm_mode_map",
        "system_modes": {
            key: {"mode": entry.mode, "name": entry.name} for key, entry in sorted(entries.items())
        },
    }


def read_state(root: Path) -> tuple[dict[str, Any] | None, list[Problem]]:
    loaded = _read_yaml(root, STATE_PATH)
    if loaded is None:
        if (root / STATE_PATH).exists():
            return None, [_error("IDM_STATE_INVALID", STATE_PATH)]
        return None, []
    data = loaded[1]
    if (
        not isinstance(data, dict)
        or data.get("kind") != "idm_import_state"
        or data.get("schema_version") != STATE_VERSION
    ):
        return None, [_error("IDM_STATE_INVALID", STATE_PATH)]
    return data, []


# ---- helpers on files --------------------------------------------------------------------------


@dataclass
class _Files:
    root: Path
    planned: dict[str, PlannedFile] = field(default_factory=dict)

    def current(self, rel: str) -> tuple[str, Any, tuple[bool, bool]] | None:
        return _read_yaml(self.root, rel)

    def create(self, rel: str, data: Any) -> None:
        self.planned[rel] = PlannedFile(rel, dump_yaml(data).encode("utf-8"), "create")

    def create_text(self, rel: str, text: str) -> None:
        self.planned[rel] = PlannedFile(rel, text.encode("utf-8"), "create")

    def update(self, rel: str, text: str, old: Any, new: Any, flags: tuple[bool, bool]) -> None:
        patched = patch_yaml_text(text, old, new)
        self.planned[rel] = PlannedFile(rel, join_text(patched, *flags), "update")


def _validate(cls: type[BudgetModel], data: Any) -> bool:
    try:
        cls.model_validate(data)
    except ValidationError, ValueError:
        return False
    return True


def _section(state: dict[str, Any] | None, name: str) -> dict[str, Any]:
    section = (state or {}).get(name)
    return section if isinstance(section, dict) else {}


# ---- one kind of entity ------------------------------------------------------------------------


def _sync(
    kind: str,
    folder: str,
    cls: type[BudgetModel],
    mapped: dict[str, dict[str, Any]],
    keys: dict[str, str],
    old_section: dict[str, Any],
    present_in_model: set[str],
    files: _Files,
    plan: ImportPlan,
) -> dict[str, Any]:
    """Create or merge the files of one kind and return the new state section."""
    new_section: dict[str, Any] = {}
    for item_id in sorted(mapped):
        rel = f"{folder}/{item_id}.yaml"
        data = mapped[item_id]
        entry = old_section.get(item_id)
        current = files.current(rel)
        state_entry = {"full_id": keys[item_id], "status": "current", "imported": data}
        if current is None:
            if (files.root / rel).exists():  # unreadable file: leave it alone
                plan.problems.append(finding(Severity.WARNING, "IDM_FILE_EXISTS_NOT_IMPORTED", rel))
                continue
            if isinstance(entry, dict) and entry.get("status") != "removed":
                plan.problems.append(finding(Severity.INFO, "IDM_DELETED_BY_USER", rel))
                new_section[item_id] = {**entry, "status": "deleted"}
                continue
            files.create(rel, data)
            new_section[item_id] = state_entry
            plan.results.append(EntityResult(kind, item_id, "added"))
            continue
        text, cur, flags = current
        if not isinstance(entry, dict) or entry.get("status") == "deleted":
            plan.problems.append(finding(Severity.WARNING, "IDM_FILE_EXISTS_NOT_IMPORTED", rel))
            continue
        log = MergeLog()
        final = merge3(entry.get("imported", ABSENT), data, cur, log, "")
        if final is ABSENT or not _validate(cls, final):
            plan.problems.append(finding(Severity.WARNING, "IDM_VALUE_INVALID", rel))
            final = cur
        for path in log.kept:
            plan.problems.append(finding(Severity.INFO, "IDM_KEPT_USER_VALUE", f"{rel}: {path}"))
        paths = changed_paths(cur, final)
        if paths:  # a new revision updates the sources of every value, so write the file ...
            files.update(rel, text, cur, final, flags)
        shown = [p for p in paths if not p.startswith("provenance")]  # ... but report real changes
        if shown:
            plan.results.append(EntityResult(kind, item_id, "changed", tuple(shown)))
        else:
            plan.results.append(EntityResult(kind, item_id, "unchanged"))
        new_section[item_id] = state_entry
    for item_id, entry in sorted(old_section.items()):
        if item_id in mapped or not isinstance(entry, dict):
            continue
        full_id = str(entry.get("full_id", ""))
        status = "removed" if full_id not in present_in_model else "not_imported"
        if entry.get("status") not in ("removed", "not_imported"):
            plan.results.append(EntityResult(kind, item_id, "removed", (full_id,)))
            plan.problems.append(
                finding(Severity.WARNING, "IDM_REMOVED_IN_MODEL", f"{folder}/{item_id}.yaml")
            )
        new_section[item_id] = {**entry, "status": status}
    return new_section


# ---- the plan ----------------------------------------------------------------------------------


def _project_name(model: IdmModel) -> str:
    return (model.project_name or Path(model.source_name).stem or "IDM-CIC model").strip()[:120]


def plan_import(
    model: IdmModel,
    root: Path,
    options: ImportOptions,
    *,
    bus_voltage_v: float | None = None,
) -> ImportPlan:
    root = Path(root)
    existing = (root / "project.yaml").is_file()
    plan = ImportPlan(root=root, new_project=not existing)
    if options.margins not in ("raw", "applied"):
        plan.problems.append(_error("IDM_OPTION_INVALID", "margins"))
        return plan
    if options.mass_properties not in MASS_PROPERTIES:
        plan.problems.append(_error("IDM_OPTION_INVALID", "mass_properties"))
        return plan
    files = _Files(root)
    state, state_problems = read_state(root) if existing else (None, [])
    mode_map, map_problems = read_mode_map(root) if existing else (None, [])
    plan.problems += [*state_problems, *map_problems]
    if not plan.ok:
        return plan

    mapped = map_model(model, options, mode_map)
    plan.problems += mapped.findings
    present = {o.full_id for o in model.occurrences}
    present |= {c.full_id for o in model.occurrences for c in o.tank_contents}

    project = None
    if existing:
        loaded = load_project(root)
        if loaded.project is None or any(p.severity is Severity.ERROR for p in loaded.problems):
            plan.problems += [p for p in loaded.problems if p.severity is Severity.ERROR]
            plan.problems.append(_error("IDM_PROJECT_UNUSABLE"))
            return plan
        project = loaded.project
        if options.bus not in {b.name for b in project.spacecraft.buses}:
            plan.problems.append(_error("IDM_BUS_UNKNOWN", options.bus))
            return plan
    elif bus_voltage_v is None:
        plan.problems.append(_error("IDM_NEW_PROJECT_INCOMPLETE", "bus_voltage_v"))
        return plan

    source = f"IDM-CIC model {model.source_name}, revision {model.sha256[:12]}"
    state_out: dict[str, Any] = {
        "schema_version": STATE_VERSION,
        "kind": "idm_import_state",
        "source": {
            "file": model.source_name,
            "sha256": model.sha256,
            "supported_format": SPEC_VERSION,
            "file_format": model.file_version,
        },
        "options": {
            "margins": options.margins,
            "bus": options.bus,
            "mass_properties": options.mass_properties,
        },
    }

    # --- the project-level files -------------------------------------------------------------
    if project is None:
        _new_project_files(model, mapped, options, bus_voltage_v or 0.0, source, files, plan)
    else:
        _merge_project_files(project.root, mapped, state, files, plan)

    # --- the entities --------------------------------------------------------------------------
    state_out["units"] = _sync(
        "unit",
        "units",
        Unit,
        mapped.units,
        mapped.unit_keys,
        _section(state, "units"),
        present,
        files,
        plan,
    )
    state_out["modes"] = _sync(
        "mode",
        "modes",
        SpacecraftMode,
        mapped.modes,
        {m: mapped.mode_system[m] for m in mapped.modes},
        _section(state, "modes"),
        {s.id for s in model.system_modes},
        files,
        plan,
    )
    state_out["expendables"] = _sync(
        "expendable",
        "expendables",
        Expendable,
        mapped.expendables,
        mapped.expendable_keys,
        _section(state, "expendables"),
        present,
        files,
        plan,
    )
    state_out["margin_classes"] = {
        name: data for name, data in sorted(mapped.margin_classes.items())
    }
    state_out["phases"] = list(mapped.phases)

    # --- the mode map ----------------------------------------------------------------------------
    entries = dict(mode_map or {})
    for system_mode, entry in mapped.mode_map.items():
        entries.setdefault(system_mode, entry)
    if mode_map is None:
        files.create(MODE_MAP_PATH, _mode_map_data(entries))
    elif set(entries) != set(mode_map):
        current = files.current(MODE_MAP_PATH)
        assert current is not None
        text, cur, flags = current
        files.update(MODE_MAP_PATH, text, cur, _mode_map_data(entries), flags)

    state_text = dump_yaml(state_out)
    old = files.current(STATE_PATH)
    if old is None or old[0] != state_text:
        files.planned[STATE_PATH] = PlannedFile(
            STATE_PATH,
            state_text.encode("utf-8"),
            "create" if old is None else "update",
        )
    order = {"units": 0, "modes": 1, "expendables": 2, "config": 3, "idm": 5}
    plan.files = sorted(
        files.planned.values(),
        key=lambda f: (order.get(f.path.split("/")[0], 4) if "/" in f.path else 4, f.path),
    )
    return plan


def _new_project_files(
    model: IdmModel,
    mapped: Mapped,
    options: ImportOptions,
    voltage: float,
    source: str,
    files: _Files,
    plan: ImportPlan,
) -> None:
    blank = build_blank(
        BlankAnswers(
            project_name=_project_name(model),
            bus_voltage_v=voltage,
            bus_name=options.bus,
        ),
        plan.root,
    )
    meta = blank.meta.model_copy(
        update={"description": f"Imported from {source}. Margins: {options.margins}."}
    )
    spacecraft = blank.spacecraft.model_copy(
        update={
            "mission_phases": list(mapped.phases),
            "body_frame": "The frame of the IDM-CIC model (origin and axes of its main system).",
        }
    )
    zero = Sourced(
        value=0.0,
        source=source,
        note="The IDM-CIC model has no system-level margin; element margins are not applied.",
        status="estimate",
    )
    classes = {name: _class_model(data) for name, data in sorted(mapped.margin_classes.items())}
    policy = MarginPolicy(
        classes=classes or blank.config.margin_policy.classes,  # type: ignore[union-attr]
        system_power_margin_ratio=zero,
        system_mass_margin_ratio=zero,
    )
    config = replace(blank.config, margin_policy=policy)
    files.create_text("project.yaml", dump_model(meta))
    files.create_text("spacecraft.yaml", dump_model(spacecraft))
    for kind in ("margin_policy", "power_config", "ebn0_table", "attenuation_table", "mass_limits"):
        files.create_text(f"config/{kind}.yaml", dump_model(getattr(config, kind)))
    if mapped.thermal_nodes:
        model_thermal = ThermalModel(
            nodes={k: ThermalNode(name=v["name"]) for k, v in sorted(mapped.thermal_nodes.items())}
        )
        files.create_text("config/thermal_model.yaml", dump_model(model_thermal))


def _class_model(data: dict[str, Any]) -> Any:
    from budget_core.model import MaturityClass

    return MaturityClass.model_validate(data)


def _merge_project_files(
    root: Path, mapped: Mapped, state: dict[str, Any] | None, files: _Files, plan: ImportPlan
) -> None:
    # phases: only add the ones that are missing
    current = files.current("spacecraft.yaml")
    if current is not None and mapped.phases:
        text, cur, flags = current
        have = list(cur.get("mission_phases") or [])
        add = [p for p in mapped.phases if p not in have]
        if add:
            files.update(
                "spacecraft.yaml", text, cur, {**cur, "mission_phases": [*have, *add]}, flags
            )
    # margin classes: only idm_ classes are touched, merged with the user's edits
    current = files.current("config/margin_policy.yaml")
    old_classes = _section(state, "margin_classes")
    if current is not None:
        text, cur, flags = current
        classes = dict(cur.get("classes") or {})
        log = MergeLog()
        changed = False
        for name, data in sorted(mapped.margin_classes.items()):
            if not name.startswith(CLASS_PREFIX):
                continue
            merged = merge3(
                old_classes.get(name, ABSENT), data, classes.get(name, ABSENT), log, name
            )
            if merged is not ABSENT and merged != classes.get(name):
                classes[name] = merged
                changed = True
        for path in log.kept:
            plan.problems.append(
                finding(Severity.INFO, "IDM_KEPT_USER_VALUE", f"margin_policy: {path}")
            )
        if changed:
            new = {**cur, "classes": dict(sorted(classes.items()))}
            if _validate(MarginPolicy, new):
                files.update("config/margin_policy.yaml", text, cur, new, flags)
            else:
                plan.problems.append(
                    finding(Severity.WARNING, "IDM_VALUE_INVALID", "margin_policy")
                )
    elif mapped.margin_classes:
        placeholder = Sourced(value=None, source="TBD", note="Supply the project's value.")
        policy = MarginPolicy(
            classes={n: _class_model(d) for n, d in sorted(mapped.margin_classes.items())},
            system_power_margin_ratio=placeholder,
            system_mass_margin_ratio=placeholder,
        )
        files.create_text("config/margin_policy.yaml", dump_model(policy))
    # thermal nodes: add the ones that are missing, never change a node
    if mapped.thermal_nodes:
        current = files.current("config/thermal_model.yaml")
        if current is None:
            thermal = ThermalModel(
                nodes={
                    k: ThermalNode(name=v["name"]) for k, v in sorted(mapped.thermal_nodes.items())
                }
            )
            files.create_text("config/thermal_model.yaml", dump_model(thermal))
        else:
            text, cur, flags = current
            nodes = dict(cur.get("nodes") or {})
            add_nodes = {k: v for k, v in mapped.thermal_nodes.items() if k not in nodes}
            if add_nodes:
                new = {**cur, "nodes": dict(sorted({**nodes, **add_nodes}.items()))}
                files.update("config/thermal_model.yaml", text, cur, new, flags)


# ---- applying ----------------------------------------------------------------------------------


def apply_plan(plan: ImportPlan) -> list[Path]:
    """Write the files of a plan: folder by folder, the state file last. Returns the paths."""
    if not plan.ok:
        raise ValueError("a plan with errors is not applied")
    written: list[Path] = []
    folders: dict[str, list[tuple[str, bytes]]] = {}
    for planned in plan.files:
        folder, _, name = planned.path.rpartition("/")
        folders.setdefault(folder, []).append((name, planned.data))
    order = sorted(folders, key=lambda f: (f == "idm", f))
    for folder in order:
        target = resolve_inside(plan.root, folder) if folder else plan.root
        if target is None:
            raise ValueError("a file of the plan lies outside the project folder")
        target.mkdir(parents=True, exist_ok=True)
        written += write_files(target, folders[folder], sanitise=False)
    return written


def digest_of(plan: ImportPlan) -> str:
    """A short hash of what a plan would write, to show that identical input is identical."""
    h = hashlib.sha256()
    for f in plan.files:
        h.update(f.path.encode())
        h.update(f.data)
    return h.hexdigest()


def sorted_results(plan: ImportPlan) -> list[EntityResult]:
    return sorted(plan.results, key=lambda r: (r.kind, r.action, r.id))
