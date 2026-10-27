"""Remove from project (D-201): which files the window can remove, and what blocks a removal.

An expendable, a ground station, an imaging target and a link are one file each. A scenario names
a ground station or an imaging target in its `sites` (and in a rule), and a link names its ground
station as its `peer`, so removing a file that is still named would leave a reference to nothing
(`REF_UNKNOWN_SITE`, `REF_UNKNOWN_STATION`). The removal is refused, as it is for a spacecraft mode
that a scenario names, and the message says who uses the file. The messages name ids only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = ["KINDS", "LABELS", "Users", "blocked_message", "rel_of", "users_of"]

KINDS = ("expendable", "ground_station", "target", "link")
FOLDERS = {
    "expendable": "expendables",
    "ground_station": "ground_stations",
    "target": "targets",
    "link": "links",
}
LABELS = {
    "expendable": "expendable",
    "ground_station": "ground station",
    "target": "imaging target",
    "link": "link",
}


@dataclass(frozen=True)
class Users:
    """The ids of the scenarios and the links that name a file."""

    scenarios: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


def rel_of(kind: str, item_id: str) -> str:
    """The project file of an item: `ground_stations/<id>.yaml` and so on."""
    if kind not in FOLDERS:
        raise ValueError("this kind of file cannot be removed here")
    return f"{FOLDERS[kind]}/{item_id}.yaml"


def _lists(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _scenario_names(site_id: str, data: Any) -> bool:
    if not isinstance(data, Mapping):
        return False
    if site_id in _lists(data.get("sites")):
        return True
    return any(
        isinstance(rule, Mapping) and rule.get("site") == site_id
        for rule in _lists(data.get("rules"))
    )


def users_of(
    kind: str,
    item_id: str,
    *,
    scenarios: Mapping[str, Any],
    links: Mapping[str, Any],
) -> Users:
    """Who names this item. `scenarios` and `links` are the plain data of the files, by id (the
    window passes the data as it is now, edits that are not saved yet included)."""
    rel_of(kind, item_id)  # refuses a kind that cannot be removed
    named_by_scenarios: list[str] = []
    named_by_links: list[str] = []
    if kind in ("ground_station", "target"):
        named_by_scenarios = [
            scenario_id
            for scenario_id in sorted(scenarios)
            if _scenario_names(item_id, scenarios[scenario_id])
        ]
    if kind == "ground_station":
        named_by_links = [
            link_id
            for link_id in sorted(links)
            if isinstance(links[link_id], Mapping) and links[link_id].get("peer") == item_id
        ]
    return Users(named_by_scenarios, named_by_links)


def blocked_message(kind: str, item_id: str, users: Users) -> str | None:
    """Why the item cannot be removed, or None when nothing names it."""
    if not users.scenarios and not users.links:
        return None
    who: list[str] = []
    if users.scenarios:
        who.append(f"the scenario(s) {', '.join(users.scenarios)}")
    if users.links:
        who.append(f"the link(s) {', '.join(users.links)}")
    if users.scenarios:
        where = "Model > Scenario; for a link, remove it first or set its peer in its file"
    else:
        where = "remove the link first, or set its peer in the link file"
    return (
        f"The {LABELS[kind]} {item_id} is used by {' and '.join(who)}: change them first "
        f"({where}). It was not removed."
    )
