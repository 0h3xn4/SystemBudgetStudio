"""A new spacecraft mode from a few answers (D-188): where the assignments start, the checks, the
data of the file and the scenarios that name a mode."""

from __future__ import annotations

from budget_core.new_mode import (
    check_mode,
    mode_data,
    scenarios_using,
    starting_assignments,
)

UNITS = {
    "camera": ["off", "imaging"],
    "obc": ["Safe", "nominal"],  # no off: starts in the first one
    "radio": ["standby", "OFF", "downlink"],  # off is found whatever the capitals
}


def test_every_unit_starts_off_or_in_its_first_power_mode() -> None:
    assignments, first = starting_assignments(UNITS)
    assert assignments == {"camera": "off", "obc": "Safe", "radio": "OFF"}
    assert first == ["obc"]  # the one that had no off: the caller says so


def test_a_copy_keeps_the_choice_of_the_copied_mode_where_it_is_valid() -> None:
    copied = {"camera": "imaging", "obc": "nominal", "radio": "no_such_mode", "gone": "x"}
    assignments, first = starting_assignments(UNITS, copied)
    assert assignments == {"camera": "imaging", "obc": "nominal", "radio": "OFF"}
    assert first == []  # nothing fell back to a first power mode: the radio fell back to off


def test_a_unit_without_a_power_mode_is_left_out() -> None:
    assignments, _first = starting_assignments({"a": [], "b": ["off"]})
    assert assignments == {"b": "off"}


def test_the_checks_say_what_is_wrong_by_field() -> None:
    def issues(mode_id: str, name: str = "Safe", description: str = "", units=("obc",)):  # type: ignore[no-untyped-def]
        return check_mode(
            mode_id, name, description, existing_ids=["nominal"], unit_ids=list(units)
        )

    assert issues("safe") == []
    assert issues("")[0].field == "mode_id"
    assert issues("a b")[0].field == "mode_id"
    assert issues("Nominal")[0].field == "mode_id"  # differs from an existing id only in capitals
    assert issues("x" * 61)[0].field == "mode_id"
    assert issues("safe", name="  ")[0].field == "name"
    assert issues("safe", description="d" * 481)[0].field == "description"
    no_units = issues("safe", units=())
    assert no_units[0].field == "units" and "add a unit first" in no_units[0].message


def test_the_data_is_a_valid_spacecraft_mode_with_sorted_assignments() -> None:
    data = mode_data(" Safe ", " detumbled ", {"obc": "safe", "adcs": "off"})
    assert data["kind"] == "spacecraft_mode" and data["name"] == "Safe"
    assert data["description"] == "detumbled"
    assert list(data["assignments"]) == ["adcs", "obc"]


def test_a_mode_without_a_unit_makes_no_valid_file() -> None:
    import pytest

    with pytest.raises(ValueError):
        mode_data("Empty", "", {})


def test_the_scenarios_that_name_a_mode_are_found() -> None:
    scenarios = {
        "a": {"default_mode": "safe", "rules": [], "segments": []},
        "b": {"default_mode": "nominal", "rules": [{"kind": "in_eclipse", "mode": "safe"}]},
        "c": {"default_mode": "nominal", "segments": [{"mode": "safe", "start_s": 0}]},
        "d": {"default_mode": "nominal", "rules": [{"mode": "imaging"}], "segments": []},
    }
    assert scenarios_using("safe", scenarios) == ["a", "b", "c"]
    assert scenarios_using("unused", scenarios) == []
