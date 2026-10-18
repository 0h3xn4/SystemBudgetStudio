"""The editable model: the files behind the grids, with one undo stack and an explicit Save (D-159).

The grids of the Model tab do not write files. They edit this document, which holds the data of
every unit file, of every configuration file and of every link file, as the model would write it
(`model_to_data`). One edit (a cell, a paste of many cells, a fill-down, an added mode) is one
undo step. Every edit is checked by the model at once: a cell that makes its file invalid is kept
(so that the user sees and corrects it) and is reported with the field it concerns, in words, with
no value from the file in the message. **Save** writes the files that changed, in place, keeping
comments and key order (`save_edited_data`, D-103), and only when every changed file is valid and
none changed on disk since it was loaded.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from budget_core.io.errors import explain
from budget_core.io.project_loader import CONFIG_FILES, model_to_data
from budget_core.io.roundtrip import file_stamp, save_edited_data
from budget_core.io.yamlio import LineMap, format_path
from budget_core.model import Project
from budget_core.model.base import BudgetModel
from budget_core.problems import Problem, Severity
from budget_core.reports.files import OutputError

Path_ = tuple[str | int, ...]  # keys and list positions that lead to a value inside a file


@dataclass
class FileState:
    rel: str
    cls: type[BudgetModel]
    original: dict[str, Any]  # as the file holds it (as the model writes it)
    current: dict[str, Any]  # as edited
    stamp: str | None  # the file as it was when `original` was read
    problems: list[Problem] = field(default_factory=list)  # of `current`; empty when valid

    @property
    def modified(self) -> bool:
        return self.current != self.original


@dataclass(frozen=True)
class SaveReport:
    ok: bool
    written: tuple[str, ...] = ()
    message: str = ""


class EditFiles(QUndoCommand):
    """One undo step: the data of one or more files before and after an edit."""

    def __init__(
        self,
        document: ModelDocument,
        before: dict[str, dict[str, Any]],
        after: dict[str, dict[str, Any]],
        text: str,
    ) -> None:
        super().__init__(text)
        self._document = document
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._document._apply(self._after)

    def undo(self) -> None:
        self._document._apply(self._before)


def value_at(data: Any, path: Path_) -> Any:
    """The value at `path` inside plain data; None when the path leads nowhere."""
    node = data
    for key in path:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return None
    return node


def set_at(data: Any, path: Path_, value: Any) -> None:
    """Set the value at `path`. A missing mapping on the way is made (a limit typed into a unit
    that had none); `None` removes a key of a mapping (an optional field no longer given) and
    the mappings it leaves empty."""
    chain: list[tuple[Any, str | int]] = []
    node = data
    for key in path[:-1]:
        if isinstance(node, dict) and key not in node:
            if value is None:
                return
            node[key] = {}
        chain.append((node, key))
        node = node[key]
    last = path[-1]
    if value is None and isinstance(node, dict):
        node.pop(last, None)
        for parent, key in reversed(chain):
            child = parent[key]
            if isinstance(parent, dict) and isinstance(child, dict) and not child:
                del parent[key]
            else:
                break
    else:
        node[last] = value


def _data_of(model: BudgetModel) -> dict[str, Any]:
    return model_to_data(model)


class ModelDocument(QObject):
    """The data behind the grids. See the module text."""

    changed = Signal()  # data, problems or the dirty state changed (also by undo and redo)
    dirty_changed = Signal(bool)
    saved = Signal()  # files were written: the project should be loaded again

    def __init__(self) -> None:
        super().__init__()
        self.undo_stack = QUndoStack(self)
        self._files: dict[str, FileState] = {}
        self._root: Path | None = None
        self._dirty = False

    # ---- loading -----------------------------------------------------------------------------
    @property
    def root(self) -> Path | None:
        return self._root

    def load(self, root: Path | None, project: Project | None) -> None:
        """Start from a freshly loaded project, dropping every edit and the undo history."""
        self._root = root
        self._files = {}
        self.undo_stack.clear()
        if root is not None and project is not None:
            for rel, model in _models_of(project):
                self._files[rel] = self._state(root, rel, model)
        self._set_dirty(False)
        self.changed.emit()

    def reload(self, root: Path | None, project: Project | None) -> None:
        """After the project was loaded again (a save, F5, a file edited elsewhere): files with no
        pending edit show what is on disk now; a file with pending edits keeps them, and its save
        is refused if the file changed on disk meanwhile."""
        if root is None or root != self._root:
            self.load(root, project)
            return
        if project is None:
            return  # the project has an error: the grids keep what was last good
        fresh = dict(_models_of(project))
        for rel in list(self._files):
            if rel not in fresh and not self._files[rel].modified:
                del self._files[rel]
        for rel, model in fresh.items():
            known = self._files.get(rel)
            state = self._state(root, rel, model)
            if known is None or not known.modified:
                if known is not None and known.original != state.original:
                    self.undo_stack.clear()  # the file changed from outside: the history is stale
                self._files[rel] = state
        self._after_change()

    def _state(self, root: Path, rel: str, model: BudgetModel) -> FileState:
        data = _data_of(model)
        return FileState(rel, type(model), data, copy.deepcopy(data), file_stamp(root / rel))

    # ---- reading -----------------------------------------------------------------------------
    def rels(self, prefix: str = "") -> list[str]:
        return sorted(rel for rel in self._files if rel.startswith(prefix))

    def has(self, rel: str) -> bool:
        return rel in self._files

    def data(self, rel: str) -> dict[str, Any]:
        return self._files[rel].current

    def original(self, rel: str) -> dict[str, Any]:
        return self._files[rel].original

    def value(self, rel: str, path: Path_) -> Any:
        return value_at(self._files[rel].current, path)

    def problems(self, rel: str | None = None) -> list[Problem]:
        if rel is not None:
            return list(self._files[rel].problems) if rel in self._files else []
        return [p for state in self._files.values() for p in state.problems]

    def has_problems(self) -> bool:
        return any(state.problems for state in self._files.values())

    def problem_at(self, rel: str, path: Path_) -> Problem | None:
        """The problem that concerns exactly this value (its field), if there is one."""
        wanted = format_path(path)
        for problem in self.problems(rel):
            if problem.path == wanted:
                return problem
        return None

    def is_modified(self) -> bool:
        return any(state.modified for state in self._files.values())

    def modified_files(self) -> list[str]:
        return sorted(rel for rel, state in self._files.items() if state.modified)

    # ---- editing -----------------------------------------------------------------------------
    def edit(
        self, changes: Iterable[tuple[str, Callable[[dict[str, Any]], None]]], text: str
    ) -> bool:
        """One undo step: every `(file, change)` is applied to a copy of the file's data. Returns
        False when nothing changed. The data is normalised by the model when it is valid, so
        "2500 mW" becomes 2.5 (W); when it is not valid it is kept as typed, with its problems."""
        before: dict[str, dict[str, Any]] = {}
        after: dict[str, dict[str, Any]] = {}
        for rel, change in changes:
            state = self._files.get(rel)
            if state is None:
                continue
            data = copy.deepcopy(after.get(rel, state.current))  # chained: edits to one file add up
            before.setdefault(rel, state.current)
            change(data)
            after[rel] = _normalise(state.cls, data)
        before = {rel: old for rel, old in before.items() if after[rel] != old}
        after = {rel: new for rel, new in after.items() if rel in before}
        if not after:
            return False
        self.undo_stack.push(EditFiles(self, before, after, text))
        return True

    def set_value(self, rel: str, path: Path_, value: Any, text: str) -> bool:
        return self.edit([(rel, lambda data: set_at(data, path, value))], text)

    def _apply(self, data_by_file: dict[str, dict[str, Any]]) -> None:
        for rel, data in data_by_file.items():
            state = self._files.get(rel)
            if state is not None:
                state.current = copy.deepcopy(data)
        self._after_change(data_by_file)

    def _after_change(self, touched: Iterable[str] = ()) -> None:
        """Check the files whose data changed (the others are as they were), then tell the grids."""
        for rel in touched:
            state = self._files.get(rel)
            if state is not None:
                state.problems = _problems(state)
        self._set_dirty(self.is_modified())
        self.changed.emit()

    def _set_dirty(self, value: bool) -> None:
        if value != self._dirty:
            self._dirty = value
            self.dirty_changed.emit(value)

    # ---- saving ------------------------------------------------------------------------------
    def discard(self) -> None:
        """Forget every edit (the files were not touched)."""
        touched = self.modified_files()
        for state in self._files.values():
            state.current = copy.deepcopy(state.original)
        self.undo_stack.clear()
        self._after_change(touched)

    def discard_changes(self) -> None:
        """The name the Model tab uses for every editor that can drop its edits."""
        self.discard()

    def save(self) -> SaveReport:
        """Write the changed files. Nothing is written unless every changed file is valid and
        still as it was loaded."""
        root = self._root
        changed = self.modified_files()
        if root is None or not changed:
            return SaveReport(True)
        invalid = [rel for rel in changed if self._files[rel].problems]
        if invalid:
            n = sum(len(self._files[rel].problems) for rel in invalid)
            return SaveReport(
                False,
                message=f"Not saved: {n} cell{'s' if n != 1 else ''} in {', '.join(invalid)} "
                "need correcting (they are marked in the grid), or undo the edit.",
            )
        moved = [rel for rel in changed if file_stamp(root / rel) != self._files[rel].stamp]
        if moved:
            return SaveReport(
                False,
                message=f"Not saved: {', '.join(moved)} changed on disk after it was loaded. "
                "Saving would overwrite that change: reload the project (F5) and edit again.",
            )
        written: list[str] = []
        for rel in changed:
            state = self._files[rel]
            try:
                save_edited_data(root / rel, state.original, state.current, _checker(state.cls))
            except (OSError, OutputError, UnicodeDecodeError):
                return SaveReport(
                    False,
                    tuple(written),
                    f"Not saved: {rel} could not be written. Check the folder permissions.",
                )
            state.original = copy.deepcopy(state.current)
            state.stamp = file_stamp(root / rel)
            written.append(rel)
        self._after_change()
        self.saved.emit()
        return SaveReport(True, tuple(written))


# ---- helpers --------------------------------------------------------------------------------
def _models_of(project: Project) -> Iterable[tuple[str, BudgetModel]]:
    for unit_id, unit in project.units.items():
        yield f"units/{unit_id}.yaml", unit
    for scenario_id, scenario in project.scenarios.items():
        yield f"scenarios/{scenario_id}.yaml", scenario
    for link_id, link in project.links.items():
        yield f"links/{link_id}.yaml", link
    for kind in CONFIG_FILES:
        model = getattr(project.config, kind, None)
        if model is not None:
            yield f"config/{kind}.yaml", model


def _checker(cls: type[BudgetModel]) -> Callable[[Any], dict[str, Any]]:
    """Data read from a file -> the model's plain data (what `save_edited_data` compares)."""

    def check(data: Any) -> dict[str, Any]:
        return _data_of(cls.model_validate(data))

    return check


def _normalise(cls: type[BudgetModel], data: dict[str, Any]) -> dict[str, Any]:
    try:
        return _data_of(cls.model_validate(data))
    except ValidationError:
        return data


def _problems(state: FileState) -> list[Problem]:
    try:
        state.cls.model_validate(state.current)
    except ValidationError as exc:
        return explain(exc, state.cls, state.rel, LineMap())
    return _cross_checks(state)


def _cross_checks(state: FileState) -> list[Problem]:
    """What the loader checks between values of one file and the model alone does not: a
    scenario rule must name a site that the scenario lists (the loader's REF_UNKNOWN_SITE)."""
    if not state.rel.startswith("scenarios/"):
        return []
    sites = state.current.get("sites") or []
    return [
        Problem(
            Severity.ERROR,
            "REF_UNKNOWN_SITE",
            "The rule uses a site that the scenario does not list.",
            file=state.rel,
            path=f"rules[{index}].site",
            hint="Tick the site under Sites of this scenario, or choose another site.",
        )
        for index, rule in enumerate(state.current.get("rules") or [])
        if isinstance(rule, dict) and rule.get("site") and rule["site"] not in sites
    ]
