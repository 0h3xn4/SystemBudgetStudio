"""The registry of the modelling choices of the tool (D-219).

A model choice is a place where the result depends on a modelling decision a reviewer could
reasonably make differently. Each entry says what the choice is, which alternatives exist, what
the default is (the behaviour of every project that does not say), where the choice is made, and
the equations and sources of each alternative. A choice is selectable only when a defensible
alternative with a citable source exists (`docs/transparency_p5_design.md`, section 2); every
other model is registered as fixed, with the reason, so that none is hidden.

Scopes:
- `scenario`: a field of the scenario file (`field`); two scenarios can use two models;
- `run`: an option of a run (`field` is the option); it is recorded in the run parameters;
- `fixed`: not selectable in this version; `reference` says why and where it is described.

Nothing here reads a project and nothing here changes a result: the solvers keep their own
branches, and tests bind every entry to the field or option it names.
"""

from __future__ import annotations

from dataclasses import dataclass

from budget_core.equations import EQUATIONS

SCOPES = ("scenario", "run", "fixed")
SCOPE_TEXT = {
    "scenario": "Scenario file",
    "run": "Run option",
    "fixed": "Fixed",
}
AREAS = ("environment", "power", "thermal", "mass", "link")
AREA_TITLE = {
    "environment": "Environment: orbit, Earth, Sun, eclipses",
    "power": "Power",
    "thermal": "Thermal",
    "mass": "Mass",
    "link": "RF link",
}


@dataclass(frozen=True)
class Choice:
    """One alternative of a model choice. `source` is empty when the alternatives are the same
    model (then the equations carry the source)."""

    id: str
    title: str
    equations: tuple[str, ...] = ()
    source: str = ""
    note: str = ""


@dataclass(frozen=True)
class ModelChoice:
    id: str  # area.name
    title: str
    label: str  # short noun used in a row name ("shadow model")
    scope: str
    default: str
    choices: tuple[Choice, ...]
    acts_on: str  # what it changes, in plain words
    where: str  # the file and field, the option, or why it cannot be changed
    reference: str  # the deviation or decision that describes it, and why it is fixed
    field: str = ""  # the scenario field or the option, for scopes `scenario` and `run`

    @property
    def area(self) -> str:
        return self.id.partition(".")[0]

    @property
    def selectable(self) -> bool:
        return self.scope != "fixed"

    def choice(self, choice_id: str) -> Choice | None:
        return next((c for c in self.choices if c.id == choice_id), None)

    def active_title(self, choice_id: str) -> str:
        found = self.choice(choice_id)
        return found.title if found else choice_id


def _fixed(
    id: str, title: str, value: str, acts_on: str, reference: str, equations: tuple[str, ...] = ()
) -> ModelChoice:
    """A model that is not selectable: one alternative, with the reason in `reference`."""
    return ModelChoice(
        id,
        title,
        title.lower(),
        "fixed",
        value,
        (Choice(value, value, equations),),
        acts_on,
        "Not selectable in this version",
        reference,
    )


REGISTRY: tuple[ModelChoice, ...] = (
    # ---- selectable ----------------------------------------------------------------------------
    ModelChoice(
        "environment.source",
        "Source of the environment",
        "environment",
        "scenario",
        "elements",
        (
            Choice(
                "elements",
                "Computed from the orbit file",
                ("ENV-SUN", "ENV-GMST", "ENV-GEODETIC"),
                note="SGP4 on the orbit of the project, or on its TLE.",
            ),
            Choice(
                "spacemissionstudio",
                "Read from a SpaceMissionStudio export",
                note="The positions, eclipses and passes are imported, not computed here.",
            ),
        ),
        "Where the orbit, the eclipses and the passes come from.",
        "scenarios/<id>.yaml field environment_source",
        "DEVIATIONS DV-I1, docs/ENVIRONMENT_FORMAT.md",
        "environment_source",
    ),
    ModelChoice(
        "environment.shadow_model",
        "Shadow geometry",
        "shadow model",
        "scenario",
        "cylindrical",
        (
            Choice(
                "cylindrical",
                "Cylindrical shadow",
                ("ENV-SHADOW-CYL",),
                note="The Sun is a point at infinity: lit or dark, no penumbra.",
            ),
            Choice(
                "conical",
                "Conical shadow (umbra, penumbra, annular)",
                ("ENV-SHADOW-CON",),
                note="The Sun and the Earth are discs: the lit fraction falls through the "
                "penumbra.",
            ),
        ),
        "Eclipse times, the sunlit fraction of the array and every result that follows from them.",
        "scenarios/<id>.yaml field shadow_model",
        "DEVIATIONS DV-P1, DV-E4",
        "shadow_model",
    ),
    ModelChoice(
        "environment.earth_model",
        "Earth constants",
        "earth model",
        "scenario",
        "wgs84",
        (
            Choice(
                "wgs84",
                "WGS-84",
                source="WGS 84 (NIMA TR8350.2), the set of the sgp4 library: equatorial radius "
                "6378.137 km, mu 398600.5 km3/s2.",
                note="The default.",
            ),
            Choice(
                "wgs72",
                "WGS-72",
                source="WGS 72, the gravity constants of the SGP4 theory (Hoots and Roehrich, "
                "Spacetrack Report No. 3), the set of the sgp4 library: equatorial radius "
                "6378.135 km, mu 398600.8 km3/s2.",
                note="Also the set a TLE is defined on.",
            ),
        ),
        "The propagation of an orbit given as elements (mean motion and the SGP4 constants) "
        "and the Earth sphere of the shadow. The ground sites stay WGS-84 geodetic coordinates, "
        "a TLE stays on WGS-72, an imported environment is not computed here.",
        "scenarios/<id>.yaml field earth_model",
        "DEVIATIONS DV-E5",
        "earth_model",
    ),
    ModelChoice(
        "power.load_basis",
        "Load basis of the power timeline",
        "load basis",
        "run",
        "nominal",
        (
            Choice(
                "nominal",
                "Nominal loads",
                note="The average and peak power of each mode as given.",
            ),
            Choice(
                "margined",
                "Margined loads",
                note="The same with the system and source margins applied.",
            ),
        ),
        "The demand of every mode, and so the energy balance and the battery.",
        "Option --load-basis of budget power-timeline; the window runs the nominal basis",
        "docs/models/power-timeline.md",
        "load_basis",
    ),
    # ---- fixed ---------------------------------------------------------------------------------
    _fixed(
        "environment.propagation",
        "Orbit propagation",
        "SGP4 on mean elements",
        "Every position of the spacecraft.",
        "DEVIATIONS DV-E2: elements are used as mean elements, without drag (B* = 0). "
        "A numerical propagator is a different model with new inputs (forces, drag), not a switch.",
    ),
    _fixed(
        "environment.gravity_tle",
        "Gravity model of a TLE",
        "WGS-72",
        "The propagation of a TLE.",
        "DEVIATIONS DV-E5: the SGP4 library's default constants, the usual pairing for TLEs; "
        "SGP4 is defined on this set.",
    ),
    _fixed(
        "environment.sun_position",
        "Sun position",
        "Low-precision almanac formulae (about 0.01 degree)",
        "The Sun direction and distance, the shadow and the array incidence.",
        "DEVIATIONS DV-E1; equation ENV-SUN. A high-precision ephemeris needs data or a "
        "dependency that is not offline and licence-clean today.",
        ("ENV-SUN",),
    ),
    _fixed(
        "environment.earth_rotation",
        "Earth rotation",
        "GMST only, UTC treated as UT1",
        "The ground track, the passes and the visibility of a site.",
        "DEVIATIONS DV-E1: up to 0.9 s, about 400 m on the ground.",
        ("ENV-GMST",),
    ),
    _fixed(
        "environment.shadow_earth",
        "Earth in the shadow geometry",
        "Sphere of the equatorial radius",
        "The edge of the shadow.",
        "DEVIATIONS DV-P1: no oblateness, no atmosphere.",
    ),
    _fixed(
        "environment.eclipse",
        "Eclipse",
        "Any shadow, penumbra included",
        "Whether an interval counts as an eclipse.",
        "DEVIATIONS DV-E4: the sunlight ratio is below 1 by more than 1e-12.",
    ),
    _fixed(
        "power.cases",
        "Power cases",
        "BOL and EOL (EOL at the design life)",
        "The age of the array and the battery in every result.",
        "DEVIATIONS DV-P2; power_system.design_life_yr.",
    ),
    _fixed(
        "power.array_irradiance",
        "Irradiance on the array",
        "Constant solar_irradiance_wm2",
        "The array output.",
        "DEVIATIONS DV-P5: no Earth-Sun distance variation. A seasonal irradiance is planned "
        "for 2.0.0 (P5c).",
    ),
    _fixed(
        "thermal.model",
        "Thermal model",
        "Steady state, isothermal nodes, radiation to one sink",
        "Every temperature.",
        "DEVIATIONS DV-T1, DV-T3: a transient model or view factors are a different model "
        "with new inputs, not a switch.",
    ),
    _fixed(
        "mass.margin_position",
        "Position of the margin mass",
        "None: the margin is in the totals only",
        "The centre of gravity and the inertia use nominal masses.",
        "DEVIATIONS DV-M1: giving the margin a position needs new inputs.",
    ),
    _fixed(
        "link.rate_selection",
        "Data rate of a link",
        "The highest listed rate that closes the margin",
        "The rate and the data volume of every pass.",
        "docs/models/link-static.md; the rate at which the margin equals the required margin "
        "is computed and shown beside it. No other policy is offered (owner decision, D-219).",
        ("LNK-MARGIN",),
    ),
)

BY_ID: dict[str, ModelChoice] = {m.id: m for m in REGISTRY}


def of_scope(scope: str) -> tuple[ModelChoice, ...]:
    return tuple(m for m in REGISTRY if m.scope == scope)


def source_of(choice: Choice) -> str:
    """The source of an alternative: its own, else the sources of its equations."""
    if choice.source:
        return choice.source
    parts = [f"{e}: {EQUATIONS[e].source_text}" for e in choice.equations if e in EQUATIONS]
    return "; ".join(parts)


def render_markdown() -> str:
    """The page `docs/models/choices.md`, written from the registry."""
    lines = [
        "# Model choices",
        "",
        "Generated from the registry in `budget_core/model_choices.py` "
        "(`budget choices --markdown`); a test fails when this page is out of date. "
        "A *model choice* is a place where a result depends on a modelling decision. "
        "A choice is **selectable** only when a defensible alternative with a citable source "
        "exists, it can be checked against an independent reference, it changes one thing and "
        "its default is the behaviour of every project that does not say "
        "([transparency_p5_design.md](../transparency_p5_design.md), section 2). Every other "
        "model is listed as **fixed**, with the reason, so that none is hidden. "
        "Nothing on this page changes a result by being listed.",
        "",
        "**Where a choice is made.** *Scenario file*: a field of the scenario, so two scenarios "
        "can use two models. *Run option*: an option of a run, recorded in the run parameters. "
        "*Fixed*: not selectable in this version.",
        "",
        "**Contents:** "
        + " · ".join(f"[{AREA_TITLE[a]}](#{_anchor(a)})" for a in AREAS if _in_area(a)),
    ]
    for area in AREAS:
        entries = [m for m in REGISTRY if m.area == area]
        if not entries:
            continue
        lines += ["", f"## {AREA_TITLE[area]}", ""]
        lines += [
            "| Id | Choice | Default | Alternatives | Made in | Acts on | Reference |",
            "|---|---|---|---|---|---|---|",
        ]
        for m in entries:
            alternatives = (
                "; ".join(f"`{c.id}`" for c in m.choices) if m.selectable else "(none: fixed)"
            )
            lines.append(
                f"| `{m.id}` | {m.title} | {m.active_title(m.default)} | {alternatives} | "
                f"{m.where if m.selectable else SCOPE_TEXT[m.scope]} | {m.acts_on} | "
                f"{m.reference} |"
            )
    selectable = [m for m in REGISTRY if m.selectable]
    lines += ["", "## The alternatives of the selectable choices", ""]
    for m in selectable:
        lines += [
            f"### {m.title}",
            "",
            f"`{m.id}`, made in: {m.where}. Default: `{m.default}`.",
            "",
            "| Value | Title | Equations | Source or note |",
            "|---|---|---|---|",
        ]
        for c in m.choices:
            equations = ", ".join(f"`{e}`" for e in c.equations) or "(none)"
            text = " ".join(t for t in (c.note, source_of(c)) if t) or "(none)"
            lines.append(f"| `{c.id}` | {c.title} | {equations} | {text} |")
        lines.append("")
    lines += ["Next: [Models](README.md) · [Docs index](../README.md).", ""]
    return "\n".join(lines)


def _in_area(area: str) -> bool:
    return any(m.area == area for m in REGISTRY)


def _anchor(area: str) -> str:
    """The GitHub anchor of the heading of an area."""
    title = AREA_TITLE[area].lower()
    keep = "".join(ch for ch in title if ch.isalnum() or ch in " -")
    return keep.replace(" ", "-")
