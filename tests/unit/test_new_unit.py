"""A new unit from answers (D-187): nothing is invented and every missing number is refused."""

from __future__ import annotations

import pytest

from budget_core.model import Unit
from budget_core.new_unit import UnitAnswers, check_unit, id_from_name, unit_data

BUSES = ("main", "payload")
CLASSES = ("class_a", "class_b")


def answers(**kw: object) -> UnitAnswers:
    base: dict[str, object] = {
        "unit_id": "obc",
        "name": "On-board computer",
        "subsystem": "DH",
        "bus": "main",
        "maturity": "class_b",
        "mass_kg": 0.8,
        "mode_name": "nominal",
        "avg_power_w": 3.0,
        "peak_power_w": 4.5,
    }
    return UnitAnswers(**{**base, **kw})  # type: ignore[arg-type]


def issues(given: UnitAnswers, existing: tuple[str, ...] = ("radio",)) -> list[tuple[str, str]]:
    found = check_unit(given, existing_ids=existing, buses=BUSES, classes=CLASSES)
    return [(i.field, i.message) for i in found]


def test_good_answers_have_no_issue_and_make_a_valid_unit() -> None:
    assert issues(answers()) == []
    data = unit_data(answers())
    unit = Unit.model_validate(data)
    assert unit.name == "On-board computer" and unit.mass_kg == 0.8 and unit.bus == "main"
    assert [(m.name, m.avg_power_w, m.peak_power_w) for m in unit.modes] == [("nominal", 3.0, 4.5)]


def test_the_unit_holds_only_what_was_given() -> None:
    data = unit_data(answers())
    assert set(data) == {
        "schema_version",
        "kind",
        "name",
        "subsystem",
        "mass_kg",
        "bus",
        "maturity",
        "modes",
    }
    assert data["modes"][0]["duty_cycle_ratio"] == 1.0


@pytest.mark.parametrize("field", ["mass_kg", "avg_power_w", "peak_power_w"])
@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_a_missing_number_is_refused_not_read_as_zero(field: str, value: float | None) -> None:
    assert [f for f, _ in issues(answers(**{field: value}))] == [field]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit_id", ""),
        ("unit_id", " "),
        ("unit_id", "a b"),
        ("unit_id", "é"),
        ("unit_id", "_x"),
        ("unit_id", "x" * 61),
        ("unit_id", "RADIO"),
        ("name", " "),
        ("subsystem", ""),
        ("mode_name", ""),
        ("bus", "other"),
        ("maturity", "class_z"),
        ("mass_kg", -1.0),
        ("avg_power_w", -2.0),
        ("peak_power_w", 1.0),
    ],
)
def test_every_wrong_answer_is_named_by_its_field(field: str, value: object) -> None:
    assert [f for f, _ in issues(answers(**{field: value}))] == [field]


def test_with_a_thermal_model_the_subsystem_must_name_one_of_its_nodes() -> None:
    kw = {"existing_ids": (), "buses": BUSES, "classes": CLASSES}
    assert check_unit(answers(subsystem="DH"), thermal_nodes=("DH", "EPS"), **kw) == []
    found = check_unit(answers(subsystem="PAY"), thermal_nodes=("DH", "EPS"), **kw)
    assert [i.field for i in found] == ["subsystem"]
    assert "PAY" not in found[0].message and "EPS" not in found[0].message
    assert check_unit(answers(subsystem="PAY"), thermal_nodes=None, **kw) == []


def test_a_zero_mass_and_equal_powers_are_allowed() -> None:
    assert issues(answers(mass_kg=0.0, avg_power_w=2.0, peak_power_w=2.0)) == []


def test_the_id_of_an_existing_unit_is_refused_also_in_other_capitals() -> None:
    assert [f for f, _ in issues(answers(unit_id="radio"))] == ["unit_id"]
    assert [f for f, _ in issues(answers(unit_id="Radio"))] == ["unit_id"]


def test_the_messages_never_repeat_what_was_typed() -> None:
    found = issues(answers(unit_id="SECRET id", name="  "))
    assert all("SECRET" not in message for _, message in found)


@pytest.mark.parametrize(
    ("name", "suggested"),
    [
        ("On-board computer", "on_board_computer"),
        ("  UHF/VHF radio ", "uhf_vhf_radio"),
        ("Ünï", "n"),
        ("", ""),
        ("a" * 100, "a" * 60),
    ],
)
def test_the_suggested_id_is_the_name_in_file_name_form(name: str, suggested: str) -> None:
    assert id_from_name(name) == suggested
