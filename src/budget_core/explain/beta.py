"""Explanations of the node temperatures against the beta angle (2.9.0, D-252).

The table of a sweep (`thermal_beta_sweep`) has a row for each beta angle and, in it, the sunlit
part of the orbit, the orbit angle of the worst instant (peak mode), the temperature of every node,
the number of units beyond a limit and the smallest margin to a limit. A cell is explained by
solving its angle again with the code the sweep itself uses (`beta_point_detail`) and showing the
steps that lead to it: the sunlit part of the orbit (TH-BETA-LIT), the solar exposure of every
surface that gives its direction (TH-BETA-SUN), and then the steps of the ordinary static thermal
explanation, which are taken from `explain/thermal.py` unchanged: the solar view of such a surface
is the result of the exposure step, so the heat it absorbs, the heat balance of the node and the
check against the limits follow from the beta angle and the orbit, not from a typed ratio.

The orbit (Earth radius, orbit radius) is the sweep's: it is not a file of the project but the
scenario's orbit or the altitude that was typed, and the explanation says so. Nothing here computes
a physical quantity that the solver does not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from budget_core.explain.power import ExplainError
from budget_core.explain.sources import add_sources
from budget_core.explain.thermal import MODEL_FILE, thermal_cell_steps
from budget_core.explain.trace import Explanation, Quantity, Step, equations_used, link_steps
from budget_core.model import Project
from budget_core.thermal.beta import face_exposure
from budget_core.thermal.beta_sweep import BetaDetail, BetaPoint, BetaSweep, beta_point_detail

TABLE_PREFIX = "thermal-beta"
BETA_COLUMN = "Beta (deg)"
SUNLIT_COLUMN = "Sunlit (%)"
ORBIT_ANGLE_COLUMN = "Orbit angle (deg)"
EXCEEDED_COLUMN = "Units beyond a limit"
HEADROOM_COLUMN = "Smallest margin to a limit (K)"
ORBIT_ORIGIN = "the orbit of the sweep (see the note below)"
ORBIT_NOTE = (
    "The orbit is the sweep's, not a file of the project: the scenario's orbit (the mean radius "
    "of its propagated positions, taken as a circle) or the altitude typed for the sweep, with the "
    "Earth radius of the scenario's Earth model."
)
ANGLE_TOLERANCE_DEG = 0.05  # a row is named by its angle as the table shows it (one decimal)

Cell = tuple[list[Step], Quantity]


def beta_table_id(sweep: BetaSweep) -> str:
    return f"{TABLE_PREFIX}:{sweep.case}:{sweep.mode}"


def beta_columns(sweep: BetaSweep) -> list[str]:
    """The columns of the sweep's table, as the window and this explanation name them."""
    nodes = sorted({n.node for p in sweep.points for n in p.case.nodes})
    return [
        BETA_COLUMN,
        SUNLIT_COLUMN,
        ORBIT_ANGLE_COLUMN,
        *(node_column(n) for n in nodes),
        EXCEEDED_COLUMN,
        HEADROOM_COLUMN,
    ]


def node_column(node: str) -> str:
    return f"{node} (K)"


def beta_row_key(point: BetaPoint) -> str:
    """The first cell of the row, which names it."""
    return f"{point.beta_deg:+.1f}"


# ---- quantities shared by the steps -----------------------------------------------------------
def _beta(point: BetaPoint) -> Quantity:
    return Quantity("beta angle", point.beta_deg, "deg", "this row of the sweep")


def _earth(sweep: BetaSweep) -> Quantity:
    return Quantity("Earth radius", sweep.earth_radius_m, "m", ORBIT_ORIGIN)


def _orbit(sweep: BetaSweep) -> Quantity:
    return Quantity("orbit radius", sweep.orbit_radius_m, "m", ORBIT_ORIGIN)


def _sunlit_cell(sweep: BetaSweep, point: BetaPoint) -> Cell:
    fraction = Step(
        "Sunlit part of the orbit",
        (_beta(point), _earth(sweep), _orbit(sweep)),
        Quantity("sunlit fraction of the orbit", point.sunlit_fraction, "ratio", "this step"),
        "TH-BETA-LIT",
        "The part of a circular orbit outside the cylindrical shadow of the Earth: 1 when the "
        "orbit never enters the shadow.",
    )
    percent = Step(
        "Sunlit part of the orbit as a percentage",
        (fraction.result,),
        Quantity("sunlit part of the orbit", point.sunlit_fraction * 100.0, "%", "this step"),
        logic="The fraction times 100 (the table shows it with one decimal).",
    )
    return [fraction, percent], percent.result


def _weights(project: Project, detail: BetaDetail) -> list[Quantity]:
    """Absorptivity times area of each surface that takes its exposure from the beta angle: the
    weights of the peak instant."""
    model = project.config.thermal_model
    assert model is not None
    out: list[Quantity] = []
    for index, _view in detail.surfaces:
        s = model.surfaces[index]
        alpha = s.absorptivity_ratio
        value = None if alpha is None or alpha.is_placeholder else alpha.value
        out.append(
            Quantity(
                f"absorptivity x area of {s.name}",
                None if value is None else float(value) * s.area_m2,
                "m2",
                f"{MODEL_FILE} surfaces[{index}].absorptivity_ratio x area_m2",
            )
        )
    return out


def _orbit_angle_cell(
    project: Project, sweep: BetaSweep, point: BetaPoint, detail: BetaDetail
) -> Cell:
    if sweep.mode != "peak" or point.u_deg is None:
        raise ExplainError(
            "The orbit-average mode has no orbit angle: it averages over the whole orbit."
        )
    step = Step(
        "Orbit angle of the worst instant",
        (_beta(point), _earth(sweep), _orbit(sweep), *_weights(project, detail)),
        Quantity("orbit angle of the worst instant", point.u_deg, "deg", "this step"),
        logic="On the sunlit arc, the orbit angle from noon at which the sum of the exposures of "
        "the faces, each weighted by its absorptivity times its area, is largest: found on a "
        "fine grid and refined by golden-section search, as the sweep does it.",
    )
    return [step], step.result


def _exposure_steps(
    project: Project,
    sweep: BetaSweep,
    point: BetaPoint,
    detail: BetaDetail,
    node: str | None = None,
) -> list[Step]:
    """One step for each surface that takes its solar view from the beta angle (only those of
    `node` when it is given)."""
    model = project.config.thermal_model
    assert model is not None
    steps: list[Step] = []
    for index, view in detail.surfaces:
        s = model.surfaces[index]
        if node is not None and s.node != node:
            continue
        normal = s.normal_lvlh or (0.0, 0.0, 0.0)
        path = f"{MODEL_FILE} surfaces[{index}].normal_lvlh"
        axes = tuple(
            Quantity(f"{axis} component of the normal of {s.name}", float(normal[k]), "", path)
            for k, axis in enumerate(("x", "y", "z"))
        )
        if sweep.mode == "average":
            value = face_exposure(
                normal, point.beta_deg, sweep.earth_radius_m, sweep.orbit_radius_m
            ).average
            extra: tuple[Quantity, ...] = ()
            logic = (
                "The orbit average of max(0, n . s) over the whole orbit, the eclipse counted as "
                "zero: this is the solar view ratio of the surface for the sweep."
            )
        else:
            value = view  # the solver's own value at the worst instant (rounding as it made it)
            u = Quantity(
                "orbit angle of the worst instant",
                point.u_deg,
                "deg",
                f"column {ORBIT_ANGLE_COLUMN} of this row (explain it with the same row)",
            )
            extra = (u,)
            logic = (
                "max(0, n . s) at the orbit angle of the worst instant: the solar view ratio of "
                "the surface for the sweep."
            )
        steps.append(
            Step(
                f"Solar exposure of surface {s.name}",
                (*axes, _beta(point), _earth(sweep), _orbit(sweep), *extra),
                Quantity(f"solar view of {s.name}", value, "ratio", "this step"),
                "TH-BETA-SUN",
                logic,
            )
        )
    return steps


def _temperature_cell(
    project: Project, sweep: BetaSweep, point: BetaPoint, detail: BetaDetail, node: str
) -> Cell:
    if node not in {n.node for n in point.case.nodes} and point.case.complete:
        raise ExplainError("There is no such node in this sweep.")
    exposure = _exposure_steps(project, sweep, point, detail, node)
    case_table = f"thermal:temperatures:{sweep.case}"
    steps, final, _title = thermal_cell_steps(
        detail.trial, case_table, [node], "Temperature (K)", detail.result
    )
    return [*exposure, *steps], final


def _limit_status_steps(
    detail: BetaDetail, case: str, column: str
) -> tuple[list[Step], list[Quantity]]:
    """The limit check of every unit for `column` (a status or a headroom), one step each, and
    the checked values in the same order."""
    steps: list[Step] = []
    values: list[Quantity] = []
    checks = next(c for c in detail.result.cases if c.case == case).checks
    for check in checks:
        got, final, _title = thermal_cell_steps(
            detail.trial, f"thermal:limits:{case}", [check.unit_id], column, detail.result
        )
        steps.extend(got)
        values.append(
            Quantity(
                f"{column.replace(' (K)', '').lower()} of {check.unit_id}",
                final.value,
                final.unit,
                "step above",
            )
        )
    return steps, values


def _not_computed(
    project: Project, sweep: BetaSweep, detail: BetaDetail, what: str, column: str
) -> Cell:
    """The case could not be solved at this angle: the explanation of any node's temperature says
    which inputs are placeholders."""
    first = detail.result.cases[0].nodes[0].node if detail.result.cases[0].nodes else ""
    key = [first] if first else ["-"]
    steps, _final, _title = thermal_cell_steps(
        detail.trial, f"thermal:temperatures:{sweep.case}", key, "Temperature (K)", detail.result
    )
    return steps, Quantity(what, None, "", "this step")


def _exceeded_cell(
    project: Project, sweep: BetaSweep, point: BetaPoint, detail: BetaDetail
) -> Cell:
    if not point.case.complete:
        return _not_computed(project, sweep, detail, "units beyond a limit", EXCEEDED_COLUMN)
    exposure = _exposure_steps(project, sweep, point, detail)
    steps, statuses = _limit_status_steps(detail, sweep.case, "Status")
    count = sum(1 for q in statuses if q.value == "exceeded")
    final = Step(
        "Units beyond a limit",
        tuple(statuses),
        Quantity("units beyond a limit", float(count), "", "this step"),
        logic="The number of units whose status is exceeded: a temperature below the lower or "
        "above the upper limit of the set the case uses.",
    )
    return [*exposure, *_node_steps(project, sweep, point, detail), *steps, final], final.result


def _node_steps(
    project: Project, sweep: BetaSweep, point: BetaPoint, detail: BetaDetail
) -> list[Step]:
    """The temperatures of all nodes at this angle: one step, the solver's result, with the
    inputs the nodes were found from (every node's own explanation lists the terms)."""
    nodes = [n for n in point.case.nodes]
    members = tuple(
        Quantity(
            f"temperature of node {n.node}",
            n.temperature_k,
            "K",
            f"column {node_column(n.node)} of this row (explain it with the same row)",
        )
        for n in nodes
    )
    if not members:
        return []
    return [
        Step(
            "Temperatures of the nodes at this angle",
            members,
            Quantity("temperatures of the nodes", float(len(members)), "nodes", "this step"),
            "TH-BAL",
            "Each node's temperature is the solver's result of the steady-state heat balance "
            "with the solar views above; explain a node's column of this row for its terms.",
        )
    ]


def _headroom_cell(
    project: Project, sweep: BetaSweep, point: BetaPoint, detail: BetaDetail
) -> Cell:
    if not point.case.complete:
        return _not_computed(project, sweep, detail, "smallest margin", HEADROOM_COLUMN)
    exposure = _exposure_steps(project, sweep, point, detail)
    steps: list[Step] = []
    values: list[Quantity] = []
    for column in ("Headroom to lower (K)", "Headroom to upper (K)"):
        got, quantities = _limit_status_steps(detail, sweep.case, column)
        steps.extend(got)
        values.extend(q for q in quantities if q.value is not None)
    floats = [float(q.value) for q in values if isinstance(q.value, float)]
    smallest = min(floats) if floats else None
    final = Step(
        "Smallest margin to a limit",
        tuple(values),
        Quantity("smallest margin to a limit", smallest, "K", "this step"),
        logic="The smallest of the headrooms of every unit to its lower and upper limit; a "
        "negative value is a unit beyond a limit. n/a when no unit has a limit.",
    )
    return [*exposure, *_node_steps(project, sweep, point, detail), *steps, final], final.result


# ---- entry point -------------------------------------------------------------------------------
def explain_beta(
    project: Project, sweep: BetaSweep, key: Sequence[str], column: str
) -> Explanation:
    """How one cell of the table of `sweep` was obtained. `key` is the row: its beta angle, as
    the table shows it (the first cell); `column` is the column header."""
    if len(key) != 1:
        raise ExplainError("Name the row by its beta angle.")
    try:
        angle = float(key[0])
    except ValueError as exc:
        raise ExplainError("The row is named by its beta angle, in degrees.") from exc
    point = next((p for p in sweep.points if abs(p.beta_deg - angle) <= ANGLE_TOLERANCE_DEG), None)
    if point is None:
        raise ExplainError("The sweep has no such beta angle.")
    nodes = {n.node for p in sweep.points for n in p.case.nodes}
    node_columns = {node_column(n): n for n in nodes}
    if column not in beta_columns(sweep):
        raise ExplainError("This column is not explained.")
    detail = beta_point_detail(project, sweep, point.beta_deg)
    if column == BETA_COLUMN:
        step = Step(
            "Read from the sweep",
            (),
            _beta(point),
            logic="Not computed: the angle this row of the sweep was solved at.",
        )
        steps, final = [step], step.result
    elif column == SUNLIT_COLUMN:
        steps, final = _sunlit_cell(sweep, point)
    elif column == ORBIT_ANGLE_COLUMN:
        steps, final = _orbit_angle_cell(project, sweep, point, detail)
    elif column == EXCEEDED_COLUMN:
        steps, final = _exceeded_cell(project, sweep, point, detail)
    elif column == HEADROOM_COLUMN:
        steps, final = _headroom_cell(project, sweep, point, detail)
    else:
        steps, final = _temperature_cell(project, sweep, point, detail, node_columns[column])
    linked = link_steps(tuple(steps))
    mode = "orbit average" if sweep.mode == "average" else "worst instant"
    title = f"Beta sweep, case {sweep.case} ({mode}) / {beta_row_key(point)} / {column}"
    explanation = Explanation(
        (beta_table_id(sweep), (key[0],), column),
        title,
        replace(final, origin=""),
        linked,
        notes=(
            ORBIT_NOTE,
            "The orbit is circular and the spacecraft points to nadir, the faces are flat and "
            "there is no thermal capacity (steady state): see DEVIATIONS DV-T4 and DV-T5. The "
            "Earth view and the albedo of each surface are the typed ones.",
        ),
        equations=equations_used(linked),
    )
    return add_sources(project, explanation)


__all__ = [
    "beta_columns",
    "beta_row_key",
    "beta_table_id",
    "explain_beta",
    "node_column",
]
