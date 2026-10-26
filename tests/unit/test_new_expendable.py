"""A new expendable from a few answers (D-197): the checks and the data of the file. An
expendable is propellant, an oxidizer, a pressurant or jettisoned equipment: its mass differs per
mission phase, and every phase of the spacecraft needs a mass (zero if it is not on board)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.new_expendable import ExpendableAnswers, check_expendable, expendable_data

PHASES = ("launch", "bol", "eol")
EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "microsat_250kg_eps"


def answers(**kw: object) -> ExpendableAnswers:
    base: dict[str, object] = {
        "expendable_id": "oxidizer",
        "name": "Oxidizer",
        "subsystem": "PROP",
        "maturity": "class_c",
        "masses_kg": {"launch": 3.2, "bol": 3.1, "eol": 0.4},
        "position": (0.0, 0.0, 0.3),
    }
    return ExpendableAnswers(**{**base, **kw})  # type: ignore[arg-type]


def issues(a: ExpendableAnswers, *, existing=(), classes=("class_a", "class_c"), phases=PHASES):  # type: ignore[no-untyped-def]
    return check_expendable(a, existing_ids=list(existing), classes=list(classes), phases=phases)


def test_good_answers_have_no_issue() -> None:
    assert issues(answers()) == []
    assert issues(answers(position=None)) == []  # the position is optional


@pytest.mark.parametrize(
    ("kw", "field"),
    [
        ({"expendable_id": ""}, "expendable_id"),
        ({"expendable_id": "a b"}, "expendable_id"),
        ({"name": " "}, "name"),
        ({"subsystem": ""}, "subsystem"),
        ({"maturity": "class_z"}, "maturity"),
        ({"masses_kg": {"launch": 3.2, "bol": None, "eol": 0.4}}, "masses_kg.bol"),
        ({"masses_kg": {"launch": 3.2, "bol": -1.0, "eol": 0.4}}, "masses_kg.bol"),
        ({"masses_kg": {"launch": 3.2, "bol": float("nan"), "eol": 0.4}}, "masses_kg.bol"),
        ({"masses_kg": {"launch": 3.2, "bol": 3.1}}, "masses_kg.eol"),
        ({"position": (0.0, None, 0.3)}, "position"),
        ({"position": (0.0, 0.0, float("inf"))}, "position"),
    ],
)
def test_each_wrong_answer_names_its_field(kw: dict[str, object], field: str) -> None:
    found = issues(answers(**kw))
    assert found and found[0].field == field


def test_an_existing_id_is_refused_also_in_other_capitals() -> None:
    assert issues(answers(), existing=["Oxidizer"])[0].field == "expendable_id"


def test_a_project_without_phases_has_the_one_phase_all() -> None:
    assert issues(answers(masses_kg={"all": 2.0}), phases=("all",)) == []


def test_the_data_has_a_mass_per_phase_and_the_position_only_when_given() -> None:
    data = expendable_data(answers())
    assert data["kind"] == "expendable" and data["name"] == "Oxidizer"
    assert data["subsystem"] == "PROP" and data["maturity"] == "class_c"
    assert data["masses_kg"] == {"bol": 3.1, "eol": 0.4, "launch": 3.2}
    assert data["mass_properties"]["position_m"] == [0.0, 0.0, 0.3]
    assert "mass_properties" not in expendable_data(answers(position=None))


def test_a_second_expendable_makes_a_project_that_loads_and_counts_both(tmp_path: Path) -> None:
    """A bipropellant: the fuel of the example and a new oxidizer, one file each."""
    folder = tmp_path / "p"
    shutil.copytree(EXAMPLE, folder)
    result = load_project(folder)
    assert result.project is not None
    phases = result.project.phases
    mass = dict.fromkeys(phases, 1.5)
    data = expendable_data(
        answers(maturity="class_c", masses_kg=dict(mass), position=(0.0, 0.0, 0.25))
    )
    assert (
        issues(
            answers(maturity="class_c", masses_kg=dict(mass)),
            existing=list(result.project.expendables),
            classes=list(result.project.config.margin_policy.classes),  # type: ignore[union-attr]
            phases=phases,
        )
        == []
    )
    import yaml

    (folder / "expendables" / "oxidizer.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    again = load_project(folder)
    assert again.project is not None
    assert set(again.project.expendables) == {"propellant", "oxidizer"}
    assert not [
        p for p in again.problems if p.severity.name == "ERROR" and "xpendable" in str(p.file)
    ]
