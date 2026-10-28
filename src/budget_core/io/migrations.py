"""Schema versioning: older files migrate in memory, newer files fail with a clear message.

A migration takes the raw mapping of version N and returns the mapping of version N+1 (including
the new `schema_version`). Saving a project afterwards writes the current version.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from budget_core.model.versions import CURRENT_VERSIONS
from budget_core.problems import Problem, Severity

Migration = Callable[[dict[str, Any]], dict[str, Any]]


class MigrationRegistry:
    def __init__(
        self,
        current: Mapping[str, int],
        migrations: Mapping[tuple[str, int], Migration] | None = None,
    ) -> None:
        self._current = dict(current)
        self._migrations = dict(migrations or {})

    def current(self, kind: str) -> int:
        return self._current[kind]

    def migrate(self, kind: str, data: dict[str, Any]) -> tuple[dict[str, Any], Problem | None]:
        """Return (data at the current version, problem). The problem is an info note when the
        file was migrated, an error when it cannot be, and None when nothing was needed."""
        target = self._current[kind]
        version = data.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            return data, Problem(
                Severity.ERROR,
                "SCHEMA_VERSION_MISSING",
                "The file has no valid 'schema_version' (a whole number).",
                path="schema_version",
                hint=f"Add 'schema_version: {target}' as the first line.",
            )
        if version > target:
            return data, Problem(
                Severity.ERROR,
                "SCHEMA_TOO_NEW",
                f"The file uses schema version {version}, newer than this version of the tool "
                f"supports ({target}).",
                path="schema_version",
                hint="Upgrade System Budget Studio, or open the file with the tool that wrote it.",
            )
        if version < 1:
            return data, Problem(
                Severity.ERROR,
                "SCHEMA_VERSION_MISSING",
                "The file has no valid 'schema_version': versions start at 1.",
                path="schema_version",
                hint=f"Set 'schema_version: {target}' (or the version the file was written with).",
            )
        start = version
        current = data
        while version < target:
            step = self._migrations.get((kind, version))
            if step is None:
                return data, Problem(
                    Severity.ERROR,
                    "SCHEMA_MIGRATION_MISSING",
                    f"No migration exists from schema version {version} to {version + 1}.",
                    path="schema_version",
                    hint="Open the file with an older release of the tool, save it, and retry.",
                )
            try:
                nxt = step(dict(current))
                new_version = int(nxt["schema_version"])
                if new_version <= version:
                    raise ValueError("a migration must raise the schema version")
                current, version = nxt, new_version
            except Exception:  # a broken migration must not crash the loader or leak content
                return data, Problem(
                    Severity.ERROR,
                    "SCHEMA_MIGRATION_FAILED",
                    f"Migrating from schema version {version} failed; the file does not match "
                    "that version's layout.",
                    path="schema_version",
                    hint="Check the file against the documentation of that version.",
                )
        if start == target:
            return current, None
        return current, Problem(
            Severity.INFO,
            "FILE_MIGRATED",
            f"The file was migrated in memory from schema version {start} to {target}.",
            path="schema_version",
            hint="Save the project to upgrade the file on disk.",
        )


def _placeholder(note: str) -> dict[str, Any]:
    return {"value": None, "source": "TBD", "note": note}


def margin_policy_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """v1 had one margin per class and one system margin (used for power). v2 separates power and
    mass margins; the mass values do not exist in v1 and become placeholders (decision D-051).
    Keys this migration does not know stay where they are, so the model still rejects them."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key == "classes":
            out["classes"] = _classes_v1_to_v2(value)
        elif key == "system_margin_ratio":
            out["system_power_margin_ratio"] = value
        elif key != "schema_version":
            out[key] = value
    out["schema_version"] = 2
    out.setdefault("kind", "margin_policy")
    out.setdefault(  # v1 files had no mass margin at all
        "system_mass_margin_ratio", _placeholder("Added by migration to schema 2; supply a value.")
    )
    return dict(sorted(out.items(), key=lambda kv: _ORDER.get(kv[0], 99)))


_ORDER = {"schema_version": 0, "kind": 1}


def _classes_v1_to_v2(classes: Any) -> Any:
    if not isinstance(classes, dict):
        return classes  # the model reports the wrong type
    out: dict[str, Any] = {}
    for name, cls in classes.items():
        if not isinstance(cls, dict):
            out[name] = cls
            continue
        item: dict[str, Any] = {}
        for key, value in cls.items():
            if key == "margin_ratio":
                item["power_margin_ratio"] = value
                item["mass_margin_ratio"] = _placeholder(
                    "Added by migration to schema 2; supply a value."
                )
            else:
                item[key] = value
        out[name] = item
    return out


def scenario_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """v2 adds the optional `mission_phase`; a v1 scenario is valid unchanged (decision D-062)."""
    out = dict(data)
    out["schema_version"] = 2
    return out


def unit_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """v2 adds the optional `heat_dissipation_ratio` per power mode, `thermal_node` and
    `temperature_limits`; a v1 unit is valid unchanged and its thermal results are n/a until the
    dissipation ratios are given (decision D-071)."""
    out = dict(data)
    out["schema_version"] = 2
    return out


def _annotated(version: int) -> Migration:
    """The step to `version` of the format revision for provenance (D-213): files gain the
    optional `provenance`, `status` or `requires`, so no key moves and the data stays as it is."""

    def step(data: dict[str, Any]) -> dict[str, Any]:
        out = dict(data)
        out["schema_version"] = version
        return out

    return step


# one step for every kind: the files of version 1 (2 for unit, scenario and margin_policy) read
# unchanged in the next version
_PROVENANCE_STEPS = {
    **{
        (kind, 1): _annotated(2)
        for kind in (
            "project",
            "spacecraft",
            "expendable",
            "orbit",
            "ground_station",
            "target",
            "link",
            "spacecraft_mode",
            "power_config",
            "power_system",
            "thermal_model",
            "thermal_environment",
            "mass_limits",
            "ebn0_table",
            "attenuation_table",
        )
    },
    **{(kind, 2): _annotated(3) for kind in ("unit", "scenario", "margin_policy")},
}

DEFAULT_REGISTRY = MigrationRegistry(
    CURRENT_VERSIONS,
    {
        ("margin_policy", 1): margin_policy_v1_to_v2,
        ("scenario", 1): scenario_v1_to_v2,
        ("unit", 1): unit_v1_to_v2,
        **_PROVENANCE_STEPS,
    },
)
