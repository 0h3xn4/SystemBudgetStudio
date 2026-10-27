"""Remove from project (D-201): which files can be removed, and what blocks a removal. A ground
station or an imaging target that a scenario lists, and a ground station that a link names as its
peer, cannot be removed without leaving a reference to a file that is gone."""

from __future__ import annotations

import pytest

from budget_core.remove_item import KINDS, blocked_message, rel_of, users_of

SCENARIOS = {
    "one_day": {
        "sites": ["gs_north", "tgt_plains"],
        "rules": [{"kind": "during_pass", "site": "gs_north", "mode": "downlink"}],
    },
    "week": {"sites": ["gs_north"]},
    "bare": {},
}
LINKS = {
    "sband_down": {"peer": "gs_north"},
    "xband_down": {"peer": "gs_south"},
    "static_only": {"peer": None},
}


def test_the_four_kinds_and_their_files() -> None:
    assert KINDS == ("expendable", "ground_station", "target", "link")
    assert rel_of("expendable", "oxidizer") == "expendables/oxidizer.yaml"
    assert rel_of("ground_station", "gs_north") == "ground_stations/gs_north.yaml"
    assert rel_of("target", "tgt_plains") == "targets/tgt_plains.yaml"
    assert rel_of("link", "sband_down") == "links/sband_down.yaml"
    with pytest.raises(ValueError):
        rel_of("unit", "radio")


def test_a_ground_station_is_used_by_the_scenarios_that_list_it_and_the_links_that_name_it() -> (
    None
):
    users = users_of("ground_station", "gs_north", scenarios=SCENARIOS, links=LINKS)
    assert users.scenarios == ["one_day", "week"] and users.links == ["sband_down"]
    assert users_of("ground_station", "gs_south", scenarios=SCENARIOS, links=LINKS).links == [
        "xband_down"
    ]


def test_a_target_is_used_by_scenarios_only() -> None:
    users = users_of("target", "tgt_plains", scenarios=SCENARIOS, links=LINKS)
    assert users.scenarios == ["one_day"] and users.links == []
    # a link names a ground station, never a target, even when an id happens to be the same
    assert users_of("target", "gs_north", scenarios={}, links=LINKS).links == []


def test_a_rule_that_names_a_site_the_scenario_does_not_list_still_counts() -> None:
    scenarios = {"odd": {"sites": [], "rules": [{"kind": "during_pass", "site": "gs_x"}]}}
    assert users_of("ground_station", "gs_x", scenarios=scenarios, links={}).scenarios == ["odd"]


def test_an_expendable_and_a_link_are_used_by_nothing() -> None:
    for kind, item_id in (("expendable", "oxidizer"), ("link", "sband_down")):
        users = users_of(kind, item_id, scenarios=SCENARIOS, links=LINKS)
        assert users.scenarios == [] and users.links == []
        assert blocked_message(kind, item_id, users) is None


def test_a_used_item_gives_a_message_that_names_the_users_and_where_to_change_them() -> None:
    users = users_of("ground_station", "gs_north", scenarios=SCENARIOS, links=LINKS)
    message = blocked_message("ground_station", "gs_north", users)
    assert message is not None
    assert "one_day" in message and "week" in message and "sband_down" in message
    assert "Model > Scenario" in message
    free = users_of("ground_station", "gs_other", scenarios=SCENARIOS, links=LINKS)
    assert blocked_message("ground_station", "gs_other", free) is None


def test_the_data_may_have_odd_shapes_without_failing() -> None:
    scenarios = {"a": {"sites": None, "rules": "x"}, "b": {"sites": "gs_north", "rules": [1, None]}}
    links = {"l": "not a mapping"}
    users = users_of("ground_station", "gs_north", scenarios=scenarios, links=links)  # type: ignore[arg-type]
    assert users.scenarios == [] and users.links == []
