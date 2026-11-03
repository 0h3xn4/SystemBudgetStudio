"""`budget orbit`: the orbit design calculator on the command line (2.2.0, D-226).

Four commands that turn what a mission analyst asks for into the numbers an orbit file takes:
`ltan` (the local time of the node and the right ascension, both ways), `sso` (the
sun-synchronous orbit of an altitude or an inclination), `repeat` (the orbit of one repeat ground
track) and `repeats` (every repeat cycle in an altitude window). The inputs are the arguments; no
project file is read, so every value printed is one the user typed or derived from it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from budget_core.environment.constants import DEFAULT_EARTH_MODEL, EARTH_MODELS
from budget_core.orbit_design import (
    OrbitDesignError,
    RepeatSolution,
    design_sun_synchronous,
    j2_secular_rates,
    mean_solar_time_of_node_h,
    raan_from_ltan_deg,
    repeat_candidates,
    repeat_ground_track,
    sun_synchronous_altitude_m,
    sun_synchronous_inclination_deg,
)
from budget_core.timeutil import parse_utc


def _fail(text: str) -> int:
    sys.stdout.flush()
    print(text, file=sys.stderr)
    return 1


def _local_time_h(text: str) -> float:
    """'10:30' or '10.5' (hours) to hours; a ValueError for anything else or out of 0 up to 24."""
    text = text.strip()
    if ":" in text:
        hours_text, _, minutes_text = text.partition(":")
        hours, minutes = float(hours_text), float(minutes_text)
        if not 0.0 <= minutes < 60.0:
            raise ValueError("minutes")
        value = hours + minutes / 60.0
    else:
        value = float(text)
    if not 0.0 <= value < 24.0:
        raise ValueError("hours")
    return value


def _clock(hours: float) -> str:
    total = round(hours * 60.0) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def add_parser(sub: Any) -> None:
    orbit = sub.add_parser(
        "orbit",
        help="Orbit design: local time of the node, sun-synchronous orbit, repeat ground track.",
    )
    commands = orbit.add_subparsers(dest="orbit_command", required=True)

    def common(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--earth-model",
            choices=sorted(EARTH_MODELS),
            default=DEFAULT_EARTH_MODEL,
            help="The Earth constants (radius, gravitational parameter, J2). Default: wgs84.",
        )
        parser.add_argument("--format", choices=("text", "json"), default="text")

    ltan = commands.add_parser(
        "ltan", help="Convert the mean local solar time of the ascending node and its RAAN."
    )
    ltan.add_argument("--epoch", required=True, help="UTC time, for example 2026-06-01T00:00:00Z.")
    ltan.add_argument("--ltan", help="Local time of the ascending node, HH:MM or decimal hours.")
    ltan.add_argument("--raan", type=float, help="Right ascension of the ascending node, degrees.")
    common(ltan)

    sso = commands.add_parser(
        "sso", help="The sun-synchronous orbit of an altitude or an inclination."
    )
    sso.add_argument("--altitude-km", type=float, help="Altitude (semi-major axis minus radius).")
    sso.add_argument("--inclination-deg", type=float, help="Inclination (above 90 degrees).")
    sso.add_argument("--eccentricity", type=float, default=0.0)
    sso.add_argument("--ltan", help="With --epoch: the node's local time, to get the RAAN.")
    sso.add_argument("--epoch", help="UTC time of the elements, with --ltan.")
    common(sso)

    repeat = commands.add_parser(
        "repeat", help="The orbit whose ground track repeats after N revolutions in D days."
    )
    repeat.add_argument("--revolutions", type=int, required=True, help="N, nodal periods.")
    repeat.add_argument("--days", type=int, required=True, help="D, nodal days.")
    repeat.add_argument("--sso", action="store_true", help="Sun-synchronous.")
    repeat.add_argument("--inclination-deg", type=float, help="Or give the inclination.")
    repeat.add_argument("--eccentricity", type=float, default=0.0)
    common(repeat)

    repeats = commands.add_parser(
        "repeats", help="Every repeat cycle that has an orbit in an altitude window."
    )
    repeats.add_argument("--altitude-min-km", type=float, required=True)
    repeats.add_argument("--altitude-max-km", type=float, required=True)
    repeats.add_argument("--max-days", type=int, default=10, help="Longest cycle, in days.")
    repeats.add_argument("--sso", action="store_true", help="Sun-synchronous.")
    repeats.add_argument("--inclination-deg", type=float, help="Or give the inclination.")
    repeats.add_argument("--eccentricity", type=float, default=0.0)
    common(repeats)


def _round(value: float) -> float:
    return round(value, 6)


def _solution_dict(s: RepeatSolution) -> dict[str, Any]:
    return {
        "revolutions": s.revolutions,
        "days": s.days,
        "altitude_km": _round(s.altitude_m / 1000.0),
        "semi_major_axis_km": _round(s.semi_major_axis_m / 1000.0),
        "eccentricity": s.eccentricity_ratio,
        "inclination_deg": _round(s.inclination_deg),
        "sun_synchronous": s.sun_synchronous,
        "nodal_period_min": _round(s.nodal_period_s / 60.0),
        "track_spacing_km": _round(s.track_spacing_km),
        "earth_model": s.earth_model,
    }


_UNITS = {
    "altitude_km": " km",
    "semi_major_axis_km": " km",
    "inclination_deg": " deg",
    "raan_deg": " deg",
    "nodal_period_min": " min",
    "track_spacing_km": " km",
    "revolutions_per_day": " per day",
}
_LABELS = {
    "altitude_km": "Altitude",
    "semi_major_axis_km": "Semi-major axis",
    "eccentricity": "Eccentricity",
    "inclination_deg": "Inclination",
    "raan_deg": "RAAN",
    "ltan": "Ascending node local time (mean solar)",
    "ltdn": "Descending node local time (mean solar)",
    "nodal_period_min": "Nodal period",
    "revolutions_per_day": "Revolutions",
    "track_spacing_km": "Track spacing at the equator",
    "revolutions": "Revolutions",
    "days": "Days",
    "epoch": "Epoch",
    "earth_model": "Earth model",
    "sun_synchronous": "Sun-synchronous",
}


def _print(data: dict[str, Any] | list[dict[str, Any]], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    rows = data if isinstance(data, list) else [data]
    for index, row in enumerate(rows):
        if index:
            print()
        for key, value in row.items():
            if key in ("ltan_h", "ltdn_h"):
                continue
            label = _LABELS.get(key, key)
            shown = f"{value:g}" if isinstance(value, float) else str(value)
            print(f"{label + '.':<42}{shown}{_UNITS.get(key, '')}")


def run(args: argparse.Namespace) -> int:
    try:
        return _dispatch(args)
    except OrbitDesignError as exc:
        return _fail(str(exc))


def _epoch(text: str | None) -> datetime | None | str:
    if text is None:
        return None
    try:
        return parse_utc(text)
    except ValueError:
        return "The epoch is a UTC time such as 2026-06-01T00:00:00Z."


def _dispatch(args: argparse.Namespace) -> int:
    command = args.orbit_command
    earth = args.earth_model
    if command == "ltan":
        epoch = _epoch(args.epoch)
        if isinstance(epoch, str) or epoch is None:
            return _fail(epoch or "Give the epoch.")
        if (args.ltan is None) == (args.raan is None):
            return _fail("Give either --ltan (to get the RAAN) or --raan (to get the local time).")
        if args.ltan is not None:
            try:
                hours = _local_time_h(args.ltan)
            except ValueError:
                return _fail("The local time is HH:MM or decimal hours, from 0 up to 24.")
            raan = raan_from_ltan_deg(hours, epoch)
        else:
            raan = args.raan % 360.0
            hours = mean_solar_time_of_node_h(raan, epoch)
        _print(
            {
                "epoch": args.epoch,
                "ltan": _clock(hours),
                "ltan_h": _round(hours),
                "raan_deg": _round(raan),
            },
            args.format,
        )
        return 0
    if command == "sso":
        return _sso(args, earth)
    if command == "repeat":
        solution = repeat_ground_track(
            args.revolutions,
            args.days,
            eccentricity=args.eccentricity,
            inclination_deg=args.inclination_deg,
            sun_synchronous=args.sso,
            earth_model=earth,
        )
        _print(_solution_dict(solution), args.format)
        return 0
    found = repeat_candidates(
        args.altitude_min_km * 1000.0,
        args.altitude_max_km * 1000.0,
        args.max_days,
        eccentricity=args.eccentricity,
        inclination_deg=args.inclination_deg,
        sun_synchronous=args.sso,
        earth_model=earth,
    )
    _print([_solution_dict(s) for s in found], args.format)
    return 0


def _sso(args: argparse.Namespace, earth: str) -> int:
    if (args.altitude_km is None) == (args.inclination_deg is None):
        return _fail("Give either --altitude-km or --inclination-deg.")
    if (args.ltan is None) != (args.epoch is None):
        return _fail("The node's local time needs the epoch, and the epoch needs the local time.")
    e = args.eccentricity
    radius = EARTH_MODELS[earth].radius_m
    if args.altitude_km is not None:
        altitude_m = args.altitude_km * 1000.0
        inclination = sun_synchronous_inclination_deg(radius + altitude_m, e, earth)
    else:
        inclination = args.inclination_deg
        altitude_m = sun_synchronous_altitude_m(inclination, e, earth)
    a = radius + altitude_m
    rates = j2_secular_rates(a, e, inclination, earth)
    data: dict[str, Any] = {
        "altitude_km": _round(altitude_m / 1000.0),
        "semi_major_axis_km": _round(a / 1000.0),
        "eccentricity": e,
        "inclination_deg": _round(inclination),
        "nodal_period_min": _round(rates.nodal_period_s / 60.0),
        "revolutions_per_day": _round(86400.0 / rates.nodal_period_s),
        "earth_model": earth,
    }
    if args.ltan is not None:
        epoch = _epoch(args.epoch)
        if isinstance(epoch, str) or epoch is None:
            return _fail(epoch or "Give the epoch.")
        try:
            hours = _local_time_h(args.ltan)
        except ValueError:
            return _fail("The local time is HH:MM or decimal hours, from 0 up to 24.")
        design = design_sun_synchronous(
            altitude_m=altitude_m, ltan_h=hours, epoch=epoch, eccentricity=e, earth_model=earth
        )
        data["raan_deg"] = _round(design.raan_deg)
        data["ltan"] = _clock(design.ltan_h)
        data["ltan_h"] = _round(design.ltan_h)
        data["ltdn"] = _clock(design.ltdn_h)
        data["ltdn_h"] = _round(design.ltdn_h)
        data["epoch"] = args.epoch
    _print(data, args.format)
    return 0
