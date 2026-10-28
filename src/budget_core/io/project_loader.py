"""Load and write a project folder.

Layout: project.yaml, spacecraft.yaml, units/*.yaml, modes/*.yaml, config/<kind>.yaml.
`load_project` never raises for user errors; it returns Problems (see problems.py).
"""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path as FsPath
from typing import Any, TypeVar

from pydantic import ValidationError

from budget_core.io.errors import explain
from budget_core.io.migrations import DEFAULT_REGISTRY, MigrationRegistry
from budget_core.io.paths import resolve_inside
from budget_core.io.yamlio import (
    MAX_YAML_BYTES,
    LineMap,
    YamlSyntaxError,
    dump_yaml,
    format_path,
    load_yaml_text,
    read_limited,
)
from budget_core.manifest import ManifestEntry, entry_for
from budget_core.model import (
    AttenuationTable,
    BudgetModel,
    Ebn0Table,
    Expendable,
    GroundStation,
    Link,
    MarginPolicy,
    MassLimits,
    Orbit,
    PowerConfig,
    PowerSystem,
    Project,
    ProjectConfig,
    ProjectMeta,
    Scenario,
    Spacecraft,
    SpacecraftMode,
    Target,
    ThermalEnvironment,
    ThermalModel,
    Unit,
)
from budget_core.model.annotations import unknown_paths
from budget_core.problems import Problem, Severity, sort_problems
from budget_core.reports.files import write_file

M = TypeVar("M", bound=BudgetModel)

CONFIG_FILES: dict[str, type[BudgetModel]] = {
    "margin_policy": MarginPolicy,
    "power_config": PowerConfig,
    "ebn0_table": Ebn0Table,
    "attenuation_table": AttenuationTable,
    "mass_limits": MassLimits,
    "power_system": PowerSystem,
    "thermal_model": ThermalModel,
    "thermal_environment": ThermalEnvironment,
}

# Files a project may leave out without a warning (the static budgets do not need them).
OPTIONAL_CONFIG = frozenset({"power_system", "thermal_model", "thermal_environment"})


@dataclass(frozen=True)
class LoadResult:
    """`project` is None when any error was found; `problems` is sorted and deterministic."""

    project: Project | None
    problems: list[Problem]
    lines: dict[str, LineMap]


# Fields that say where a number came from or what kind it is. They are written only when they
# differ from the default, and the model digest leaves them out (D-213).
ANNOTATION_FIELDS = frozenset({"provenance", "status"})
_FILE_ORDER = {"schema_version": 0, "kind": 1, "provenance": 3, "requires": 4}


def model_to_data(model: BudgetModel, *, annotations: bool = True) -> dict[str, Any]:
    """Model -> plain data in field order. Optional fields that are None or empty are omitted, and
    so are the annotation fields and `requires` at their default. `annotations=False` leaves the
    annotation fields out altogether (the content of the model, as the digest sees it)."""
    out: dict[str, Any] = {}
    # schema_version and kind come first in every file (a site model declares them last); the
    # provenance mapping and the feature list come last
    fields = sorted(type(model).model_fields.items(), key=lambda kv: _FILE_ORDER.get(kv[0], 2))
    for name, info in fields:
        value = getattr(model, name)
        if name in ANNOTATION_FIELDS and not annotations:
            continue
        if not info.is_required() and (
            value is None or value == "" or (name in _OMIT_AT_DEFAULT and value == info.default)
        ):
            continue
        if not info.is_required() and name in _OMIT_WHEN_EMPTY and not value:
            continue
        out[name] = _plain(value, annotations)
    return out


_OMIT_AT_DEFAULT = frozenset({"status"})
_OMIT_WHEN_EMPTY = frozenset({"provenance", "requires"})


def _plain(value: Any, annotations: bool = True) -> Any:
    if isinstance(value, BudgetModel):
        return model_to_data(value, annotations=annotations)
    if isinstance(value, list):
        return [_plain(v, annotations) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v, annotations) for k, v in value.items()}
    return value


def dump_model(model: BudgetModel) -> str:
    return dump_yaml(model_to_data(model))


def _write(path: FsPath, model: BudgetModel) -> None:
    # atomic, and a link at the target is replaced, not followed (OutputError on failure)
    write_file(path.parent, path.name, dump_model(model).encode("utf-8"), sanitise=False)


def write_project(project: Project, root: FsPath) -> None:
    """Write all project files in canonical form (stable bytes for an unchanged project)."""
    root = FsPath(root)
    _write(root / "project.yaml", project.meta)
    _write(root / "spacecraft.yaml", project.spacecraft)
    for uid, unit in project.units.items():
        _write(root / "units" / f"{uid}.yaml", unit)
    for mid, mode in project.modes.items():
        _write(root / "modes" / f"{mid}.yaml", mode)
    for eid, expendable in project.expendables.items():
        _write(root / "expendables" / f"{eid}.yaml", expendable)
    for folder, items in (
        ("orbits", project.orbits),
        ("ground_stations", project.ground_stations),
        ("targets", project.targets),
        ("scenarios", project.scenarios),
        ("links", project.links),
    ):
        for item_id, model in items.items():
            _write(root / folder / f"{item_id}.yaml", model)
    for kind in CONFIG_FILES:
        model = getattr(project.config, kind)
        if model is not None:
            _write(root / "config" / f"{kind}.yaml", model)


def _yaml_hint(message: str) -> str:
    """What to do about a YAML failure: a limit or an unsupported construct is not an indentation
    problem."""
    if "not supported" in message or "too " in message or "not plain text" in message:
        return (
            "Project files are small plain YAML: text, numbers and lists, without anchors, "
            "tags or merge keys."
        )
    return "Check indentation, colons and quotes around this line."


class _Loader:
    def __init__(self, root: FsPath, registry: MigrationRegistry) -> None:
        self.root = root
        self.registry = registry
        self.problems: list[Problem] = []
        self.lines: dict[str, LineMap] = {}
        self.manifest: list[ManifestEntry] = []

    def error(self, code: str, message: str, file: str | None, hint: str = "") -> None:
        self.problems.append(Problem(Severity.ERROR, code, message, file=file, hint=hint))

    def load(self, rel: str, model_cls: type[M], kind: str) -> M | None:
        path = self.root / rel
        if resolve_inside(self.root, rel) is None:
            self.error(
                "FILE_INVALID",
                "The file must be inside the project folder (links that lead out are not "
                "followed).",
                rel,
            )
            return None
        try:
            if not stat.S_ISREG(path.stat().st_mode):  # a folder, a pipe or a device: never read
                self.error(
                    "FILE_INVALID",
                    "This is not a regular file (it is a folder, a pipe or a device).",
                    rel,
                    "Remove it, or replace it with a text file.",
                )
                return None
            raw = read_limited(path, MAX_YAML_BYTES)
            if len(raw) > MAX_YAML_BYTES:
                self.error(
                    "FILE_INVALID",
                    "The file is too large to be a project file.",
                    rel,
                    "Project files are small text files; check that this is the right file.",
                )
                return None
            self.manifest.append(entry_for(rel, raw))
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            self.error(
                "FILE_INVALID", "The file is not valid UTF-8 text.", rel, "Save the file as UTF-8."
            )
            return None
        except OSError:
            self.error(
                "FILE_NOT_FOUND",
                "The file cannot be read.",
                rel,
                "Check that the file exists and you have permission to read it.",
            )
            return None
        try:
            loaded = load_yaml_text(text)
        except YamlSyntaxError as exc:
            self.problems.append(
                Problem(
                    Severity.ERROR,
                    "YAML_SYNTAX",
                    f"{exc}.",
                    file=rel,
                    line=exc.line,
                    hint=_yaml_hint(str(exc)),
                )
            )
            return None
        self.lines[rel] = loaded.lines
        data = loaded.data
        if not isinstance(data, dict):
            self.error(
                "FILE_INVALID", "The file must contain a mapping of fields (name: value).", rel
            )
            return None
        if data.get("kind") != kind:
            self.problems.append(
                Problem(
                    Severity.ERROR,
                    "KIND_MISMATCH",
                    f"This file must have 'kind: {kind}'.",
                    file=rel,
                    path="kind",
                    line=loaded.lines.lookup(("kind",)),
                    hint=f"Set 'kind: {kind}' (the file location decides its kind).",
                )
            )
            return None
        data, problem = self.registry.migrate(kind, data)
        if problem is not None:
            self.problems.append(_located(problem, rel, loaded.lines))
            if problem.severity is Severity.ERROR:
                return None
        try:
            model = model_cls.model_validate(data)
        except ValidationError as exc:
            self.problems.extend(explain(exc, model_cls, rel, loaded.lines))
            return None
        except ArithmeticError, ValueError, TypeError, RecursionError:
            # a validator hit an impossible number (overflow and the like): report the file
            self.error(
                "FILE_INVALID",
                "The file contains a value that cannot be processed.",
                rel,
                "Check the numbers in this file; values must be finite and of a sensible size.",
            )
            return None
        for key in unknown_paths(data):
            self.problems.append(
                Problem(
                    Severity.WARNING,
                    "PROVENANCE_PATH_UNKNOWN",
                    "A 'provenance' entry names an input that the file does not have.",
                    file=rel,
                    path=format_path(("provenance", key)),
                    line=loaded.lines.lookup(("provenance", key)),
                    hint="The field may have been renamed or removed; correct the key or "
                    "delete the entry.",
                )
            )
        return model


KNOWN_FEATURES: frozenset[str] = frozenset()  # P4 adds "settings", P7 adds "overrides"


def _unsupported_features(meta: ProjectMeta) -> list[Problem]:
    """An error for each feature the project says it needs that this version does not have: a
    tool that ignored it would give results the project did not ask for (D-213)."""
    return [
        Problem(
            Severity.ERROR,
            "FEATURE_UNSUPPORTED",
            "The project needs a feature that this version of the tool does not have.",
            file="project.yaml",
            path=f"requires[{i}]",
            hint="Upgrade System Budget Studio, or open the project with the tool that wrote it.",
        )
        for i, name in enumerate(meta.requires)
        if name not in KNOWN_FEATURES
    ]


def _located(problem: Problem, file: str, lines: LineMap) -> Problem:
    path = tuple(problem.path.split(".")) if problem.path else ()
    return Problem(
        problem.severity,
        problem.code,
        problem.message,
        file=file,
        path=problem.path,
        line=lines.lookup(path),
        hint=problem.hint,
    )


ENTITY_FOLDERS = (
    "units",
    "modes",
    "expendables",
    "orbits",
    "ground_stations",
    "targets",
    "scenarios",
    "links",
)
_CLEAN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _safe_text(text: str) -> str:
    """`text` with lone surrogates (the bytes of a file name that is not UTF-8) escaped, so that
    the Problem can be printed and written in any encoding."""
    return "".join(f"\\u{ord(c):04x}" if 0xD800 <= ord(c) <= 0xDFFF else c for c in text)


def _yaml_names(folder: FsPath) -> list[str]:
    try:
        return sorted(n for n in os.listdir(folder) if n.endswith(".yaml"))
    except OSError:
        return []


def _id_problems(folder: str, names: list[str]) -> tuple[list[Problem], set[str]]:
    """Checks on the ids (file names without .yaml) of one folder. Returns the problems and the
    names that cannot be used at all (an error: the id would be empty, hidden or unencodable).
    Unusual but workable ids only get a warning (decision D-120)."""
    problems: list[Problem] = []
    unusable: set[str] = set()
    seen: dict[str, str] = {}
    clashes: set[str] = set()
    for name in names:
        stem = name[: -len(".yaml")]
        rel = _safe_text(f"{folder}/{name}")
        try:
            stem.encode("utf-8")
        except UnicodeEncodeError:
            unusable.add(name)
            problems.append(
                Problem(
                    Severity.ERROR,
                    "ID_INVALID",
                    "The file name is not valid text (it holds bytes that are not UTF-8).",
                    file=rel,
                    hint="Rename the file with letters, digits, '_' and '-'.",
                )
            )
            continue
        if not stem or stem.startswith("."):
            unusable.add(name)
            problems.append(
                Problem(
                    Severity.ERROR,
                    "ID_INVALID",
                    "The id (the file name without .yaml) must not be empty or start with a dot.",
                    file=rel,
                    hint="Rename the file, for example to a name made of letters, digits, '_' "
                    "and '-'.",
                )
            )
            continue
        if not _CLEAN_ID.fullmatch(stem):
            problems.append(
                Problem(
                    Severity.WARNING,
                    "ID_UNUSUAL",
                    "The id (the file name without .yaml) has characters other than ASCII letters, "
                    "digits, '_' and '-'.",
                    file=rel,
                    hint="Spaces, accents and look-alike letters make ids hard to type and to "
                    "tell apart; rename the file (and every reference to it).",
                )
            )
        folded = unicodedata.normalize("NFC", stem).casefold()
        if folded in seen:
            clashes.update((seen[folded], name))
        else:
            seen[folded] = name
    for name in sorted(clashes):
        problems.append(
            Problem(
                Severity.WARNING,
                "ID_COLLISION",
                "Another file in this folder has an id that differs only in capital letters or in "
                "the way an accent is encoded.",
                file=_safe_text(f"{folder}/{name}"),
                hint=(
                    "On some file systems, Windows among them, such names are one file; rename one."
                ),
            )
        )
    return problems, unusable


def _ignored_files(root: FsPath) -> list[Problem]:
    """Files the loader skips although they look like project files (decision D-120)."""

    def warn(rel: str, message: str, hint: str) -> Problem:
        return Problem(Severity.WARNING, "FILE_IGNORED", message, file=_safe_text(rel), hint=hint)

    out: list[Problem] = []
    wrong_suffix = "Only files whose name ends in exactly '.yaml' are read."
    try:
        top = sorted(os.listdir(root))
    except OSError:
        return out
    for name in top:
        lower = name.lower()
        if name.startswith(".") or not lower.endswith((".yaml", ".yml")):
            continue
        if name not in ("project.yaml", "spacecraft.yaml"):
            out.append(
                warn(
                    name,
                    "This file is ignored: only project.yaml and spacecraft.yaml are read here.",
                    wrong_suffix + " Entities belong in the sub-folders (units/, modes/, ...).",
                )
            )
    for folder in (*ENTITY_FOLDERS, "config"):
        try:
            entries = sorted(os.scandir(root / folder), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            rel = f"{folder}/{name}"
            if name.startswith("."):
                continue
            try:
                is_dir = entry.is_dir()
            except OSError:
                is_dir = False
            if is_dir:
                if not name.endswith(".yaml"):  # a folder named x.yaml is reported when loaded
                    out.append(
                        warn(
                            rel,
                            "This folder is ignored: project files are not read from sub-folders.",
                            f"Move its files up into {folder}/.",
                        )
                    )
                continue
            lower = name.lower()
            if name.endswith(".yaml"):
                if folder == "config" and name[:-5] not in CONFIG_FILES:
                    out.append(
                        warn(
                            rel,
                            "This configuration file is ignored: its name is not one of the "
                            "known configuration files.",
                            "Known: " + ", ".join(f"{k}.yaml" for k in sorted(CONFIG_FILES)) + ".",
                        )
                    )
            elif lower.endswith((".yaml", ".yml")):
                out.append(
                    warn(rel, "This file is ignored: its name does not end in .yaml.", wrong_suffix)
                )
    return out


def load_project(root: FsPath, registry: MigrationRegistry = DEFAULT_REGISTRY) -> LoadResult:
    from budget_core.io.validation import validate_references

    root = FsPath(root)
    if not root.is_dir():
        is_file = root.is_file()
        problem = Problem(
            Severity.ERROR,
            "FILE_NOT_FOUND",
            "The project path is a file, not a folder."
            if is_file
            else "The project folder does not exist.",
            hint="Give the folder that contains project.yaml, not a file inside it."
            if is_file
            else "Check the path; a project folder contains project.yaml.",
        )
        return LoadResult(None, [problem], {})

    loader = _Loader(root, registry)
    meta = loader.load("project.yaml", ProjectMeta, "project")
    if meta is not None:
        loader.problems.extend(_unsupported_features(meta))
    spacecraft = loader.load("spacecraft.yaml", Spacecraft, "spacecraft")
    failed: dict[str, set[str]] = {}  # per folder: ids of files that exist but did not load

    def load_dir(folder: str, cls: type[M], kind: str) -> dict[str, M]:
        found: dict[str, M] = {}
        names = _yaml_names(root / folder)
        id_problems, unusable = _id_problems(folder, names)
        loader.problems.extend(id_problems)
        for name in names:
            stem = name[: -len(".yaml")]
            if name in unusable:
                failed.setdefault(folder, set()).add(stem)
                continue
            item = loader.load(f"{folder}/{name}", cls, kind)
            if item is not None:
                found[stem] = item
            else:
                failed.setdefault(folder, set()).add(stem)
        return found

    units = load_dir("units", Unit, "unit")
    modes = load_dir("modes", SpacecraftMode, "spacecraft_mode")
    expendables = load_dir("expendables", Expendable, "expendable")
    orbits = load_dir("orbits", Orbit, "orbit")
    stations = load_dir("ground_stations", GroundStation, "ground_station")
    targets = load_dir("targets", Target, "target")
    scenarios = load_dir("scenarios", Scenario, "scenario")
    links = load_dir("links", Link, "link")
    loader.problems.extend(_ignored_files(root))

    configs: dict[str, Any] = {}
    for kind, cls in CONFIG_FILES.items():
        rel = f"config/{kind}.yaml"
        if not (root / rel).exists():
            if kind in OPTIONAL_CONFIG:
                continue
            loader.problems.append(
                Problem(
                    Severity.WARNING,
                    "CONFIG_MISSING",
                    "Configuration file is missing.",
                    file=rel,
                    hint="Create it with every number sourced (or 'TBD').",
                )
            )
            continue
        configs[kind] = loader.load(rel, cls, kind)
        if configs[kind] is None:
            failed.setdefault("config", set()).add(kind)

    problems = loader.problems
    project: Project | None = None
    if meta is not None and spacecraft is not None:
        project = Project(
            root,
            meta,
            spacecraft,
            units,
            modes,
            ProjectConfig(**configs),
            expendables,
            orbits,
            stations,
            targets,
            scenarios,
            links,
            tuple(sorted(loader.manifest)),
        )
        problems = problems + validate_references(project, loader.lines, failed)
    problems = sort_problems(problems)
    if any(p.severity is Severity.ERROR for p in problems):
        project = None
    return LoadResult(project, problems, loader.lines)
