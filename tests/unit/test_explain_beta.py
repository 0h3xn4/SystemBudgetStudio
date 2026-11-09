# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Explain for the beta sweep (D-252): every cell of the table has an explanation whose result is
the number the table shows, and the solar view of a surface that takes it from the beta angle is
the result of an exposure step, not a typed ratio."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from budget_core.environment.constants import EARTH_MODELS
from budget_core.explain import ExplainError, Explanation, explain_beta
from budget_core.explain.beta import (
    BETA_COLUMN,
    EXCEEDED_COLUMN,
    HEADROOM_COLUMN,
    ORBIT_ANGLE_COLUMN,
    SUNLIT_COLUMN,
    beta_columns,
    beta_row_key,
    node_column,
)
from budget_core.io.project_loader import load_project
from budget_core.model import Project, Sourced
from budget_core.thermal.beta import face_exposure
from budget_core.thermal.beta_sweep import (
    BetaSweep,
    Mode,
    node_temperatures,
    thermal_beta_sweep,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
RE = EARTH_MODELS["wgs84"].radius_m
ORBIT = RE + 550_000.0
BETAS = [-60.0, 0.0, 30.0, 75.0]


@pytest.fixture(scope="module")
def project() -> Project:
    loaded = load_project(EXAMPLES / "microsat_250kg_clean").project
    assert loaded is not None
    return loaded


def _sweep(project: Project, mode: Mode) -> BetaSweep:
    return thermal_beta_sweep(
        project,
        "hot",
        BETAS,
        mode=mode,
        earth_radius_m=RE,
        orbit_radius_m=ORBIT,
    )


def _headroom(point: object) -> float | None:
    values = [
        v
        for c in point.case.checks  # type: ignore[attr-defined]
        for v in (c.lower_headroom_k, c.upper_headroom_k)
        if v is not None
    ]
    return min(values) if values else None


@pytest.mark.parametrize("mode", ["average", "peak"])
def test_every_cell_of_the_table_is_explained_with_the_value_it_shows(
    project: Project, mode: Mode
) -> None:
    sweep = _sweep(project, mode)
    for point in sweep.points:
        key = [beta_row_key(point)]
        temps = node_temperatures(point)
        expected: dict[str, float | None] = {
            BETA_COLUMN: point.beta_deg,
            SUNLIT_COLUMN: point.sunlit_fraction * 100.0,
            ORBIT_ANGLE_COLUMN: point.u_deg,
            EXCEEDED_COLUMN: float(sum(1 for c in point.case.checks if c.status == "exceeded")),
            HEADROOM_COLUMN: _headroom(point),
            **{node_column(n): t for n, t in temps.items()},
        }
        for column in beta_columns(sweep):
            if column == ORBIT_ANGLE_COLUMN and mode == "average":
                with pytest.raises(ExplainError, match="no orbit angle"):
                    explain_beta(project, sweep, key, column)
                continue
            explanation = explain_beta(project, sweep, key, column)
            assert explanation.result.value is not None, column
            assert math.isclose(
                float(explanation.result.value), float(expected[column] or 0.0), abs_tol=1e-6
            ), (point.beta_deg, column)
            assert explanation.steps


def test_the_solar_view_of_a_surface_comes_from_the_exposure_step(project: Project) -> None:
    sweep = _sweep(project, "average")
    point = sweep.points[2]  # +30
    explanation = explain_beta(project, sweep, ["+30.0"], node_column("ADCS"))
    exposure = [s for s in explanation.steps if s.equation_id == "TH-BETA-SUN"]
    assert [s.result.name for s in exposure] == ["solar view of ADCS panel"]
    expected = face_exposure((0.0, 0.0, -1.0), 30.0, RE, ORBIT).average
    assert exposure[0].result.value == pytest.approx(expected)
    number = explanation.steps.index(exposure[0]) + 1
    absorbed = next(s for s in explanation.steps if s.equation_id == "TH-ABS")
    view = next(q for q in absorbed.inputs if q.name == "solar view of ADCS panel")
    assert view.origin == f"result of step {number}"
    assert view.value == exposure[0].result.value
    assert point.solar_view["ADCS panel"] == exposure[0].result.value
    assert {e.id for e in explanation.equations} >= {"TH-BETA-SUN", "TH-ABS", "TH-BAL"}


def test_a_node_is_explained_with_its_own_surfaces_only(project: Project) -> None:
    sweep = _sweep(project, "average")
    explanation = explain_beta(project, sweep, ["0"], node_column("EPS"))
    names = [s.result.name for s in explanation.steps if s.equation_id == "TH-BETA-SUN"]
    assert names == ["solar view of EPS panel"]


def test_the_sunlit_part_cites_its_equation_and_the_orbit(project: Project) -> None:
    sweep = _sweep(project, "average")
    explanation = explain_beta(project, sweep, ["0.0"], SUNLIT_COLUMN)
    assert explanation.steps[0].equation_id == "TH-BETA-LIT"
    names = {q.name for q in explanation.steps[0].inputs}
    assert names == {"beta angle", "Earth radius", "orbit radius"}
    assert explanation.steps[0].result.value == pytest.approx(
        1.0 - math.asin(RE / ORBIT) / math.pi, abs=1e-9
    )
    assert any("not a file of the project" in n for n in explanation.notes)


def test_the_peak_angle_names_the_weights(project: Project) -> None:
    sweep = _sweep(project, "peak")
    explanation = explain_beta(project, sweep, ["+30.0"], ORBIT_ANGLE_COLUMN)
    (step,) = explanation.steps
    weights = [q.name for q in step.inputs if q.name.startswith("absorptivity x area of")]
    assert len(weights) == 7
    assert step.result.value == pytest.approx(sweep.points[2].u_deg)


def test_a_surface_without_a_direction_keeps_its_typed_solar_view(project: Project) -> None:
    model = project.config.thermal_model
    assert model is not None
    surfaces = [
        s.model_copy(update={"normal_lvlh": None}) if i == 0 else s
        for i, s in enumerate(model.surfaces)
    ]
    config = replace(project.config, thermal_model=model.model_copy(update={"surfaces": surfaces}))
    typed = replace(project, config=config)
    sweep = _sweep(typed, "average")
    explanation = explain_beta(typed, sweep, ["+30.0"], node_column("ADCS"))
    assert not [s for s in explanation.steps if s.equation_id == "TH-BETA-SUN"]
    absorbed = next(s for s in explanation.steps if s.equation_id == "TH-ABS")
    view = next(q for q in absorbed.inputs if q.name == "solar view of ADCS panel")
    assert view.origin.startswith("config/thermal_model.yaml surfaces[0].exposure.hot")


def test_a_placeholder_gives_n_a_and_names_the_input(project: Project) -> None:
    model = project.config.thermal_model
    assert model is not None
    surfaces = list(model.surfaces)
    exposure = dict(surfaces[1].exposure)
    exposure["hot"] = exposure["hot"].model_copy(
        update={"earth_view_ratio": Sourced(value=None, source="TBD")}
    )
    surfaces[1] = surfaces[1].model_copy(update={"exposure": exposure})
    config = replace(project.config, thermal_model=model.model_copy(update={"surfaces": surfaces}))
    gapped = replace(project, config=config)
    sweep = _sweep(gapped, "average")
    assert not sweep.points[0].case.complete
    assert node_column("ADCS") not in beta_columns(sweep)  # no node has a temperature
    for column in (EXCEEDED_COLUMN, HEADROOM_COLUMN):
        explanation = explain_beta(gapped, sweep, ["+30.0"], column)
        assert not explanation.complete
        text = explanation.format_text()
        assert "placeholder" in text.lower() or "not computed" in text.lower()


@pytest.mark.parametrize(
    ("key", "column", "message"),
    [
        (["+30.0", "x"], "Sunlit (%)", "Name the row"),
        (["abc"], "Sunlit (%)", "beta angle"),
        (["12.0"], "Sunlit (%)", "no such beta angle"),
        (["+30.0"], "Nope (K)", "not explained"),
    ],
)
def test_a_wrong_address_is_refused_in_words(
    project: Project, key: list[str], column: str, message: str
) -> None:
    with pytest.raises(ExplainError, match=message):
        explain_beta(project, _sweep(project, "average"), key, column)


def test_an_explanation_is_serialisable(project: Project) -> None:
    explanation = explain_beta(project, _sweep(project, "average"), ["+30.0"], node_column("DH"))
    assert isinstance(explanation, Explanation)
    data = explanation.to_dict()
    assert data["address"]["table"] == "thermal-beta:hot:average"
    assert data["complete"] is True
    assert "Step 1" in explanation.format_text()
