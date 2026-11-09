# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Pointing and manoeuvres on a scenario (2.3.0, D-235).

A scenario may hold a **pointing mode** over its whole length (`pointing_default`) and change it
with rules, exactly like the spacecraft modes but separately from them. Where the pointing mode
changes, the slew between the two modes of `config/pointing.yaml` is flown: the actuators draw
their slew power for the slew time, then the new mode's holding power takes over. A scenario may
also place **burns** of `config/propulsion.yaml` (`maneuvers`): an electric system draws its
thrusting power for the burn time of the manoeuvre, a chemical one draws none, and a manoeuvre that
names a spacecraft `mode` switches the scenario to it for the burn.

These loads are kept apart from the spacecraft modes' demand. A load that is a placeholder is
unknown (n/a, never zero); a pointing mode with no holding power given is not modelled and holds
no event. No margin is applied to them: put the margin in the input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from budget_core.assumptions import incomplete
from budget_core.environment.data import EnvironmentData
from budget_core.model import Project, Scenario, ScenarioSegment, Sourced
from budget_core.pointing.budget import SlewRow, pointing_budget
from budget_core.power.signals import step_means
from budget_core.problems import Problem, Severity
from budget_core.propulsion.budget import propulsion_budget
from budget_core.scenario.timeline import build_timeline

NDArray = np.ndarray[Any, np.dtype[np.float64]]
EventKind = Literal["hold", "slew", "burn"]


@dataclass(frozen=True)
class LoadEvent:
    kind: EventKind
    label: str  # the pointing mode, the slew or the manoeuvre
    start_s: float
    end_s: float
    power_w: float | None  # None: an input is a placeholder

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass(frozen=True)
class ExtraLoads:
    events: tuple[LoadEvent, ...]
    problems: tuple[Problem, ...]
    incomplete: bool  # an event could not be placed: the load is unknown

    def mean_power(self, edges: NDArray) -> NDArray | None:
        """The mean power on each step between `edges`, or None when a power or a time is
        unknown. Hold and slew events do not overlap; burns are added one by one."""
        if self.incomplete or any(e.power_w is None for e in self.events):
            return None
        pointing = sorted(
            (e for e in self.events if e.kind != "burn" and e.duration_s > 0.0),
            key=lambda e: e.start_s,
        )
        total = np.zeros(len(edges) - 1, dtype=np.float64)
        if pointing:
            total += step_means(
                [e.start_s for e in pointing],
                [e.end_s for e in pointing],
                [float(e.power_w or 0.0) for e in pointing],
                edges,
            )
        for burn in (e for e in self.events if e.kind == "burn" and e.duration_s > 0.0):
            total += step_means([burn.start_s], [burn.end_s], [float(burn.power_w or 0.0)], edges)
        return total

    def peak_between(self, start_s: float, end_s: float) -> float:
        """The largest total power of the known events inside [start, end) (0 where none): the
        pieces between the event edges are looked at one by one."""
        inside = sorted(
            {start_s, end_s}
            | {t for e in self.events for t in (e.start_s, e.end_s) if start_s < t < end_s}
        )
        if len(inside) < 2:
            return 0.0
        known = ExtraLoads(
            tuple(e for e in self.events if e.power_w is not None), (), False
        ).mean_power(np.array(inside, dtype=np.float64))
        return 0.0 if known is None or len(known) == 0 else float(np.max(known))

    def energy_wh(self) -> float | None:
        if self.incomplete or any(e.power_w is None for e in self.events):
            return None
        return math.fsum(float(e.power_w or 0.0) * e.duration_s for e in self.events) / 3600.0


def _value(item: Sourced | None) -> float | None:
    return None if item is None or item.is_placeholder else item.value


def maneuver_segments(project: Project, scenario: Scenario) -> list[ScenarioSegment]:
    """The spacecraft-mode segments the placed burns make: a manoeuvre that names a `mode`
    switches the scenario to it for the burn (cut at the scenario end)."""
    if not scenario.maneuvers or project.config.propulsion is None:
        return []
    budget = propulsion_budget(project)
    if budget is None:
        return []
    rows = {r.name: r for r in budget.maneuvers}
    out: list[ScenarioSegment] = []
    for placed in scenario.maneuvers:
        row = rows.get(placed.name)
        if row is None or row.mode is None or row.burn_time_s is None:
            continue
        end = min(placed.start_s + row.burn_time_s, scenario.duration_s)
        if end - placed.start_s > 1e-9:
            out.append(
                ScenarioSegment(
                    start_s=placed.start_s, duration_s=end - placed.start_s, mode=row.mode
                )
            )
    return out


def pointing_segments(scenario: Scenario, env: EnvironmentData) -> list[tuple[float, float, str]]:
    """The pointing mode over the scenario: (start, end, mode), contiguous."""
    if not scenario.pointing_default:
        return []
    as_modes = scenario.model_copy(
        update={
            "default_mode": scenario.pointing_default,
            "rules": scenario.pointing_rules,
            "segments": [],
            "maneuvers": [],
        }
    )
    return [(s.start_s, s.end_s, s.mode) for s in build_timeline(as_modes, env)]


def extra_loads(project: Project, run: Any) -> ExtraLoads | None:
    """The loads of the scenario's pointing and burns; None when it places neither."""
    scenario: Scenario = run.scenario
    if not scenario.pointing_default and not scenario.maneuvers:
        return None
    file = f"scenarios/{run.scenario_id}.yaml"
    events: list[LoadEvent] = []
    problems: list[Problem] = []
    unknown = False
    limit = scenario.duration_s

    config = project.config.pointing
    segments = pointing_segments(scenario, run.env) if config is not None else []
    if segments and config is not None:
        budget = pointing_budget(project)
        rows: list[SlewRow] = list(budget.slews) if budget else []
        missing: set[tuple[str, str]] = set()
        for k, (start, end, mode) in enumerate(segments):
            hold_from = start
            if k > 0:
                before = segments[k - 1][2]
                slew_index = next(
                    (
                        i
                        for i, s in enumerate(config.slews)
                        if s.from_mode == before and s.to_mode == mode
                    ),
                    None,
                )
                if slew_index is None:
                    if (before, mode) not in missing:
                        missing.add((before, mode))
                        problems.append(
                            Problem(
                                Severity.WARNING,
                                "POINTING_SLEW_MISSING",
                                "The pointing mode changes where config/pointing.yaml defines "
                                "no slew between the two modes; the change costs nothing here.",
                                file=file,
                                path="pointing_rules",
                                hint="Add a slew between the two pointing modes to "
                                "config/pointing.yaml.",
                            )
                        )
                else:
                    slew = config.slews[slew_index]
                    row = rows[slew_index]
                    actuator = config.actuators.get(slew.actuator)
                    power = _value(actuator.slew_power_w) if actuator else None
                    if row.slew_time_s is None:
                        unknown = True
                        problems.append(
                            incomplete(
                                "A slew time is unknown (a torque or an inertia is missing), so "
                                "the slew cannot be placed.",
                                "config/pointing.yaml",
                                f"slews[{slew_index}]",
                            )
                        )
                    else:
                        slew_end = min(start + row.slew_time_s, end)
                        if row.slew_time_s > end - start + 1e-9:
                            problems.append(
                                Problem(
                                    Severity.WARNING,
                                    "POINTING_SLEW_TOO_LONG",
                                    "A slew is longer than the pointing mode it leads to, so it "
                                    "is cut at the end of that mode.",
                                    file=file,
                                    path="pointing_rules",
                                    hint="Lengthen the event, lower the torque demand or use "
                                    "fewer changes of pointing mode.",
                                    actual=row.slew_time_s,
                                    limit=end - start,
                                    unit="s",
                                )
                            )
                        if actuator is not None and actuator.slew_power_w is not None:
                            events.append(LoadEvent("slew", slew.name, start, slew_end, power))
                            if power is None:
                                problems.append(
                                    incomplete(
                                        "A slew power is a placeholder.",
                                        "config/pointing.yaml",
                                        f"actuators.{slew.actuator}.slew_power_w",
                                    )
                                )
                        hold_from = slew_end
            hold = config.modes.get(mode)
            if hold is not None and hold.hold_power_w is not None and end > hold_from:
                power_hold = _value(hold.hold_power_w)
                events.append(LoadEvent("hold", hold.name, hold_from, end, power_hold))
                if power_hold is None:
                    problems.append(
                        incomplete(
                            "A holding power is a placeholder.",
                            "config/pointing.yaml",
                            f"modes.{mode}.hold_power_w",
                        )
                    )

    prop = project.config.propulsion
    if scenario.maneuvers and prop is not None:
        budget_p = propulsion_budget(project)
        by_name = {r.name: r for r in budget_p.maneuvers} if budget_p else {}
        for index, placed in enumerate(scenario.maneuvers):
            row_p = by_name.get(placed.name)
            if row_p is None:
                continue
            if row_p.burn_time_s is None:
                unknown = True
                problems.append(
                    incomplete(
                        "A burn time is unknown (an input of the propulsion file is a placeholder "
                        "or missing), so the manoeuvre cannot be placed.",
                        file,
                        f"maneuvers[{index}]",
                    )
                )
                continue
            end = min(placed.start_s + row_p.burn_time_s, limit)
            if placed.start_s >= limit or end < placed.start_s + row_p.burn_time_s - 1e-9:
                problems.append(
                    Problem(
                        Severity.WARNING,
                        "MANEUVER_CUT",
                        "A manoeuvre starts after the scenario ends or runs past its end; only "
                        "the part inside is counted.",
                        file=file,
                        path=f"maneuvers[{index}]",
                        hint="Start the manoeuvre earlier or lengthen the scenario.",
                        actual=placed.start_s + row_p.burn_time_s,
                        limit=limit,
                        unit="s",
                    )
                )
            if placed.start_s >= limit:
                continue
            events.append(LoadEvent("burn", row_p.name, placed.start_s, end, row_p.power_w))
            if row_p.power_w is None:
                problems.append(
                    incomplete(
                        "The thrusting power of an electric system is a placeholder or missing.",
                        "config/propulsion.yaml",
                        f"maneuvers[{index}]",
                    )
                )
    ordered = tuple(sorted(events, key=lambda e: (e.start_s, e.kind)))
    return ExtraLoads(ordered, tuple(problems), unknown)
