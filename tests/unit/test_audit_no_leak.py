"""Audit MI-4 / TL-15: Problem messages and hints never contain text read from project files.

A secret is planted, one at a time, in every free-text value and every user-chosen key of the
example projects (names, descriptions, notes, sources, phase, mode, class, node and case names,
paths, units). After each plant the project is loaded and, when it still loads, every static
budget runs. No Problem may carry the secret in its message, hint or (for values) path.

Keys are the one place where a path may legitimately show the text: a path locates the entry, and
a map key is part of the location. So for keys only message and hint are checked.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import dump_yaml, load_yaml_text
from budget_core.link.evaluate import link_static_budget
from budget_core.mass.static_mass import static_mass_budget
from budget_core.power.static_budget import static_power_budget
from budget_core.problems import Problem
from budget_core.thermal.static_thermal import static_thermal_budget

SECRET = "ZQSECRETQZ"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PROJECTS = ("microsat_250kg_eps", "microsat_150kg", "microsat_250kg")

Leaf = tuple[Path, tuple[str | int, ...], bool]  # file, path in the data, is_key


def _leaves(
    data: Any, path: tuple[str | int, ...] = ()
) -> Iterator[tuple[tuple[str | int, ...], bool]]:
    if isinstance(data, dict):
        for key, value in data.items():
            yield path + (key,), True
            yield from _leaves(value, path + (key,))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _leaves(value, path + (index,))
    elif isinstance(data, str) and path and path[-1] != "kind":
        yield path, False


def _field_names() -> set[str]:
    import budget_core.model as model

    names: set[str] = set()
    for item in vars(model).values():
        if isinstance(item, type) and issubclass(item, BaseModel):
            names.update(item.model_fields)
    return names


FIELD_NAMES = _field_names()


def _shape(path: tuple[str | int, ...]) -> tuple[str, ...]:
    """The path with indices and user-chosen keys replaced by '*': one variant per kind of place."""
    norm = tuple(p if isinstance(p, str) and p in FIELD_NAMES else "*" for p in path)
    if norm[-1] in {"source", "note", "value", "description"}:
        return norm[:1] + norm[-1:]
    return norm[:1] + norm[-2:]


def _mutated(data: Any, path: tuple[str | int, ...], is_key: bool) -> Any:
    """A copy of `data` with the secret appended to the value (or key) at `path`."""
    if not path:
        return data
    head, rest = path[0], path[1:]
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if key == head:
                if is_key and not rest:
                    out[f"{key}{SECRET}"] = value
                else:
                    out[key] = _mutated(value, rest, is_key) if rest else f"{value}{SECRET}"
            else:
                out[key] = value
        return out
    assert isinstance(data, list)
    items = list(data)
    assert isinstance(head, int)
    items[head] = _mutated(items[head], rest, is_key) if rest else f"{items[head]}{SECRET}"
    return items


def _variants() -> list[tuple[str, Path, tuple[str | int, ...], bool]]:
    found: list[tuple[str, Path, tuple[str | int, ...], bool]] = []
    for name in PROJECTS:
        seen: set[tuple[str, tuple[str, ...], bool]] = set()
        root = EXAMPLES / name
        for file in sorted(root.rglob("*.yaml")):
            rel = file.relative_to(root)
            group = rel.parent.name + ("/" + rel.stem if rel.parent.name == "config" else "")
            group = group or rel.stem
            data = load_yaml_text(file.read_text(encoding="utf-8")).data
            for path, is_key in _leaves(data):
                if is_key and path[-1] in FIELD_NAMES:
                    continue  # renaming a field is a typo, not free text
                marker = (group, _shape(path), is_key)
                if marker not in seen:
                    seen.add(marker)
                    found.append((name, rel, path, is_key))
    return found


VARIANTS = _variants()


def _problems_of(root: Path) -> list[Problem]:
    result = load_project(root)
    problems = list(result.problems)
    project = result.project
    if project is not None:
        problems += static_power_budget(project).problems
        problems += static_mass_budget(project).problems
        problems += static_thermal_budget(project).problems
        if project.links:
            problems += link_static_budget(project).problems
    return problems


def test_there_are_many_variants() -> None:
    assert len(VARIANTS) > 150


@pytest.fixture(scope="module")
def copies(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base = tmp_path_factory.mktemp("leak")
    out = {}
    for name in PROJECTS:
        shutil.copytree(EXAMPLES / name, base / name)
        out[name] = base / name
    return out


def test_the_secret_appears_in_no_problem(copies: dict[str, Path]) -> None:
    leaks: list[str] = []
    for name, rel, path, is_key in VARIANTS:
        file = copies[name] / rel
        original = file.read_text(encoding="utf-8")
        data = load_yaml_text(original).data
        file.write_text(dump_yaml(_mutated(data, path, is_key)), encoding="utf-8", newline="\n")
        try:
            for problem in _problems_of(copies[name]):
                texts = {"message": problem.message, "hint": problem.hint}
                if not is_key:
                    texts["path"] = problem.path
                if problem.code == "FIELD_UNKNOWN":  # a misspelt field name is a field name
                    texts.pop("message")
                for where, text in texts.items():
                    if SECRET in text:
                        leaks.append(f"{name}/{rel} {path} key={is_key}: {problem.code} {where}")
        finally:
            file.write_text(original, encoding="utf-8", newline="\n")
    assert not leaks, "\n".join(sorted(set(leaks)))


def test_a_tle_digit_that_int_cannot_read_is_not_echoed(tmp_path: Path) -> None:
    """tle_checksum_ok raises ValueError("invalid literal for int(): '²'") for a superscript digit;
    that text must not reach the Problem."""
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    orbit = next((root / "orbits").glob("*.yaml"))
    first = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
    second = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
    first = first[:10] + "\u00b2" + first[11:]
    orbit.write_text(
        dump_yaml({"schema_version": 1, "kind": "orbit", "name": "x", "tle": [first, second]}),
        encoding="utf-8",
        newline="\n",
    )
    problems = [p for p in load_project(root).problems if p.file and p.file.startswith("orbits/")]
    assert problems
    for problem in problems:
        assert "\u00b2" not in problem.message + problem.hint + problem.path
        assert "literal" not in problem.message
