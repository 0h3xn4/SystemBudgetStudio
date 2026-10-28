"""D-204: the file manifest, the model digest, the run parameters and `budget verify`."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from budget_cli.main import main
from budget_core.io.project_digest import project_data, project_digest
from budget_core.io.project_loader import load_project
from budget_core.manifest import canonical_json, files_digest
from budget_core.provenance import Provenance, make_provenance
from budget_core.verify import DIFFERENT, MATCH, UNKNOWN, VerifyError, verify_export

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture()
def eps(tmp_path: Path) -> Path:
    root = tmp_path / "eps"
    shutil.copytree(EXAMPLES / "microsat_250kg_eps", root)
    return root


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767323045")
    monkeypatch.setenv("BUDGET_USER", "tester")


def _project(root: Path):  # type: ignore[no-untyped-def]
    project = load_project(root).project
    assert project is not None
    return project


# ---- the manifest ----------------------------------------------------------------------------
def test_the_manifest_lists_every_file_read_with_the_hash_of_its_bytes(eps: Path) -> None:
    project = _project(eps)
    on_disk = sorted(p.relative_to(eps).as_posix() for p in eps.rglob("*.yaml"))
    assert [e.path for e in project.manifest] == on_disk
    for entry in project.manifest:
        raw = (eps / entry.path).read_bytes()
        assert entry.size == len(raw)
        assert entry.sha256 == hashlib.sha256(raw).hexdigest()


def test_a_comment_changes_the_manifest_but_not_the_model_digest(eps: Path) -> None:
    before = _project(eps)
    target = eps / "project.yaml"
    target.write_text("# a comment that carries no number\n" + target.read_text(encoding="utf-8"))
    after = _project(eps)
    assert project_digest(after) == project_digest(before)
    assert files_digest(after.manifest) != files_digest(before.manifest)


def test_key_order_and_spacing_do_not_change_the_model_digest(eps: Path) -> None:
    before = project_digest(_project(eps))
    target = eps / "spacecraft.yaml"
    lines = target.read_text(encoding="utf-8").splitlines()
    head, rest = lines[:2], lines[2:]
    target.write_text("\n".join(head + [""] + rest[::1]) + "\n\n", encoding="utf-8")
    assert project_digest(_project(eps)) == before


def test_a_changed_number_changes_the_model_digest(eps: Path) -> None:
    before = project_digest(_project(eps))
    unit = sorted((eps / "units").glob("*.yaml"))[0]
    text = unit.read_text(encoding="utf-8")
    edited = re.sub(r"mass_kg: [0-9.]+", "mass_kg: 987.5", text, count=1)
    assert edited != text
    unit.write_text(edited, encoding="utf-8")
    assert project_digest(_project(eps)) != before


def test_the_digest_does_not_depend_on_where_the_project_is(eps: Path, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere" / "copy"
    shutil.copytree(eps, other)
    assert project_digest(_project(other)) == project_digest(_project(eps))


def test_the_canonical_form_is_deterministic_and_has_no_path(eps: Path) -> None:
    data = project_data(_project(eps))
    text = canonical_json(data)
    assert text == canonical_json(json.loads(text))
    assert str(eps) not in text


# ---- the provenance ---------------------------------------------------------------------------
def test_the_provenance_rows_name_the_digest_and_the_files(eps: Path) -> None:
    prov = make_provenance(_project(eps))
    rows = dict(prov.rows())
    assert rows["Inputs digest (model)"] == project_digest(_project(eps))
    assert rows["Input files"].startswith(f"{len(prov.input_files)} files, sha256:")


def test_a_provenance_built_by_hand_shows_no_input_rows() -> None:
    prov = Provenance("t", "1", "3.14", (), "p", "1", "static", "2026-01-01T00:00:00Z", "u")
    assert [name for name, _ in prov.rows()] == [
        "Tool",
        "Python",
        "Libraries",
        "Project",
        "Project revision",
        "Scenario",
        "Generated (UTC)",
        "User",
    ]


def test_the_json_export_carries_the_digest_the_files_and_no_local_path(
    eps: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    assert main(["run", str(eps), "--budget", "power", "--report", "json", "--out", str(out)]) == 0
    data = json.loads((out / "power_static.json").read_text(encoding="utf-8"))
    prov = data["provenance"]
    assert prov["inputs_digest"] == project_digest(_project(eps))
    assert [f["path"] for f in prov["input_files"]] == [e.path for e in _project(eps).manifest]
    assert str(eps) not in json.dumps(prov)


def test_a_power_timeline_records_the_options_that_change_its_numbers(
    eps: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    scenario = next((eps / "scenarios").glob("*.yaml")).stem
    code = main(
        [
            "power-timeline",
            str(eps),
            "--scenario",
            scenario,
            "--load-basis",
            "margined",
            "--case",
            "eol",
            "--report",
            "json",
            "--out",
            str(out),
        ]
    )
    assert code in (0, 1)
    path = next(out.glob("*.json"))
    params = dict(json.loads(path.read_text(encoding="utf-8"))["provenance"]["parameters"])
    assert params["Demand basis"] == "margined"
    assert params["Cases"] == "eol"
    assert {"Shadow model", "Step", "Duration", "Start (UTC)", "Mission phase"} <= set(params)


# ---- verify -----------------------------------------------------------------------------------
def _export(eps: Path, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    assert (
        main(
            [
                "run",
                str(eps),
                "--budget",
                "power",
                "--report",
                "json",
                "--report",
                "csv",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    return out


def test_verify_says_match_for_the_project_the_export_came_from(eps: Path, tmp_path: Path) -> None:
    out = _export(eps, tmp_path)
    for name in ("power_static.json", "power_static_provenance.csv"):
        result = verify_export(out / name, eps)
        assert result.status == MATCH, result.lines


def test_verify_names_the_changed_file_when_a_number_changed(eps: Path, tmp_path: Path) -> None:
    out = _export(eps, tmp_path)
    unit = sorted((eps / "units").glob("*.yaml"))[0]
    text = unit.read_text(encoding="utf-8")
    assert "mass_kg: " in text
    unit.write_text(re.sub(r"mass_kg: [0-9.]+", "mass_kg: 987.5", text, count=1), encoding="utf-8")
    result = verify_export(out / "power_static.json", eps)
    assert result.status == DIFFERENT
    assert any(f"units/{unit.name}" in line for line in result.lines)


def test_verify_says_match_but_lists_a_file_that_differs_in_text_only(
    eps: Path, tmp_path: Path
) -> None:
    out = _export(eps, tmp_path)
    target = eps / "project.yaml"
    target.write_text("# edited after the export\n" + target.read_text(encoding="utf-8"))
    result = verify_export(out / "power_static.json", eps)
    assert result.status == MATCH
    assert any("project.yaml" in line and "text only" in line for line in result.lines)


def test_verify_cannot_check_an_export_without_a_digest(eps: Path, tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"provenance": {"tool_version": "1.7.0"}}), encoding="utf-8")
    assert verify_export(old, eps).status == UNKNOWN


def test_verify_refuses_files_that_are_not_exports(eps: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(VerifyError):
        verify_export(bad, eps)
    other = tmp_path / "other.json"
    other.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(VerifyError):
        verify_export(other, eps)


def test_verify_reports_a_project_that_does_not_load(eps: Path, tmp_path: Path) -> None:
    out = _export(eps, tmp_path)
    (eps / "spacecraft.yaml").write_text("kind: spacecraft\n: broken\n", encoding="utf-8")
    result = verify_export(out / "power_static.json", eps)
    assert result.status == UNKNOWN and "cannot be loaded" in result.lines[0]


def test_the_command_exits_0_for_a_match_1_for_a_difference_2_for_a_bad_file(
    eps: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _export(eps, tmp_path)
    capsys.readouterr()
    assert main(["verify", str(out / "power_static.json"), str(eps)]) == 0
    assert "MATCH" in capsys.readouterr().out
    other = tmp_path / "other"
    shutil.copytree(EXAMPLES / "microsat_150kg", other)
    assert main(["verify", str(out / "power_static.json"), str(other)]) == 1
    assert "DIFFERENT" in capsys.readouterr().out
    nothing = tmp_path / "missing.json"
    assert main(["verify", str(nothing), str(eps)]) == 2


# ---- the result envelope (D-205) ---------------------------------------------------------------
def test_every_json_result_names_its_format_and_kind(eps: Path, tmp_path: Path) -> None:
    from budget_core.result_format import KINDS, RESULT_FORMAT_NAME, RESULT_FORMAT_VERSION

    out = tmp_path / "out"
    scenario = next((eps / "scenarios").glob("*.yaml")).stem
    for budget in ("power", "mass", "thermal", "link"):
        main(["run", str(eps), "--budget", budget, "--report", "json", "--out", str(out)])
    main(["scenario", str(eps), "--scenario", scenario, "--out", str(out)])
    main(
        ["power-timeline", str(eps), "--scenario", scenario, "--report", "json", "--out", str(out)]
    )
    main(["link-passes", str(eps), "--scenario", scenario, "--report", "json", "--out", str(out)])
    main(["compare", str(eps), str(eps), "--report", "json", "--out", str(out)])
    seen = set()
    for path in sorted(out.glob("*.json")):
        fmt = json.loads(path.read_text(encoding="utf-8"))["result_format"]
        assert fmt["name"] == RESULT_FORMAT_NAME and fmt["version"] == RESULT_FORMAT_VERSION
        seen.add(fmt["kind"])
    assert seen == set(KINDS)


def test_the_format_page_describes_every_kind() -> None:
    from budget_core.result_format import KINDS

    page = (Path(__file__).resolve().parents[2] / "docs" / "RESULT_FORMAT.md").read_text(
        encoding="utf-8"
    )
    for kind in KINDS:
        assert f"| `{kind}` |" in page, kind


def test_a_comparison_names_the_inputs_of_both_sides(eps: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    shutil.copytree(EXAMPLES / "microsat_150kg", other)
    out = tmp_path / "out"
    main(["compare", str(eps), str(other), "--report", "json", "--out", str(out)])
    data = json.loads((out / "compare.json").read_text(encoding="utf-8"))
    params = dict(data["provenance"]["parameters"])
    assert params["Side A inputs digest"] == project_digest(_project(eps))
    assert params["Side B inputs digest"] == project_digest(_project(other))
