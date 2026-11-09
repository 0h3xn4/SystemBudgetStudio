# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The centre of gravity moves over the mission as a tank empties (2.2.0, D-230): an expendable may
give the position of its centre of mass for each phase, and the mass report shows the shift of the
centre of gravity between the phases."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from budget_core.io.project_loader import load_project
from budget_core.mass.static_mass import static_mass_budget
from budget_core.model import Expendable

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PHASES_BLOCK = (
    "phase_positions_m:\n"
    "  launch: [0.0, 0.0, 0.4]\n"
    "  bol: [0.0, 0.0, 0.38]\n"
    "  eol: [0.0, 0.0, 0.3]\n"
)


def _project(tmp_path: Path, block: str = ""):  # type: ignore[no-untyped-def]
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    if block:
        path = root / "expendables" / "propellant.yaml"
        text = path.read_text(encoding="utf-8")
        text = text.replace("provenance:", block + "provenance:", 1)
        path.write_text(text, encoding="utf-8", newline="\n")
    loaded = load_project(root)
    assert loaded.project is not None, [
        p.message for p in loaded.problems if p.severity.value == "error"
    ]
    return loaded


def _expendable(**extra: object) -> Expendable:
    return Expendable(
        name="Propellant",
        subsystem="PROP",
        maturity="class_c",
        masses_kg={"launch": 5.0, "bol": 4.8, "eol": 0.6},
        **extra,  # type: ignore[arg-type]
    )


# ---- the model ------------------------------------------------------------------------------


def test_the_positions_are_optional() -> None:
    assert _expendable().phase_positions_m == {}


def test_a_position_per_phase_is_kept() -> None:
    e = _expendable(phase_positions_m={"eol": [0.0, 0.0, 0.3]})
    assert e.phase_positions_m == {"eol": [0.0, 0.0, 0.3]}


@pytest.mark.parametrize("bad", [[0.0, 0.0], [0.0, 0.0, float("nan")], [1.0, 2.0, 3.0, 4.0]])
def test_a_position_is_three_finite_numbers(bad: list[float]) -> None:
    with pytest.raises(ValidationError):
        _expendable(phase_positions_m={"bol": bad})


# ---- the budget -----------------------------------------------------------------------------


def test_the_centre_of_gravity_follows_the_tank(tmp_path: Path) -> None:
    fixed = static_mass_budget(_project(tmp_path / "a").project)
    moving = static_mass_budget(_project(tmp_path / "b", PHASES_BLOCK).project)
    by_phase = {p.phase: p for p in moving.phases}
    base = {p.phase: p for p in fixed.phases}
    # hand calculation: only the propellant moves, by (position - 0.4 m) in z over the mass counted
    for phase, mass, z in (("launch", 5.0, 0.4), ("bol", 4.8, 0.38), ("eol", 0.6, 0.3)):
        a, b = base[phase].cog, by_phase[phase].cog
        assert a is not None and b is not None
        expected_dz = mass * (z - 0.4) / b.mass_kg
        assert b.position_m[2] - a.position_m[2] == pytest.approx(expected_dz, abs=1e-12)
        assert b.position_m[0] == pytest.approx(a.position_m[0]) and b.position_m[
            1
        ] == pytest.approx(a.position_m[1])


def test_without_positions_the_budget_is_what_it_was(tmp_path: Path) -> None:
    one = static_mass_budget(_project(tmp_path / "a").project)
    two = static_mass_budget(_project(tmp_path / "b").project)
    assert [p.cog for p in one.phases] == [p.cog for p in two.phases]


def test_a_position_for_a_phase_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "p"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    path = root / "expendables" / "propellant.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "provenance:", "phase_positions_m:\n  nowhere: [0.0, 0.0, 0.3]\nprovenance:", 1
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    result = load_project(root)
    assert any(
        p.code == "REF_UNKNOWN_PHASE" and p.file == "expendables/propellant.yaml"
        for p in result.problems
    )


# ---- the report -----------------------------------------------------------------------------


def test_the_report_shows_the_shift_between_phases(tmp_path: Path) -> None:
    project = _project(tmp_path, PHASES_BLOCK).project
    result = static_mass_budget(project)
    shift = result.cog_shifts
    assert [s.phase for s in shift][0] == result.phases[0].phase
    assert shift[0].distance_m == 0.0 and all(c == 0.0 for c in shift[0].delta_m)
    assert shift[-1].distance_m > 0.0
    first, last = result.phases[0].cog, result.phases[-1].cog
    assert first is not None and last is not None
    assert shift[-1].delta_m[2] == pytest.approx(last.position_m[2] - first.position_m[2])
