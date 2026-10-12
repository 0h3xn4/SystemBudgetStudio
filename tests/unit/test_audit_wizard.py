"""Audit MI-19 / MI-8 for the guided-mode wizard."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_core.io.project_loader import load_project
from budget_core.problems import Severity
from budget_core.wizard import (
    SAMPLES,
    WizardAnswers,
    WizardError,
    check_answers,
    create_project,
    folder_name,
)


def answers(**kw: object) -> WizardAnswers:
    base = {"project_name": "My first satellite", "sample": "cubesat_3u_eps"}
    return WizardAnswers(**{**base, **kw})  # type: ignore[arg-type]


def errors_of(folder: Path) -> list[str]:
    return [p.format() for p in load_project(folder).problems if p.severity is Severity.ERROR]


@pytest.mark.parametrize("sample", sorted(SAMPLES))
@pytest.mark.parametrize("days", [0.0001, 0.001, 0.01, 0.0208, 0.03])
def test_a_short_duration_is_refused_by_name_or_gives_a_loadable_project(
    sample: str, days: float, tmp_path: Path
) -> None:
    issues = check_answers(answers(sample=sample, duration_days=days))
    if issues:
        assert any(i.field == "duration_days" for i in issues)
        with pytest.raises(WizardError):
            create_project(answers(sample=sample, duration_days=days), tmp_path)
        assert list(tmp_path.iterdir()) == []
    else:
        folder = create_project(answers(sample=sample, duration_days=days), tmp_path)
        assert errors_of(folder) == []


def test_the_duration_message_says_how_long_it_must_be() -> None:
    (issue,) = [
        i for i in check_answers(answers(duration_days=0.0001)) if i.field == "duration_days"
    ]
    assert "at least" in issue.message and "days" in issue.message


def test_the_microsat_sample_needs_room_for_its_manual_segments() -> None:
    issues = check_answers(answers(sample="microsat_150kg", duration_days=0.01))
    assert any(i.field == "duration_days" for i in issues)


@pytest.mark.parametrize(
    "start",
    [
        "0001-01-01T00:00:00Z",
        "9999-12-31T23:59:59Z",
        "1900-01-01T00:00:00Z",
        "2101-01-01T00:00:00Z",
        "0001-01-01T00:00:00+05:00",
        "9999-12-31T23:59:59-05:00",
    ],
)
def test_start_dates_outside_1950_to_2100_are_an_answer_error(start: str, tmp_path: Path) -> None:
    assert any(i.field == "start_utc" for i in check_answers(answers(start_utc=start)))
    with pytest.raises(WizardError):
        create_project(answers(start_utc=start), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_scenario_that_would_end_after_2100_is_refused(tmp_path: Path) -> None:
    issues = check_answers(answers(start_utc="2100-12-31T00:00:00Z", duration_days=30.0))
    assert any(i.field in ("start_utc", "duration_days") for i in issues)


@pytest.mark.parametrize("start", ["1950-01-01T00:00:00Z", "2026-06-01", "2026-06-01 00:00"])
def test_edge_and_loose_dates_still_work(start: str, tmp_path: Path) -> None:
    folder = create_project(answers(start_utc=start), tmp_path)
    assert errors_of(folder) == []


def test_a_long_name_gives_a_short_folder(tmp_path: Path) -> None:
    folder = create_project(answers(project_name="x" * 400), tmp_path)
    assert len(folder.name) <= 60 and errors_of(folder) == []


def test_slug_is_cut_at_a_hyphen_boundary_when_possible() -> None:
    slug = folder_name("word " * 60)
    assert len(slug) <= 60 and not slug.endswith("-") and not slug.startswith("-")


@pytest.mark.parametrize(
    "name",
    ["CON", "con", "NUL", "aux", "Prn", "COM1", "lpt9", "con.", "  con  "],
)
def test_windows_device_names_are_not_folder_names(name: str) -> None:
    slug = folder_name(name)
    assert slug not in {"con", "nul", "aux", "prn", "com1", "lpt9"}
    assert slug.startswith("project-")


def test_ordinary_names_are_unchanged() -> None:
    assert folder_name("Console") == "console"
    assert folder_name("My first satellite!") == "my-first-satellite"
    assert folder_name("   ") == "project"


def test_nothing_unexpected_escapes_create_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import budget_core.wizard as wizard

    def boom(*_args: object, **_kw: object) -> None:
        raise OverflowError("date value out of range")

    monkeypatch.setattr(wizard, "write_project", boom)
    with pytest.raises(WizardError):
        create_project(answers(), tmp_path)
    assert list(tmp_path.iterdir()) == []  # no half-written project folder is left behind


def test_a_failed_write_removes_what_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import budget_core.wizard as wizard

    real = wizard.write_project

    def partial(project: object, root: Path) -> None:
        real(project, root)  # type: ignore[arg-type]
        raise OSError("disk full")

    monkeypatch.setattr(wizard, "write_project", partial)
    with pytest.raises(WizardError):
        create_project(answers(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_scenario_is_built_through_validation(tmp_path: Path) -> None:
    folder = create_project(answers(duration_days=2.0), tmp_path)
    project = load_project(folder).project
    assert project is not None
    scenario = next(iter(project.scenarios.values()))
    assert scenario.duration_s == 2 * 86400.0 and scenario.step_s <= scenario.duration_s
