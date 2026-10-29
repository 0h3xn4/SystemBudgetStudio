"""Cross-file checks: references between files, and configuration gaps (placeholders)."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path as FsPath
from typing import Any

from budget_core.io.paths import resolve_inside
from budget_core.io.yamlio import LineMap, Path, format_path
from budget_core.model import Antenna, BudgetModel, Link, Project, Scenario, Sourced
from budget_core.problems import Problem, Severity
from budget_core.units.quantity import canonical_unit


def iter_sourced(value: Any, path: Path = ()) -> Iterator[tuple[Path, Sourced]]:
    """Every `Sourced` number inside a config model, with its path."""
    if isinstance(value, Sourced):
        yield path, value
    elif isinstance(value, BudgetModel):
        for name in type(value).model_fields:
            yield from iter_sourced(getattr(value, name), path + (name,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_sourced(item, path + (index,))
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_sourced(item, path + (key,))


def _p(
    sev: Severity,
    code: str,
    msg: str,
    file: str,
    path: Path,
    lines: dict[str, LineMap],
    hint: str = "",
) -> Problem:
    line = lines[file].lookup(path) if file in lines else None
    return Problem(sev, code, msg, file=file, path=format_path(path), line=line, hint=hint)


Failed = Mapping[str, set[str]]


def _failed(failed: Failed | None, *folders: str) -> set[str]:
    """Ids of files in `folders` that exist but did not load: a reference to one of them is
    not reported as unknown (the file's own problem explains it)."""
    found: set[str] = set()
    for folder in folders:
        found |= (failed or {}).get(folder, set())
    return found


def validate_references(
    project: Project, lines: dict[str, LineMap], failed: Failed | None = None
) -> list[Problem]:
    out: list[Problem] = []
    err, warn = Severity.ERROR, Severity.WARNING
    buses = sorted(b.name for b in project.spacecraft.buses)
    policy = project.config.margin_policy

    for uid, unit in project.units.items():
        file = f"units/{uid}.yaml"
        if unit.bus not in buses:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_BUS",
                    "The unit's supply bus is not defined in spacecraft.yaml.",
                    file,
                    ("bus",),
                    lines,
                    "Use the name of a bus listed under 'buses' in spacecraft.yaml.",
                )
            )
        if policy is not None and unit.maturity not in policy.classes:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_MATURITY",
                    "The unit's maturity class is not defined in config/margin_policy.yaml.",
                    file,
                    ("maturity",),
                    lines,
                    "Use a class listed under 'classes' in config/margin_policy.yaml.",
                )
            )

    for mid, mode in project.modes.items():
        file = f"modes/{mid}.yaml"
        for uid, unit_mode in mode.assignments.items():
            target = project.units.get(uid)
            if target is None and uid in _failed(failed, "units"):
                continue
            if target is None:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_UNIT",
                        "This unit id does not exist in units/.",
                        file,
                        ("assignments", uid),
                        lines,
                        "Use the file name (without .yaml) of a unit.",
                    )
                )
            elif unit_mode not in {m.name for m in target.modes}:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_UNIT_MODE",
                        f"Unit '{uid}' has no power mode with this name.",
                        file,
                        ("assignments", uid),
                        lines,
                        "Use a power mode name listed under 'modes' in the unit file.",
                    )
                )
        for uid in sorted(set(project.units) - set(mode.assignments)):
            out.append(
                _p(
                    err,
                    "UNIT_NOT_MAPPED",
                    f"Unit '{uid}' is not assigned a power mode.",
                    file,
                    ("assignments",),
                    lines,
                    f"Add '{uid}: <power mode name>' under assignments.",
                )
            )

    power = project.config.power_config
    if power is not None:
        for bus in power.converter_efficiency_ratio:
            if bus not in buses:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_BUS",
                        "Converter efficiency is given for a bus that spacecraft.yaml lacks.",
                        "config/power_config.yaml",
                        ("converter_efficiency_ratio", bus),
                        lines,
                        "Use the name of a bus listed under 'buses' in spacecraft.yaml.",
                    )
                )

    out.extend(_mass_references(project, lines))
    out.extend(_environment_references(project, lines, failed))
    out.extend(_power_system_references(project, lines, failed))
    out.extend(_thermal_references(project, lines, failed))
    out.extend(_link_references(project, lines, failed))
    out.extend(_value_ranges(project, lines))

    for kind in (
        "margin_policy",
        "power_config",
        "ebn0_table",
        "attenuation_table",
        "mass_limits",
        "power_system",
        "thermal_model",
        "thermal_environment",
    ):
        model = getattr(project.config, kind)
        if model is None:
            continue
        file = f"config/{kind}.yaml"
        for path, sourced in iter_sourced(model):
            if sourced.is_placeholder:
                out.append(
                    _p(
                        warn,
                        "CONFIG_PLACEHOLDER",
                        "This number is a placeholder (no value or source 'TBD'); results "
                        "that use it are not trustworthy.",
                        file,
                        path,
                        lines,
                        "Replace it with a value from your margin policy, standard or data "
                        "sheet and cite the source.",
                    )
                )
        if kind == "mass_limits" and not model.limits:
            out.append(
                _p(
                    Severity.WARNING,
                    "CONFIG_EMPTY_TABLE",
                    "The table has no entries.",
                    file,
                    ("limits",),
                    lines,
                    "Add mass limits with their sources (for example launch mass).",
                )
            )
        if kind in ("ebn0_table", "attenuation_table") and not model.entries:
            out.append(
                _p(
                    warn,
                    "CONFIG_EMPTY_TABLE",
                    "The table has no entries.",
                    file,
                    ("entries",),
                    lines,
                    "Add entries from a cited source, or import them from a file.",
                )
            )
    for lid, link in project.links.items():
        file = f"links/{lid}.yaml"
        for path, sourced in iter_sourced(link):
            if sourced.is_placeholder:
                out.append(
                    _p(
                        warn,
                        "CONFIG_PLACEHOLDER",
                        "This number is a placeholder (no value or source 'TBD'); results "
                        "that use it are not trustworthy.",
                        file,
                        path,
                        lines,
                        "Replace it with a value from the data sheet or requirement and cite "
                        "the source.",
                    )
                )
        for side, antenna in _antennas(link):
            if antenna.pattern is not None and antenna.pattern.is_placeholder:
                out.append(
                    _p(
                        warn,
                        "CONFIG_PLACEHOLDER",
                        "The antenna pattern is a placeholder (source 'TBD').",
                        file,
                        (side, "antenna", "pattern", "source"),
                        lines,
                        "Replace it with data-sheet values and cite the source.",
                    )
                )
            if (
                antenna.pattern_source is not None
                and antenna.pattern_source.strip().upper() == "TBD"
            ):
                out.append(
                    _p(
                        warn,
                        "CONFIG_PLACEHOLDER",
                        "The antenna pattern file is a placeholder (source 'TBD').",
                        file,
                        (side, "antenna", "pattern_source"),
                        lines,
                        "Cite the source of the pattern file.",
                    )
                )
    return out


def _range_problem(
    file: str, path: Path, lines: dict[str, LineMap], what: str, allowed: str
) -> Problem:
    line = lines[file].lookup(path + ("value",)) if file in lines else None
    unit = canonical_unit(str(path[-1])) if path and isinstance(path[-1], str) else None
    if unit == "ratio":
        hint = "Ratios are written as fractions (0.1 means 10 %); the allowed range is above."
    elif unit:
        hint = f"The value is in {unit}; the allowed range is above."
    else:
        hint = "Check the value and its unit; the allowed range is above."
    return Problem(
        Severity.ERROR,
        "CONFIG_VALUE_INVALID",
        f"{what} is outside the allowed range {allowed}.",
        file=file,
        path=format_path(path + ("value",)),
        line=line,
        hint=hint,
    )


def _value_ranges(project: Project, lines: dict[str, LineMap]) -> list[Problem]:
    """Placeholders are skipped; real values must be physically meaningful."""
    out: list[Problem] = []

    def check(
        file: str,
        path: Path,
        item: Sourced,
        what: str,
        lo: float,
        hi: float,
        lo_open: bool = False,
        hi_open: bool = False,
    ) -> None:
        v = item.value
        if v is None or item.is_placeholder:
            return
        below = v <= lo if lo_open else v < lo
        above = v >= hi if hi_open else v > hi
        if below or above:
            allowed = ("(" if lo_open else "[") + f"{lo:g}, {hi:g}" + (")" if hi_open else "]")
            out.append(_range_problem(file, path, lines, what, allowed))

    policy = project.config.margin_policy
    if policy is not None:
        f = "config/margin_policy.yaml"
        for name, cls in policy.classes.items():
            for field in ("power_margin_ratio", "mass_margin_ratio"):
                check(f, ("classes", name, field), getattr(cls, field), "A margin ratio", 0.0, 10.0)
        for field in ("system_power_margin_ratio", "system_mass_margin_ratio"):
            check(f, (field,), getattr(policy, field), "The system margin", 0.0, 10.0)
    limits = project.config.mass_limits
    if limits is not None:
        for index, limit in enumerate(limits.limits):
            check(
                "config/mass_limits.yaml",
                ("limits", index, "limit_kg"),
                limit.limit_kg,
                "A mass limit",
                0.0,
                1e9,
                lo_open=True,
            )
    power = project.config.power_config
    if power is not None:
        f = "config/power_config.yaml"
        check(
            f,
            ("distribution_loss_ratio",),
            power.distribution_loss_ratio,
            "The distribution loss",
            0.0,
            1.0,
            hi_open=True,
        )
        for bus, item in power.converter_efficiency_ratio.items():
            check(
                f,
                ("converter_efficiency_ratio", bus),
                item,
                "A converter efficiency",
                0.0,
                1.0,
                lo_open=True,
            )
    system = project.config.power_system
    if system is not None:
        f = "config/power_system.yaml"
        arr, bat = system.solar_array, system.battery
        big = 1e12
        ratio_checks: list[tuple[Path, Sourced, str, float, float, bool, bool]] = [
            (("design_life_yr",), system.design_life_yr, "The design life", 0.0, 1e3, True, False),
            (
                ("solar_array", "solar_irradiance_wm2"),
                arr.solar_irradiance_wm2,
                "The solar irradiance",
                0.0,
                1e4,
                True,
                False,
            ),
            (
                ("solar_array", "cell_area_m2"),
                arr.cell_area_m2,
                "The cell area",
                0.0,
                big,
                True,
                False,
            ),
            (
                ("solar_array", "cell_efficiency_ratio"),
                arr.cell_efficiency_ratio,
                "The cell efficiency",
                0.0,
                1.0,
                True,
                False,
            ),
            (
                ("solar_array", "reference_temperature_k"),
                arr.reference_temperature_k,
                "The reference temperature",
                0.0,
                1e4,
                True,
                False,
            ),
            (
                ("solar_array", "cell_temperature_k"),
                arr.cell_temperature_k,
                "The cell temperature",
                0.0,
                1e4,
                True,
                False,
            ),
            (
                ("solar_array", "efficiency_temp_coeff_perk"),
                arr.efficiency_temp_coeff_perk,
                "The temperature coefficient",
                -1.0,
                1.0,
                True,
                True,
            ),
            (
                ("solar_array", "packing_loss_ratio"),
                arr.packing_loss_ratio,
                "The packing loss",
                0.0,
                1.0,
                False,
                True,
            ),
            (
                ("solar_array", "harness_loss_ratio"),
                arr.harness_loss_ratio,
                "The harness loss",
                0.0,
                1.0,
                False,
                True,
            ),
            (
                ("solar_array", "annual_degradation_ratio"),
                arr.annual_degradation_ratio,
                "The annual degradation",
                0.0,
                1.0,
                False,
                True,
            ),
            (
                ("battery", "cell_capacity_ah"),
                bat.cell_capacity_ah,
                "The cell capacity",
                0.0,
                big,
                True,
                False,
            ),
            (
                ("battery", "cell_nominal_voltage_v"),
                bat.cell_nominal_voltage_v,
                "The cell voltage",
                0.0,
                big,
                True,
                False,
            ),
            (
                ("battery", "charge_efficiency_ratio"),
                bat.charge_efficiency_ratio,
                "The charge efficiency",
                0.0,
                1.0,
                True,
                False,
            ),
            (
                ("battery", "discharge_efficiency_ratio"),
                bat.discharge_efficiency_ratio,
                "The discharge efficiency",
                0.0,
                1.0,
                True,
                False,
            ),
            (
                ("battery", "annual_capacity_fade_ratio"),
                bat.annual_capacity_fade_ratio,
                "The annual capacity fade",
                0.0,
                1.0,
                False,
                True,
            ),
            (
                ("battery", "initial_soc_ratio"),
                bat.initial_soc_ratio,
                "The initial state of charge",
                0.0,
                1.0,
                False,
                False,
            ),
            (
                ("limits", "peak_power_w"),
                system.limits.peak_power_w,
                "The peak power limit",
                0.0,
                big,
                True,
                False,
            ),
        ]
        for path, item, what, lo, hi, lo_open, hi_open in ratio_checks:
            check(f, path, item, what, lo, hi, lo_open, hi_open)
        for phase, item in bat.max_dod_ratio.items():
            check(
                f,
                ("battery", "max_dod_ratio", phase),
                item,
                "An allowed depth of discharge",
                0.0,
                1.0,
                lo_open=True,
            )
    out.extend(_thermal_ranges(project, check))
    out.extend(_link_ranges(project, check))
    out.extend(_table_ranges(project, check))
    return out


def _thermal_ranges(project: Project, check: Callable[..., None]) -> list[Problem]:
    """Range checks of the thermal files (placeholders are skipped by `check`)."""
    env, model = project.config.thermal_environment, project.config.thermal_model
    f = "config/thermal_environment.yaml"
    big = 1e12
    if env is not None:
        check(
            f,
            ("space_temperature_k",),
            env.space_temperature_k,
            "The space temperature",
            0.0,
            1e4,
            True,
        )
        check(
            f,
            ("temperature_margin_k",),
            env.temperature_margin_k,
            "The temperature margin",
            0.0,
            1e4,
        )
        for name, case in env.cases.items():
            base: tuple[str | int, ...] = ("cases", name)
            check(f, (*base, "solar_flux_wm2"), case.solar_flux_wm2, "The solar flux", 0.0, 1e5)
            check(f, (*base, "albedo_ratio"), case.albedo_ratio, "The albedo", 0.0, 1.0)
            check(
                f, (*base, "earth_ir_wm2"), case.earth_ir_wm2, "The Earth infrared flux", 0.0, 1e5
            )
    if model is not None:
        f = "config/thermal_model.yaml"
        for i, link in enumerate(model.conductances):
            check(
                f,
                ("conductances", i, "conductance_wk"),
                link.conductance_wk,
                "A conductance",
                0.0,
                big,
                True,
            )
        for i, surface in enumerate(model.surfaces):
            base = ("surfaces", i)
            check(
                f,
                (*base, "emissivity_ratio"),
                surface.emissivity_ratio,
                "An emissivity",
                0.0,
                1.0,
                True,
            )
            check(
                f,
                (*base, "absorptivity_ratio"),
                surface.absorptivity_ratio,
                "An absorptivity",
                0.0,
                1.0,
            )
            for case_name, exposure in surface.exposure.items():
                for field in ("solar_view_ratio", "earth_view_ratio"):
                    check(
                        f,
                        (*base, "exposure", case_name, field),
                        getattr(exposure, field),
                        "A view ratio",
                        0.0,
                        1.0,
                    )
    return []


def _antennas(link: Link) -> list[tuple[str, Antenna]]:
    out: list[tuple[str, Antenna]] = [("transmitter", link.transmitter.antenna)]
    if link.receiver.antenna is not None:
        out.append(("receiver", link.receiver.antenna))
    return out


def _link_ranges(project: Project, check: Callable[..., None]) -> list[Problem]:
    big = 1e12
    for lid, link in project.links.items():
        f = f"links/{lid}.yaml"
        tx, rx = link.transmitter, link.receiver
        check(f, ("transmitter", "power_w"), tx.power_w, "The transmit power", 0.0, big, True)
        check(f, ("transmitter", "line_loss_db"), tx.line_loss_db, "The line loss", 0.0, 100.0)
        for field, what in (
            ("required_margin_db", "The required margin"),
            ("pointing_loss_db", "The pointing loss"),
            ("polarisation_loss_db", "The polarisation loss"),
            ("implementation_loss_db", "The implementation loss"),
        ):
            check(f, (field,), getattr(link, field), what, 0.0, 100.0)
        if rx.system_noise_temperature_k is not None:
            check(
                f,
                ("receiver", "system_noise_temperature_k"),
                rx.system_noise_temperature_k,
                "The system noise temperature",
                0.0,
                1e6,
                True,
            )
        if rx.feed_loss_db is not None:
            check(f, ("receiver", "feed_loss_db"), rx.feed_loss_db, "The feed loss", 0.0, 100.0)
        if rx.g_over_t_dbk is not None:
            check(f, ("receiver", "g_over_t_dbk"), rx.g_over_t_dbk, "The G/T", -100.0, 100.0)
        for side, antenna in _antennas(link):
            if antenna.gain_dbi is not None:
                check(
                    f,
                    (side, "antenna", "gain_dbi"),
                    antenna.gain_dbi,
                    "The antenna gain",
                    -50.0,
                    100.0,
                )
    return []


def _table_ranges(project: Project, check: Callable[..., None]) -> list[Problem]:
    """Range checks of the Eb/N0 and attenuation tables."""
    ebn0, table = project.config.ebn0_table, project.config.attenuation_table
    for index, entry in enumerate(ebn0.entries if ebn0 else []):
        check(
            "config/ebn0_table.yaml",
            ("entries", index, "required_ebn0_db"),
            entry.required_ebn0_db,
            "The required Eb/N0",
            -20.0,
            60.0,
        )
    for index, att in enumerate(table.entries if table else []):
        check(
            "config/attenuation_table.yaml",
            ("entries", index, "loss_db"),
            att.loss_db,
            "An atmospheric loss",
            0.0,
            100.0,
        )
    return []


def _link_references(
    project: Project, lines: dict[str, LineMap], failed: Failed | None = None
) -> list[Problem]:
    out: list[Problem] = []
    err = Severity.ERROR
    ebn0, table = project.config.ebn0_table, project.config.attenuation_table
    for lid, link in project.links.items():
        file = f"links/{lid}.yaml"
        if (
            link.peer is not None
            and link.peer not in project.ground_stations
            and link.peer not in _failed(failed, "ground_stations")
        ):
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_STATION",
                    "The peer is not a ground station in ground_stations/.",
                    file,
                    ("peer",),
                    lines,
                    "Defined stations: " + ", ".join(sorted(project.ground_stations)) + ".",
                )
            )
        for i, mode in enumerate(link.active_modes):
            if mode not in project.modes and mode not in _failed(failed, "modes"):
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_MODE",
                        "This is not a spacecraft mode in modes/.",
                        file,
                        ("active_modes", i),
                        lines,
                        "Defined modes: " + ", ".join(sorted(project.modes)) + ".",
                    )
                )
        if table is not None and table.entries:
            names = {e.name for e in table.entries}
            for i, name in enumerate(link.attenuation):
                if name not in names:
                    out.append(
                        _p(
                            err,
                            "REF_UNKNOWN_ATTENUATION",
                            "The attenuation is not defined in config/attenuation_table.yaml.",
                            file,
                            ("attenuation", i),
                            lines,
                            "Use a name listed under 'entries' in config/attenuation_table.yaml.",
                        )
                    )
        listed = ebn0 is not None and any(
            e.modulation == link.modulation and e.coding == link.coding for e in ebn0.entries
        )
        if ebn0 is not None and ebn0.entries and not listed:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_MODULATION",
                    "No Eb/N0 entry has this modulation and coding in config/ebn0_table.yaml.",
                    file,
                    ("modulation",),
                    lines,
                    "Add the entry with its source, or correct the names.",
                )
            )
        ground = "receiver" if link.direction == "downlink" else "transmitter"
        antenna = link.receiver.antenna if ground == "receiver" else link.transmitter.antenna
        if antenna is not None and antenna.gain_dbi is None:
            out.append(
                _p(
                    err,
                    "LINK_ANTENNA_PATTERN_GROUND",
                    "A ground antenna has a constant gain; patterns are for the spacecraft end.",
                    file,
                    (ground, "antenna"),
                    lines,
                    "Use gain_dbi (the ground antenna tracks the spacecraft).",
                )
            )
        for side, ant in _antennas(link):
            found = resolve_inside(project.root, ant.pattern_file) if ant.pattern_file else None
            if ant.pattern_file is not None and (found is None or not found.is_file()):
                out.append(
                    _p(
                        err,
                        "LINK_PATTERN_FILE_MISSING",
                        "The antenna pattern file must be inside the project folder."
                        if found is None
                        else "The antenna pattern file does not exist.",
                        file,
                        (side, "antenna", "pattern_file"),
                        lines,
                        "The path is relative to the project folder.",
                    )
                )
    return out


def _ignored_scenario_options(sc: Scenario, file: str, lines: dict[str, LineMap]) -> list[Problem]:
    """Options that the chosen environment source never reads: a warning, since the user
    probably expects them to matter."""
    ignored: list[str] = []
    if sc.environment_source == "elements":
        if sc.import_dir is not None:
            ignored.append("import_dir")
    else:
        if sc.orbit is not None:
            ignored.append("orbit")
        if sc.shadow_model != "cylindrical":
            ignored.append("shadow_model")  # imported eclipse intervals are used as they are
        if sc.earth_model != "wgs84":
            ignored.append("earth_model")  # the imported geometry is not computed here
    return [
        _p(
            Severity.WARNING,
            "SCENARIO_OPTION_IGNORED",
            "This option is not used with the scenario's environment source.",
            file,
            (name,),
            lines,
            "Remove it, or change 'environment_source'.",
        )
        for name in ignored
    ]


def _inside_dir(root: FsPath, rel: str) -> bool:
    found = resolve_inside(root, rel)
    return found is not None and found.is_dir()


def _thermal_references(
    project: Project, lines: dict[str, LineMap], failed: Failed | None = None
) -> list[Problem]:
    out: list[Problem] = []
    err = Severity.ERROR
    model, env = project.config.thermal_model, project.config.thermal_environment
    mfile = "config/thermal_model.yaml"
    if model is not None:
        for i, link in enumerate(model.conductances):
            for field in ("first_node", "second_node"):
                if getattr(link, field) not in model.nodes:
                    out.append(
                        _p(
                            err,
                            "THERMAL_NODE_UNKNOWN",
                            "The conductance names a node that is not defined.",
                            mfile,
                            ("conductances", i, field),
                            lines,
                            "Use a node listed under 'nodes' in config/thermal_model.yaml.",
                        )
                    )
        for i, surface in enumerate(model.surfaces):
            if surface.node not in model.nodes:
                out.append(
                    _p(
                        err,
                        "THERMAL_NODE_UNKNOWN",
                        "The surface names a node that is not defined.",
                        mfile,
                        ("surfaces", i, "node"),
                        lines,
                        "Use a node listed under 'nodes' in config/thermal_model.yaml.",
                    )
                )
            if env is not None:
                for case_name in surface.exposure:
                    if case_name not in env.cases:
                        out.append(
                            _p(
                                err,
                                "REF_UNKNOWN_CASE",
                                "This case is not defined in the thermal environment.",
                                mfile,
                                ("surfaces", i, "exposure", case_name),
                                lines,
                                "Use a case listed under 'cases' in thermal_environment.yaml.",
                            )
                        )
        for uid, unit in project.units.items():
            node = unit.thermal_node or unit.subsystem
            if node not in model.nodes:
                hint = (
                    "Add a node named like the subsystem to config/thermal_model.yaml, or give "
                    "the unit a 'thermal_node'."
                )
                out.append(
                    _p(
                        err,
                        "THERMAL_NODE_UNKNOWN",
                        "The unit's thermal node is not defined in config/thermal_model.yaml.",
                        f"units/{uid}.yaml",
                        ("thermal_node",) if unit.thermal_node else ("subsystem",),
                        lines,
                        hint,
                    )
                )
    if env is not None:
        known = ", ".join(sorted(project.modes))
        for name, case in env.cases.items():
            if case.spacecraft_mode not in project.modes and case.spacecraft_mode not in _failed(
                failed, "modes"
            ):
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_MODE",
                        "This is not a spacecraft mode in modes/.",
                        "config/thermal_environment.yaml",
                        ("cases", name, "spacecraft_mode"),
                        lines,
                        f"Defined modes: {known}.",
                    )
                )
    return out


def _power_system_references(
    project: Project, lines: dict[str, LineMap], failed: Failed | None = None
) -> list[Problem]:
    out: list[Problem] = []
    system = project.config.power_system
    file = "config/power_system.yaml"
    if system is not None:
        for phase in system.battery.max_dod_ratio:
            if phase not in project.phases:
                out.append(
                    _p(
                        Severity.ERROR,
                        "REF_UNKNOWN_PHASE",
                        "This phase is not a mission phase.",
                        file,
                        ("battery", "max_dod_ratio", phase),
                        lines,
                        "Use a name listed under 'mission_phases' in spacecraft.yaml.",
                    )
                )
        known = ", ".join(sorted(project.modes))
        for mode in system.attitude.by_mode:
            if mode not in project.modes and mode not in _failed(failed, "modes"):
                out.append(
                    _p(
                        Severity.ERROR,
                        "REF_UNKNOWN_MODE",
                        "This is not a spacecraft mode in modes/.",
                        file,
                        ("attitude", "by_mode", mode),
                        lines,
                        f"Defined modes: {known}.",
                    )
                )
    for scid, sc in project.scenarios.items():
        if sc.mission_phase is not None and sc.mission_phase not in project.phases:
            out.append(
                _p(
                    Severity.ERROR,
                    "REF_UNKNOWN_PHASE",
                    "This phase is not a mission phase.",
                    f"scenarios/{scid}.yaml",
                    ("mission_phase",),
                    lines,
                    "Use a name listed under 'mission_phases' in spacecraft.yaml.",
                )
            )
        elif (
            sc.mission_phase is not None
            and system is not None
            and sc.mission_phase not in system.battery.max_dod_ratio
        ):
            out.append(
                _p(
                    Severity.WARNING,
                    "SCENARIO_PHASE_NO_DOD",
                    "The battery has no allowed depth of discharge for the mission phase of "
                    "this scenario, so the depth-of-discharge check is not evaluated.",
                    f"scenarios/{scid}.yaml",
                    ("mission_phase",),
                    lines,
                    "Add the phase under battery.max_dod_ratio in config/power_system.yaml.",
                )
            )
    return out


def _mass_references(project: Project, lines: dict[str, LineMap]) -> list[Problem]:
    out: list[Problem] = []
    err = Severity.ERROR
    phases = project.phases
    policy = project.config.margin_policy

    for uid, unit in project.units.items():
        for index, name in enumerate(unit.phases or []):
            if name not in phases:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_PHASE",
                        "This phase is not a mission phase.",
                        f"units/{uid}.yaml",
                        ("phases", index),
                        lines,
                        "Use a name listed under 'mission_phases' in spacecraft.yaml.",
                    )
                )

    for eid, exp in project.expendables.items():
        file = f"expendables/{eid}.yaml"
        if policy is not None and exp.maturity not in policy.classes:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_MATURITY",
                    "The maturity class is not defined in config/margin_policy.yaml.",
                    file,
                    ("maturity",),
                    lines,
                    "Use a class listed under 'classes' in config/margin_policy.yaml.",
                )
            )
        for index, phase in enumerate(phases):
            if phase not in exp.masses_kg:
                where = (
                    f"mission_phases[{index}] in spacecraft.yaml"
                    if project.spacecraft.mission_phases
                    else "the implicit phase 'all'"
                )
                out.append(
                    _p(
                        err,
                        "PHASE_MASS_MISSING",
                        f"No mass is given for the phase {where}.",
                        file,
                        ("masses_kg",),
                        lines,
                        "Add an entry named like that phase, with its mass in kg (write 0.0 if it "
                        "is not present).",
                    )
                )
        for phase in exp.masses_kg:
            if phase not in phases:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_PHASE",
                        "This phase is not a mission phase.",
                        file,
                        ("masses_kg", phase),
                        lines,
                        "Use a name listed under 'mission_phases' in spacecraft.yaml.",
                    )
                )

    limits = project.config.mass_limits
    for index, limit in enumerate(limits.limits if limits else []):
        if limit.phase is not None and limit.phase not in phases:
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_PHASE",
                    "This phase is not a mission phase.",
                    "config/mass_limits.yaml",
                    ("limits", index, "phase"),
                    lines,
                    "Use a name listed under 'mission_phases' in spacecraft.yaml.",
                )
            )

    uses_positions = any(u.mass_properties for u in project.units.values()) or any(
        e.mass_properties for e in project.expendables.values()
    )
    if uses_positions and not project.spacecraft.body_frame.strip():
        out.append(
            _p(
                Severity.WARNING,
                "MASS_FRAME_UNDEFINED",
                "Positions are given but the body frame is not described.",
                "spacecraft.yaml",
                ("body_frame",),
                lines,
                "Describe the axes and origin in 'body_frame' (for example: origin at the "
                "centre of the launch interface plane, +Z along the launch axis).",
            )
        )
    return out


def _environment_references(
    project: Project, lines: dict[str, LineMap], failed: Failed | None = None
) -> list[Problem]:
    from budget_core.environment.elements import check_orbit

    out: list[Problem] = []
    err, warn = Severity.ERROR, Severity.WARNING

    for oid, orbit in project.orbits.items():
        reason = check_orbit(orbit)
        if reason:
            out.append(
                _p(
                    err,
                    "ORBIT_INVALID",
                    f"{reason}.",
                    f"orbits/{oid}.yaml",
                    ("elements",) if orbit.elements else ("tle",),
                    lines,
                    "Check the elements (a perigee below the Earth's surface is not valid) "
                    "or the TLE.",
                )
            )

    for sid in sorted(set(project.ground_stations) & set(project.targets)):
        out.append(
            _p(
                err,
                "DUPLICATE_ID",
                f"The id '{sid}' is used by a ground station and by a target.",
                f"targets/{sid}.yaml",
                (),
                lines,
                "Site ids must be unique across ground_stations/ and targets/.",
            )
        )
    sites = set(project.ground_stations) | set(project.targets)

    if "model_choices" not in project.meta.requires and any(
        sc.earth_model != "wgs84" for sc in project.scenarios.values()
    ):
        out.append(
            _p(
                warn,
                "FEATURE_NOT_DECLARED",
                "The project uses a model choice that an older version would not know, and "
                "does not list the feature in 'requires'.",
                "project.yaml",
                ("requires",),
                lines,
                "Add 'model_choices' to 'requires' in project.yaml, so that an older version "
                "refuses the project instead of ignoring the choice.",
            )
        )
    for scid, sc in project.scenarios.items():
        file = f"scenarios/{scid}.yaml"
        if (
            sc.environment_source == "elements"
            and sc.orbit not in project.orbits
            and sc.orbit not in _failed(failed, "orbits")
        ):
            out.append(
                _p(
                    err,
                    "REF_UNKNOWN_ORBIT",
                    "The orbit does not exist in orbits/.",
                    file,
                    ("orbit",),
                    lines,
                    "Defined orbits: " + ", ".join(sorted(project.orbits)) + ".",
                )
            )
        out.extend(_ignored_scenario_options(sc, file, lines))
        used_orbit = project.orbits.get(sc.orbit) if sc.orbit else None
        if (
            sc.environment_source == "elements"
            and sc.earth_model != "wgs84"
            and (used_orbit is not None and used_orbit.tle is not None)
        ):
            out.append(
                _p(
                    warn,
                    "MODEL_CHOICE_IGNORED",
                    "The Earth model does not apply to an orbit given as a TLE.",
                    file,
                    ("earth_model",),
                    lines,
                    "A TLE is propagated on WGS-72, the set SGP4 is defined on. Remove the "
                    "option, or give the orbit as elements.",
                )
            )
        missing_import = (
            sc.environment_source == "spacemissionstudio"
            and sc.import_dir is not None
            and not _inside_dir(project.root, sc.import_dir)
        )
        if missing_import:
            out.append(
                _p(
                    err,
                    "IMPORT_DIR_MISSING",
                    "The SpaceMissionStudio import folder must be an existing folder inside "
                    "the project folder.",
                    file,
                    ("import_dir",),
                    lines,
                    "The path is relative to the project folder.",
                )
            )
        for index, site in enumerate(sc.sites):
            if site not in sites and site not in _failed(failed, "ground_stations", "targets"):
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_SITE",
                        "This site does not exist.",
                        file,
                        ("sites", index),
                        lines,
                        "Use the file name (without .yaml) of a ground station or target.",
                    )
                )
        for index, rule in enumerate(sc.rules):
            if rule.site is not None and rule.site not in sc.sites:
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_SITE",
                        "The rule uses a site that the scenario does not list.",
                        file,
                        ("rules", index, "site"),
                        lines,
                        "Add the site to 'sites' of the scenario.",
                    )
                )
        known = ", ".join(sorted(project.modes))
        wanted = [("default_mode", sc.default_mode)]
        wanted += [(f"rules[{i}].mode", r.mode) for i, r in enumerate(sc.rules)]
        wanted += [(f"segments[{i}].mode", s.mode) for i, s in enumerate(sc.segments)]
        for path, mode in wanted:
            if mode not in project.modes and mode not in _failed(failed, "modes"):
                parts: tuple[str | int, ...] = tuple(
                    int(x) if x.isdigit() else x
                    for x in path.replace("]", "").replace("[", ".").split(".")
                )
                out.append(
                    _p(
                        err,
                        "REF_UNKNOWN_MODE",
                        "This is not a spacecraft mode in modes/.",
                        file,
                        parts,
                        lines,
                        f"Defined modes: {known}.",
                    )
                )
    return out
