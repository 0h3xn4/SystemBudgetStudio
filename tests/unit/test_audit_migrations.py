"""Audit MI-13: migrations keep unknown keys, schema version 0, progress guard."""

from __future__ import annotations

from pathlib import Path

from budget_core.io.migrations import DEFAULT_REGISTRY, MigrationRegistry, margin_policy_v1_to_v2
from budget_core.io.project_loader import load_project
from tests.helpers import write_valid_project


def test_v1_margin_policy_migration_keeps_unknown_keys_so_the_model_rejects_them() -> None:
    data = {
        "schema_version": 1,
        "kind": "margin_policy",
        "classes": {"a": {"margin_ratio": {"value": 0.1, "source": "s"}, "bogus": 1}},
        "system_margin_ratio": {"value": 0.05, "source": "s"},
        "extra_top_level": 2,
    }
    out = margin_policy_v1_to_v2(data)
    assert out["extra_top_level"] == 2
    assert out["classes"]["a"]["bogus"] == 1
    assert out["classes"]["a"]["power_margin_ratio"]["value"] == 0.1
    assert out["schema_version"] == 2
    assert list(out)[:2] == ["schema_version", "kind"]


def test_loading_a_v1_margin_policy_with_a_misspelled_key_is_an_error(tmp_path: Path) -> None:
    write_valid_project(tmp_path / "p")
    (tmp_path / "p" / "config" / "margin_policy.yaml").write_text(
        "schema_version: 1\nkind: margin_policy\nclasses:\n  m1:\n    margin_ratio:\n"
        "      value: 0.1\n      source: s\n    mass_marginn: 3\n"
        "system_margin_ratio:\n  value: 0.05\n  source: s\n",
        encoding="utf-8",
    )
    codes = {p.code for p in load_project(tmp_path / "p").problems}
    assert "FIELD_UNKNOWN" in codes


def test_schema_version_zero_has_a_clear_message() -> None:
    _, problem = DEFAULT_REGISTRY.migrate("unit", {"schema_version": 0, "kind": "unit"})
    assert problem is not None and problem.code == "SCHEMA_VERSION_MISSING"
    assert "start at 1" in problem.message


def test_a_migration_that_does_not_advance_the_version_fails_cleanly() -> None:
    registry = MigrationRegistry({"k": 3}, {("k", 1): lambda d: dict(d), ("k", 2): lambda d: d})
    _, problem = registry.migrate("k", {"schema_version": 1})
    assert problem is not None and problem.code == "SCHEMA_MIGRATION_FAILED"
