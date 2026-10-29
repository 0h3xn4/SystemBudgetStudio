"""Showing and setting where the inputs came from (D-213, step P3b): Explain, the provenance
row of the reports, and `budget source`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.explain import Explainer
from budget_core.input_sources import (
    Lookup,
    SourceError,
    illustrative_inputs,
    inputs_of,
    set_source,
    status_counts,
)
from budget_core.io.project_loader import load_project
from budget_core.provenance import Provenance, make_provenance

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
ITEMS = "mass:items:launch"


@pytest.fixture()
def eps(tmp_path: Path) -> Path:
    """The example without the marking of its numbers, so each test starts with no sources."""
    root = tmp_path / "eps"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    for path in root.rglob("*.yaml"):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        if "provenance:\n" in lines:
            lines = lines[: lines.index("provenance:\n")]
        lines = [line for line in lines if line.strip() != "status: illustrative"]
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return root


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767323045")
    monkeypatch.setenv("BUDGET_USER", "tester")


def _project(root: Path):  # type: ignore[no-untyped-def]
    project = load_project(root).project
    assert project is not None
    return project


def _mark(root: Path, rel: str, block: str) -> None:
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8") + block, encoding="utf-8", newline="\n")


def _explain_mass(root: Path, unit: str):  # type: ignore[no-untyped-def]
    return Explainer(_project(root)).explain(ITEMS, [unit], "With margin (kg)")


def _inputs(explanation):  # type: ignore[no-untyped-def]
    return {q.name: q for s in explanation.steps for q in s.inputs}


# ---- reading the inputs ---------------------------------------------------------------------


def test_every_number_of_an_entity_file_and_every_sourced_number_is_an_input(eps: Path) -> None:
    items = inputs_of(_project(eps))
    paths = {(i.file, i.path) for i in items}
    assert ("units/obc.yaml", "mass_kg") in paths
    assert ("units/obc.yaml", "modes[0].avg_power_w") in paths
    assert ("config/margin_policy.yaml", "system_power_margin_ratio") in paths
    assert not [i for i in items if i.path == "schema_version"]
    assert all(i.status == "" or i.file.startswith("config/") for i in items), "nothing marked yet"


def test_marking_a_file_changes_the_counts_and_nothing_else(eps: Path) -> None:
    before = status_counts(_project(eps))
    assert before["illustrative"] == 0
    _mark(
        eps,
        "units/obc.yaml",
        "provenance:\n  '*':\n    source: Invented example value\n    status: illustrative\n",
    )
    after = status_counts(_project(eps))
    marked = after["illustrative"]
    assert marked > 0
    assert after[""] == before[""] - marked, "they were inputs without a source before"
    assert illustrative_inputs(_project(eps)) == marked


def test_a_placeholder_is_tbd_whatever_its_status(eps: Path) -> None:
    counts = status_counts(_project(eps))
    placeholders = [
        i for i in inputs_of(_project(eps)) if i.file.startswith("config/") and i.status == "tbd"
    ]
    assert counts["tbd"] == len(placeholders)


# ---- Explain --------------------------------------------------------------------------------


def test_explain_shows_the_source_and_status_of_an_input(eps: Path) -> None:
    before = _inputs(_explain_mass(eps, "obc"))["mass of obc"]
    assert before.source == "" and before.status == ""
    _mark(
        eps,
        "units/obc.yaml",
        "provenance:\n  mass_kg:\n    source: Data sheet XYZ\n    status: estimate\n",
    )
    explanation = _explain_mass(eps, "obc")
    after = _inputs(explanation)["mass of obc"]
    assert after.source == "Data sheet XYZ" and after.status == "estimate"
    text = explanation.format_text()
    assert 'source: "Data sheet XYZ"  [estimate]' in text
    assert after.to_dict()["status"] == "estimate"


def test_a_source_with_the_default_status_shows_no_status(eps: Path) -> None:
    _mark(eps, "units/obc.yaml", "provenance:\n  mass_kg:\n    source: Data sheet\n")
    q = _inputs(_explain_mass(eps, "obc"))["mass of obc"]
    assert q.source == "Data sheet" and q.status == ""
    assert "status" not in q.to_dict(), "the usual case keeps the explanation as it was"


def test_the_default_entry_covers_inputs_without_one_of_their_own(eps: Path) -> None:
    _mark(
        eps,
        "units/obc.yaml",
        "provenance:\n  '*':\n    source: Invented example value\n    status: illustrative\n",
    )
    q = _inputs(_explain_mass(eps, "obc"))["mass of obc"]
    assert q.source == "Invented example value" and q.status == "illustrative"
    other = _inputs(_explain_mass(eps, "radio"))["mass of radio"]
    assert other.source == "", "another file is not covered"


def test_a_value_that_is_only_read_says_where_it_came_from(eps: Path) -> None:
    _mark(eps, "units/obc.yaml", "provenance:\n  mass_kg:\n    source: Data sheet\n")
    explanation = Explainer(_project(eps)).explain(ITEMS, ["obc"], "Mass (kg)")
    text = explanation.format_text()
    assert "(units/obc.yaml mass_kg)" in text and 'source: "Data sheet"' in text


def test_a_sourced_number_shows_its_status_and_a_placeholder_does_not_repeat_tbd(
    eps: Path,
) -> None:
    path = eps / "config" / "margin_policy.yaml"
    text = path.read_text(encoding="utf-8")
    assert "system_mass_margin_ratio:\n" in text
    path.write_text(
        text.replace(
            "system_mass_margin_ratio:\n",
            "system_mass_margin_ratio:\n  status: estimate\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    found = Lookup(_project(eps)).find("config/margin_policy.yaml system_mass_margin_ratio")
    assert found is not None and found.status == "estimate"


def test_an_origin_that_is_not_an_input_is_not_looked_up(eps: Path) -> None:
    lookup = Lookup(_project(eps))
    assert lookup.find("result of step 2") is None
    assert lookup.find("units/missing.yaml mass_kg") is None
    assert lookup.find("units/obc.yaml") is None


# ---- the provenance row ---------------------------------------------------------------------


def test_the_provenance_row_counts_the_illustrative_inputs(eps: Path) -> None:
    rows = dict(make_provenance(_project(eps)).rows())
    assert rows["Illustrative inputs"] == "0"
    _mark(
        eps,
        "units/obc.yaml",
        "provenance:\n  '*':\n    source: Invented example value\n    status: illustrative\n",
    )
    marked = dict(make_provenance(_project(eps)).rows())["Illustrative inputs"]
    assert int(marked) == illustrative_inputs(_project(eps)) > 0


def test_a_provenance_built_by_hand_has_no_such_row() -> None:
    hand = Provenance("T", "1", "3.14", (), "P", "r", "s", "t", "u")
    assert "Illustrative inputs" not in dict(hand.rows())


# ---- setting a source -----------------------------------------------------------------------


def test_set_source_writes_an_entry_in_place_and_keeps_comments(eps: Path) -> None:
    path = eps / "units" / "obc.yaml"
    path.write_text("# kept comment\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    edit = set_source(
        eps,
        "units/obc.yaml",
        "mass_kg",
        source="Data sheet",
        note="flight model",
        status="estimate",
    )
    assert edit.plan.changed and not edit.plan.canonical
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# kept comment\n")
    entry = _project(eps).units["obc"].provenance["mass_kg"]
    assert (entry.source, entry.note, entry.status) == ("Data sheet", "flight model", "estimate")
    assert text.rstrip().endswith("status: estimate")


def test_set_source_accepts_a_name_selector_and_the_default_key(eps: Path) -> None:
    unit = _project(eps).units["obc"]
    name = unit.modes[0].name
    set_source(eps, "units/obc.yaml", f"modes[{name}].avg_power_w", source="TVAC report")
    set_source(eps, "units/obc.yaml", "*", source="Invented", status="illustrative")
    entries = _project(eps).units["obc"].provenance
    assert set(entries) == {f"modes[{name}].avg_power_w", "*"}
    found = Lookup(_project(eps)).find("units/obc.yaml modes[0].avg_power_w")
    assert found is not None and found.source == "TVAC report"


def test_set_source_changes_one_part_of_an_entry_and_keeps_the_others(eps: Path) -> None:
    set_source(eps, "units/obc.yaml", "mass_kg", source="A", note="n", status="estimate")
    set_source(eps, "units/obc.yaml", "mass_kg", source="B")
    entry = _project(eps).units["obc"].provenance["mass_kg"]
    assert (entry.source, entry.note, entry.status) == ("B", "n", "estimate")


def test_set_source_removes_an_entry(eps: Path) -> None:
    set_source(eps, "units/obc.yaml", "mass_kg", source="A")
    set_source(eps, "units/obc.yaml", "mass_kg", source=None)
    assert _project(eps).units["obc"].provenance == {}
    assert "provenance" not in (eps / "units" / "obc.yaml").read_text(encoding="utf-8")


def test_set_source_refuses_what_it_cannot_do(eps: Path) -> None:
    with pytest.raises(SourceError):
        set_source(eps, "units/obc.yaml", "no_such_field", source="A")
    with pytest.raises(SourceError):
        set_source(eps, "units/none.yaml", "mass_kg", source="A")
    with pytest.raises(SourceError):
        set_source(eps, "units/obc.yaml", "mass_kg", source="A", status="probably")
    with pytest.raises(SourceError):
        set_source(eps, "units/obc.yaml", "mass_kg", source=None, note="x")
    with pytest.raises(SourceError):
        set_source(eps, "config/margin_policy.yaml", "no_such", source="A")
    assert "provenance" not in (eps / "units" / "obc.yaml").read_text(encoding="utf-8")


def test_set_source_on_a_sourced_number_sets_its_source_and_status(eps: Path) -> None:
    set_source(
        eps,
        "config/margin_policy.yaml",
        "system_power_margin_ratio",
        source="Programme rule 12",
        status="estimate",
    )
    number = _project(eps).config.margin_policy.system_power_margin_ratio  # type: ignore[union-attr]
    assert number.source == "Programme rule 12" and number.status == "estimate"
    with pytest.raises(SourceError):
        set_source(eps, "config/margin_policy.yaml", "system_power_margin_ratio", source=None)
    with pytest.raises(SourceError):
        set_source(
            eps, "config/margin_policy.yaml", "system_power_margin_ratio", source="x", status="tbd"
        )


def test_a_file_of_the_previous_version_is_upgraded_in_place_with_its_comments(
    eps: Path,
) -> None:
    path = eps / "units" / "obc.yaml"
    text = path.read_text(encoding="utf-8")
    version = text.split("\n", 1)[0]
    path.write_text(text.replace(version, "# kept comment\nschema_version: 2", 1), encoding="utf-8")
    edit = set_source(eps, "units/obc.yaml", "mass_kg", source="Data sheet")
    assert not edit.plan.canonical
    new = path.read_text(encoding="utf-8")
    assert new.startswith("# kept comment\nschema_version: 3")
    assert _project(eps).units["obc"].provenance["mass_kg"].source == "Data sheet"


def test_the_digest_is_the_same_before_and_after_a_source_is_set(eps: Path) -> None:
    from budget_core.io.project_digest import project_digest

    before = project_digest(_project(eps))
    set_source(eps, "units/obc.yaml", "mass_kg", source="Data sheet", status="estimate")
    assert project_digest(_project(eps)) == before


# ---- the command ----------------------------------------------------------------------------


def test_the_command_counts_by_status_and_lists(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["source", str(eps)]) == 0
    out = capsys.readouterr().out
    for label in ("sourced", "estimate", "illustrative", "tbd", "no source recorded"):
        assert label in out
    assert main(["source", str(eps), "units/obc.yaml", "mass_kg", "--source", "S"]) == 0
    assert "written" in capsys.readouterr().out
    assert main(["source", str(eps), "units/obc.yaml", "mass_kg", "--source", "S"]) == 0
    assert "already as asked" in capsys.readouterr().out
    assert main(["source", str(eps), "--list", "sourced"]) == 0
    assert "units/obc.yaml mass_kg" in capsys.readouterr().out.splitlines()


def test_the_command_prints_no_project_values(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["source", str(eps), "units/obc.yaml", "mass_kg", "--source", "Secret data sheet"])
    main(["source", str(eps), "--list", "sourced"])
    out = capsys.readouterr()
    assert "Secret data sheet" not in out.out + out.err
    assert str(_project(eps).units["obc"].mass_kg) not in out.out.split()


def test_the_command_exits_2_for_a_bad_call_and_1_for_a_project_with_errors(
    eps: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["source", str(eps), "units/obc.yaml"]) == 2
    assert main(["source", str(eps), "units/obc.yaml", "mass_kg"]) == 2
    assert main(["source", str(eps), "units/obc.yaml", "nope", "--source", "S"]) == 2
    assert main(["source", str(eps), "units/obc.yaml", "mass_kg", "--clear"]) == 0
    capsys.readouterr()
    (eps / "spacecraft.yaml").write_text("kind: spacecraft\n: broken\n", encoding="utf-8")
    assert main(["source", str(eps)]) == 1


def test_a_json_export_of_a_budget_records_the_illustrative_count(
    eps: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert main(["run", str(eps), "--out", str(out)]) in (0, 1)
    document = json.loads((out / "mass_static.json").read_text(encoding="utf-8"))
    assert document["provenance"]["illustrative_inputs"] == 0
    set_source(eps, "units/obc.yaml", "*", source="Invented", status="illustrative")
    assert main(["run", str(eps), "--out", str(out)]) in (0, 1)
    document = json.loads((out / "mass_static.json").read_text(encoding="utf-8"))
    assert document["provenance"]["illustrative_inputs"] == illustrative_inputs(_project(eps)) > 0


# ---- the examples are marked as invented (P3c) ------------------------------------------------


@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir()))
def test_every_input_of_an_example_is_marked_illustrative(name: str) -> None:
    project = _project(EXAMPLES / name)
    counts = status_counts(project)
    assert counts["illustrative"] > 0
    assert counts["sourced"] == counts["estimate"] == counts[""] == 0, "nothing is left unmarked"
    placeholders = [i for i in inputs_of(project) if i.status == "tbd"]
    assert counts["tbd"] == len(placeholders), "a placeholder is not marked as invented"
    assert illustrative_inputs(project) == counts["illustrative"]
    rows = dict(make_provenance(project).rows())
    assert rows["Illustrative inputs"] == str(counts["illustrative"])


def test_marking_the_examples_does_not_change_their_digest() -> None:
    from budget_core.examples import EXAMPLES as BUILT
    from budget_core.examples import mark_illustrative
    from budget_core.io.project_digest import project_digest

    for name, build in BUILT.items():
        plain = build()  # already marked
        unmarked = mark_illustrative(plain)  # idempotent
        assert project_digest(plain) == project_digest(unmarked), name


def test_a_report_built_from_an_example_says_it_has_invented_numbers(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["run", str(EXAMPLES / "microsat_250kg_eps"), "--out", str(out)]) in (0, 1)
    document = json.loads((out / "mass_static.json").read_text(encoding="utf-8"))
    assert document["provenance"]["illustrative_inputs"] > 0
    csv = (out / "mass_static_provenance.csv").read_text(encoding="utf-8")
    assert "Illustrative inputs" in csv


# ---- helpers for the window (P3b-2) ------------------------------------------------------------


def test_stable_path_selects_a_list_item_by_name_when_that_is_safe() -> None:
    from budget_core.model.annotations import stable_path

    data = {
        "modes": [
            {"name": "idle"},
            {"name": "imaging"},
            {"name": "7"},
            {"name": "a"},
            {"name": "a"},
        ]
    }
    assert stable_path(data, ("modes", 1, "avg_power_w")) == "modes[imaging].avg_power_w"
    assert stable_path(data, ("modes", 2, "avg_power_w")) == "modes[2].avg_power_w", "a number"
    assert stable_path(data, ("modes", 3, "x")) == "modes[3].x", "a name used twice"
    assert stable_path(data, ("mass_kg",)) == "mass_kg"
    assert stable_path({"a": [[1, 2]]}, ("a", 0, 1)) == "a[0][1]"


def test_covering_entry_finds_the_own_entry_then_the_default() -> None:
    from budget_core.input_sources import covering_entry

    data = {
        "mass_kg": 1.0,
        "modes": [{"name": "idle", "avg_power_w": 1.0}, {"name": "imaging", "avg_power_w": 5.0}],
        "provenance": {
            "*": {"source": "Invented", "status": "illustrative"},
            "modes[imaging].avg_power_w": {"source": "TVAC", "note": "n"},
            "broken": "not an entry",
        },
    }
    key, entry = covering_entry(data, "modes[1].avg_power_w") or ("", None)
    assert key == "modes[imaging].avg_power_w" and entry is not None and entry.source == "TVAC"
    key, entry = covering_entry(data, "mass_kg") or ("", None)
    assert key == "*" and entry is not None and entry.status == "illustrative"
    assert covering_entry({"mass_kg": 1.0}, "mass_kg") is None
    assert covering_entry({"mass_kg": 1.0, "provenance": []}, "mass_kg") is None


def test_set_entry_writes_and_removes_and_drops_an_empty_mapping() -> None:
    from budget_core.input_sources import set_entry
    from budget_core.model.annotations import ProvenanceEntry

    data: dict = {"mass_kg": 1.0}
    set_entry(data, "mass_kg", ProvenanceEntry(source="S", note="n", status="estimate"))
    assert data["provenance"] == {"mass_kg": {"source": "S", "note": "n", "status": "estimate"}}
    set_entry(data, "mass_kg", ProvenanceEntry(source="T"))
    assert data["provenance"] == {"mass_kg": {"source": "T"}}, "the default status is not written"
    set_entry(data, "mass_kg", None)
    assert "provenance" not in data
    set_entry(data, "mass_kg", None)  # nothing to remove is not an error
    assert data == {"mass_kg": 1.0}


def test_only_the_entity_files_can_hold_a_provenance() -> None:
    from budget_core.input_sources import has_provenance

    for rel in ("spacecraft.yaml", "units/a.yaml", "modes/a.yaml", "orbits/a.yaml", "links/a.yaml"):
        assert has_provenance(rel), rel
    for rel in ("project.yaml", "config/margin_policy.yaml", "results/x.yaml"):
        assert not has_provenance(rel), rel


def test_entries_for_gives_the_own_entry_and_the_default_separately() -> None:
    from budget_core.input_sources import entries_for

    data = {
        "modes": [{"name": "idle", "avg_power_w": 1.0}, {"name": "imaging", "avg_power_w": 5.0}],
        "provenance": {
            "*": {"source": "Invented", "status": "illustrative"},
            "modes[imaging].avg_power_w": {"source": "TVAC"},
        },
    }
    own, default = entries_for(data, "modes[1].avg_power_w")
    assert own is not None and own[0] == "modes[imaging].avg_power_w" and own[1].source == "TVAC"
    assert default is not None and default.source == "Invented"
    own, default = entries_for(data, "modes[0].avg_power_w")
    assert own is None and default is not None
    assert entries_for({"mass_kg": 1.0}, "mass_kg") == (None, None)
