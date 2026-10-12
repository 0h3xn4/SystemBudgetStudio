"""Audit MI-11 (ignored files, derived errors) and MI-12 (ids from file names)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.problems import Problem, Severity
from tests.helpers import write_valid_project


@pytest.fixture
def root(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "p")
    return tmp_path / "p"


def codes(problems: list[Problem], code: str) -> list[Problem]:
    return [p for p in problems if p.code == code]


# ---- MI-11 -----------------------------------------------------------------------------------
def test_a_clean_project_has_no_ignored_file_warning(root: Path) -> None:
    (root / "README.md").write_text("notes\n", encoding="utf-8")
    (root / "results").mkdir()
    (root / "results" / "x.yaml").write_text("a: 1\n", encoding="utf-8")
    (root / "units" / ".hidden.yml").write_text("a: 1\n", encoding="utf-8")
    (root / "units" / "notes.txt").write_text("a\n", encoding="utf-8")
    assert not codes(load_project(root).problems, "FILE_IGNORED")


def test_look_alike_project_files_are_reported_as_ignored(root: Path) -> None:
    shutil.copy(root / "units" / "obc.yaml", root / "units" / "camera.yml")
    shutil.copy(root / "units" / "obc.yaml", root / "units" / "Radio2.YAML")
    (root / "modes" / "sub").mkdir()
    shutil.copy(root / "modes" / "nominal.yaml", root / "modes" / "sub" / "x.yaml")
    shutil.copy(root / "project.yaml", root / "other.yaml")
    shutil.copy(root / "config" / "power_config.yaml", root / "config" / "power_confg.yaml")
    result = load_project(root)
    ignored = {p.file: p for p in codes(result.problems, "FILE_IGNORED")}
    assert set(ignored) == {
        "units/camera.yml",
        "units/Radio2.YAML",
        "modes/sub",
        "other.yaml",
        "config/power_confg.yaml",
    }
    assert all(p.severity is Severity.WARNING and p.hint for p in ignored.values())
    assert result.project is not None  # a warning only


def test_a_broken_unit_does_not_cascade_into_unknown_unit_errors(root: Path) -> None:
    (root / "units" / "obc.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    problems = load_project(root).problems
    assert [p.code for p in problems if p.file == "units/obc.yaml"] == ["YAML_SYNTAX"]
    assert not codes(problems, "REF_UNKNOWN_UNIT")
    assert not codes(problems, "UNIT_NOT_MAPPED")


def test_a_missing_unit_is_still_reported(root: Path) -> None:
    (root / "units" / "obc.yaml").unlink()
    problems = load_project(root).problems
    assert len(codes(problems, "REF_UNKNOWN_UNIT")) == 2  # both modes name it


def test_a_broken_mode_orbit_and_site_do_not_cascade(root: Path) -> None:
    (root / "modes" / "downlink.yaml").write_text("name: [x\n", encoding="utf-8")
    (root / "orbits" / "leo.yaml").write_text("name: [x\n", encoding="utf-8")
    (root / "ground_stations" / "gs1.yaml").write_text("name: [x\n", encoding="utf-8")
    problems = load_project(root).problems
    for code in ("REF_UNKNOWN_MODE", "REF_UNKNOWN_ORBIT", "REF_UNKNOWN_SITE"):
        assert not codes(problems, code), code


# ---- MI-12 -----------------------------------------------------------------------------------
def test_ids_with_spaces_or_accents_load_with_a_warning(root: Path) -> None:
    shutil.copy(root / "units" / "obc.yaml", root / "units" / "main computer.yaml")
    shutil.copy(root / "units" / "obc.yaml", root / "units" / "obcé.yaml")
    result = load_project(root)
    unusual = {p.file for p in codes(result.problems, "ID_UNUSUAL")}
    assert unusual == {"units/main computer.yaml", "units/obcé.yaml"}
    assert all(p.severity is Severity.WARNING for p in codes(result.problems, "ID_UNUSUAL"))
    assert not codes(result.problems, "ID_INVALID")  # usable, only unusual
    assert not codes(result.problems, "FILE_INVALID")


def test_unicode_normalisation_and_case_twins_are_warned(root: Path) -> None:
    for name in ("café", "café", "Radio", "radio"):
        shutil.copy(root / "units" / "obc.yaml", root / "units" / f"{name}.yaml")
    clashing = {p.file for p in codes(load_project(root).problems, "ID_COLLISION")}
    # on a case-insensitive file system "Radio" and "radio" are one file; either way no error
    assert {"units/café.yaml", "units/café.yaml"} <= clashing
    assert all(
        p.severity is Severity.WARNING for p in codes(load_project(root).problems, "ID_COLLISION")
    )


def test_a_hidden_id_is_an_error(root: Path) -> None:
    shutil.copy(root / "units" / "obc.yaml", root / "units" / ".secret.yaml")
    shutil.copy(root / "units" / "obc.yaml", root / "units" / ".yaml")
    problems = codes(load_project(root).problems, "ID_INVALID")
    assert {p.file for p in problems} == {"units/.secret.yaml", "units/.yaml"}
    assert all(p.severity is Severity.ERROR for p in problems)


@pytest.mark.skipif(sys.platform == "win32", reason="needs a file name that is not valid UTF-8")
def test_an_undecodable_file_name_is_an_error_not_a_crash(root: Path) -> None:
    bad = os.fsencode(root / "units") + b"/bad\xff\xfename.yaml"
    try:
        with open(bad, "wb") as handle:
            handle.write(b"name: x\n")
    except OSError:
        pytest.skip("this file system refuses such names")
    result = load_project(root)
    problem = codes(result.problems, "ID_INVALID")[0]
    assert problem.severity is Severity.ERROR
    problem.file.encode("ascii") if problem.file else None  # printable without an encoding error
    assert result.project is None
