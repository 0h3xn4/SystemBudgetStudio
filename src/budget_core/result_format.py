"""The envelope every JSON result file carries: what it is and which layout it has (D-205).

`result_format.version` changes only when a key is renamed, removed or changes meaning; adding a
key does not change it. A tool that reads these files checks `name` and `version` first.
Layouts: docs/RESULT_FORMAT.md.
"""

from __future__ import annotations

from typing import Any

RESULT_FORMAT_NAME = "system-budget-studio-result"
RESULT_FORMAT_VERSION = 1

# the kinds, in the order of docs/RESULT_FORMAT.md
KINDS = (
    "power_static",
    "mass_static",
    "thermal_static",
    "link",
    "power_timeline",
    "scenario_environment",
    "comparison",
)

_STATIC_KINDS = {
    "StaticPowerResult": "power_static",
    "StaticMassResult": "mass_static",
    "StaticThermalResult": "thermal_static",
}


def result_format(kind: str) -> dict[str, Any]:
    return {"name": RESULT_FORMAT_NAME, "kind": kind, "version": RESULT_FORMAT_VERSION}


def static_kind(result: object) -> str:
    """The kind of a static budget result, from its type."""
    return _STATIC_KINDS.get(type(result).__name__, "result")
