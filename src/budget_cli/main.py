"""`budget` command: new, validate, run, scenario, power-timeline, link-passes, compare, guide,
self-test, export-schemas, units-export, units-import, export-examples."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from budget_core import APP_NAME, __version__
from budget_core.blank import BlankAnswers, create_blank_project
from budget_core.compare_run import ALL_KINDS, Side, compare_sides, default_kinds
from budget_core.examples import ExportRefusedError, export_examples
from budget_core.io.project_loader import LoadResult, load_project
from budget_core.io.unit_table import (
    apply_plan,
    plan_import,
    read_table,
    table_csv,
    table_xlsx,
)
from budget_core.link.evaluate import link_pass_series, link_static_budget
from budget_core.mass.static_mass import static_mass_budget
from budget_core.model import Project
from budget_core.power.static_budget import static_power_budget
from budget_core.power.time_domain import time_domain_budget, violation_problems
from budget_core.problems import Problem, Severity, sort_problems
from budget_core.provenance import ProvenanceError, make_provenance
from budget_core.reports.files import OutputError, write_file
from budget_core.reports.run import (
    REPORT_KINDS,
    BudgetOutput,
    link_output,
    mass_output,
    power_output,
    thermal_output,
    timeline_output,
    write_outputs,
)
from budget_core.scenario.export import write_scenario_outputs
from budget_core.scenario.run import ScenarioRunError, run_scenario
from budget_core.schemas import export_schemas
from budget_core.selftest import run_selftest
from budget_core.thermal.static_thermal import static_thermal_budget
from budget_core.timeutil import MAX_YEAR, MIN_YEAR
from budget_core.wizard import WizardError

REPORTS = REPORT_KINDS
COMPARE_KINDS = ALL_KINDS


def _iso_datetime(text: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 date and time, e.g. 2026-01-02T03:04:05Z"
        ) from None
    parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    try:
        year = parsed.astimezone(UTC).year
    except (OverflowError, ValueError):
        year = 0
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise argparse.ArgumentTypeError(
            f"the date must fall in the years {MIN_YEAR} to {MAX_YEAR} (UTC)"
        )
    return parsed


def _folder(text: str) -> Path:
    if not text.strip():
        raise argparse.ArgumentTypeError("expected a folder name (an empty value is not a folder)")
    return Path(text)


def _at_least(minimum: int, what: str) -> Callable[[str], int]:
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"expected a whole number, {what}") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"expected a whole number, {what}")
        return value

    return parse


class _Parser(argparse.ArgumentParser):
    """No abbreviated options: `--str` must not silently mean `--strict`."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(**kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="budget", description=f"{APP_NAME} command line.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    new = sub.add_parser(
        "new",
        help="Create a blank project: a spacecraft with one bus, placeholder configuration, "
        "no units.",
    )
    new.add_argument("folder", type=_folder, help="The project folder to create (must not exist).")
    new.add_argument(
        "--bus-voltage-v",
        type=float,
        required=True,
        metavar="VOLTS",
        help="Nominal voltage of the main bus, in volts (no default: it is your design value).",
    )
    new.add_argument(
        "--name", help="Project name (default: the name of the folder).", metavar="TEXT"
    )
    new.add_argument(
        "--bus-name", default="main", metavar="TEXT", help="Name of the bus (default: main)."
    )
    new.add_argument(
        "--spacecraft-name",
        default="",
        metavar="TEXT",
        help="Spacecraft name (default: the project name).",
    )

    val = sub.add_parser("validate", help="Check a project folder and list problems.")
    val.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    val.add_argument("--format", choices=("text", "json"), default="text")
    val.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    run = sub.add_parser("run", help="Compute a budget and write reports and exports.")
    run.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    run.add_argument(
        "--budget",
        choices=("power", "mass", "thermal", "link", "all"),
        default="all",
        help="Budget to compute (default: all).",
    )
    run.add_argument(
        "--report",
        action="append",
        choices=REPORTS + ("all",),
        help="Output kind; repeat for several (default: all).",
    )
    run.add_argument("--out", type=_folder, help="Output folder (default: <project>/results).")
    run.add_argument(
        "--user", help="User name for the provenance block (default: BUDGET_USER or login)."
    )
    run.add_argument(
        "--date",
        type=_iso_datetime,
        help="Generation time, ISO 8601 (default: SOURCE_DATE_EPOCH or now).",
    )
    run.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    scn = sub.add_parser(
        "scenario", help="Compute a scenario's eclipses, passes and mode timeline."
    )
    scn.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    scn.add_argument(
        "--scenario", help="Scenario id (file name in scenarios/); optional if only one."
    )
    scn.add_argument("--out", type=_folder, help="Output folder (default: <project>/results).")
    scn.add_argument("--user", help="User name for the provenance block.")
    scn.add_argument("--date", type=_iso_datetime, help="Generation time, ISO 8601.")

    pt = sub.add_parser(
        "power-timeline",
        help="Compute the time-domain power budget of a scenario (array, battery, violations).",
    )
    pt.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    pt.add_argument(
        "--scenario", help="Scenario id (file name in scenarios/); optional if only one."
    )
    pt.add_argument(
        "--case",
        choices=("bol", "eol", "both"),
        default="both",
        help="Beginning of life, end of life or both (default: both).",
    )
    pt.add_argument(
        "--load-basis",
        choices=("nominal", "margined"),
        default="nominal",
        help="Demand without margins or with unit and system margins (default: nominal).",
    )
    pt.add_argument("--phase", help="Mission phase for the depth-of-discharge limit.")
    pt.add_argument(
        "--report",
        action="append",
        choices=REPORTS + ("all",),
        help="Output kind; repeat for several (default: all).",
    )
    pt.add_argument("--out", type=_folder, help="Output folder (default: <project>/results).")
    pt.add_argument(
        "--series-every",
        type=_at_least(1, "1 or more"),
        default=1,
        metavar="N",
        help="Keep every N-th step in the series CSV (default 1: all steps).",
    )
    pt.add_argument("--no-plots", action="store_true", help="Leave the plots out of the reports.")
    pt.add_argument("--user", help="User name for the provenance block.")
    pt.add_argument("--date", type=_iso_datetime, help="Generation time, ISO 8601.")
    pt.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    lp = sub.add_parser(
        "link-passes",
        help="Compute the link margin, selected data rate and data volume over every pass.",
    )
    lp.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    lp.add_argument(
        "--scenario", help="Scenario id (file name in scenarios/); optional if only one."
    )
    lp.add_argument(
        "--report",
        action="append",
        choices=REPORTS + ("all",),
        help="Output kind; repeat for several (default: all).",
    )
    lp.add_argument("--out", type=_folder, help="Output folder (default: <project>/results).")
    lp.add_argument("--no-plots", action="store_true", help="Leave the plots out of the reports.")
    lp.add_argument("--user", help="User name for the provenance block.")
    lp.add_argument("--date", type=_iso_datetime, help="Generation time, ISO 8601.")
    lp.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    cmp = sub.add_parser(
        "compare",
        help="Compare two project revisions, or two scenarios of one project, side by side.",
    )
    cmp.add_argument("project", type=Path, help="First project folder (side A).")
    cmp.add_argument(
        "other", type=Path, nargs="?", help="Second project folder (side B; default: the first)."
    )
    cmp.add_argument("--scenario", help="Scenario id used on both sides.")
    cmp.add_argument("--scenario-a", help="Scenario id of side A.")
    cmp.add_argument("--scenario-b", help="Scenario id of side B.")
    cmp.add_argument(
        "--budget",
        action="append",
        choices=COMPARE_KINDS + ("all",),
        help="Budget to compare; repeat for several (default: all that apply).",
    )
    cmp.add_argument(
        "--report",
        action="append",
        choices=REPORTS + ("all",),
        help="Output kind; repeat for several (default: all).",
    )
    cmp.add_argument("--out", type=_folder, help="Output folder (default: <project>/results).")
    cmp.add_argument(
        "--max-rows",
        type=_at_least(0, "0 or more"),
        default=200,
        metavar="N",
        help="Differences the report lists per budget (default 200; the CSV and JSON list all).",
    )
    cmp.add_argument("--user", help="User name for the provenance block.")
    cmp.add_argument("--date", type=_iso_datetime, help="Generation time, ISO 8601.")

    gde = sub.add_parser(
        "guide", help="Write the user guide (offline HTML and PDF) with the Equations and sources."
    )
    gde.add_argument("--out", type=_folder, required=True, help="Output folder.")
    gde.add_argument("--format", choices=("html", "pdf", "all"), default="all")
    gde.add_argument(
        "--project",
        type=Path,
        help="Also list the numbers and sources of this project's configuration.",
    )

    sub.add_parser(
        "self-test", help="Check that this installation can compute and render a budget."
    )

    sch = sub.add_parser("export-schemas", help="Write the JSON Schema of every file kind.")
    sch.add_argument("out_dir", type=Path)

    ue = sub.add_parser(
        "units-export",
        help="Write the unit power modes as a CSV or XLSX table to fill in outside the tool.",
    )
    ue.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    ue.add_argument(
        "--out",
        type=Path,
        help="Output file, .csv or .xlsx (default: <project>/results/unit_power_modes.csv).",
    )

    ui = sub.add_parser(
        "units-import",
        help="Read a unit table (.csv or .xlsx) and show, or with --apply write, the changes.",
    )
    ui.add_argument("project", type=Path, help="Project folder (contains project.yaml).")
    ui.add_argument("table", type=Path, help="The filled-in table, .csv or .xlsx.")
    ui.add_argument(
        "--apply",
        action="store_true",
        help="Write the changes into the unit files (without it nothing is written).",
    )

    exa = sub.add_parser(
        "export-examples", help="Write the synthetic example projects (invented data)."
    )
    exa.add_argument("out_dir", type=Path)
    exa.add_argument(
        "--force",
        action="store_true",
        help="Replace the files of example projects that already exist in the folder.",
    )
    return parser


def _count(problems: list[Problem], severity: Severity) -> int:
    return sum(1 for p in problems if p.severity is severity)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _fail(text: str) -> None:
    """Say on standard error why a command could not do its work (D-145). Standard output is
    flushed first so the two streams read in order on a terminal and in `2>&1`."""
    sys.stdout.flush()
    print(text, file=sys.stderr)


def _validate(args: argparse.Namespace) -> int:
    result = load_project(args.project)
    problems = result.problems
    errors = _count(problems, Severity.ERROR)
    warnings = _count(problems, Severity.WARNING)
    if args.format == "json":
        payload = {
            "errors": errors,
            "warnings": warnings,
            "problems": [p.to_dict() for p in problems],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not problems:
        print("No problems found.")
    else:
        for problem in problems:
            print(problem.format())
        print(f"{_plural(errors, 'error')}, {_plural(warnings, 'warning')}.")
    return 1 if errors or (args.strict and warnings) else 0


def _valid_project(path: Path) -> tuple[Project | None, int]:
    """The project, or None after printing why it cannot be used (exit code 1)."""
    loaded = load_project(path)
    errors = _count(loaded.problems, Severity.ERROR)
    if loaded.project is None or errors:
        for problem in loaded.problems:
            _fail(problem.format())
        _fail(f"{_plural(errors, 'error')}; nothing was written.")
        return None, 1
    return loaded.project, 0


def _units_export(args: argparse.Namespace) -> int:
    out = args.out or (args.project / "results" / "unit_power_modes.csv")
    kind = out.suffix.lower()
    if kind not in (".csv", ".xlsx"):  # checked first: no need to load a project for this
        _fail("The output file must end in .csv or .xlsx.")
        return 2
    project, code = _valid_project(args.project)
    if project is None:
        return code
    data = (
        # a byte order mark makes Excel read the UTF-8 text correctly
        b"\xef\xbb\xbf" + table_csv(project).encode("utf-8")
        if kind == ".csv"
        else table_xlsx(project)
    )
    path = write_file(out.parent, out.name, data, sanitise=False)
    print(f"Wrote {path}")
    return 0


def _format_number(value: float | None) -> str:
    return "(new)" if value is None else f"{value:g}"


def _units_import(args: argparse.Namespace) -> int:
    project, code = _valid_project(args.project)
    if project is None:
        return code
    table = read_table(args.table)
    plan = plan_import(project, table, args.table.name)
    if not plan.ok:
        for problem in plan.problems:
            _fail(problem.format())
        errors = sum(1 for p in plan.problems if p.severity is Severity.ERROR)
        _fail(f"{_plural(errors, 'error')}; nothing was written.")
        return 1
    for problem in plan.problems:
        print(problem.format())
    if not plan.changes:
        print(f"No change: {_plural(plan.unchanged, 'power mode')} already as in the table.")
        return 0
    for change in plan.changes:
        print(
            f"{change.unit_id} / {change.power_mode}: {change.field} "
            f"{_format_number(change.old)} -> {change.new:g} (row {change.line})"
        )
    modes = {(c.unit_id, c.power_mode) for c in plan.changes}
    print(
        f"{_plural(len(plan.changes), 'value')} in {_plural(len(modes), 'power mode')} "
        f"{'changed' if args.apply else 'would change'}; {plan.unchanged} already as in the table."
    )
    if not args.apply:
        print("Nothing was written. Add --apply to write the changes.")
        return 0
    for path in apply_plan(args.project, plan):
        print(f"Wrote units/{path.name}")
    return 0


# Warnings that every placeholder produces: the INCOMPLETE banner and the reports list them, so
# the command line only counts them (`budget validate` lists them one by one).
_COUNTED_ONLY = frozenset({"CONFIG_PLACEHOLDER", "RESULT_INCOMPLETE"})


def _load_or_fail(path: Path) -> tuple[LoadResult | None, int]:
    """The loaded project, or None after printing why it cannot be used (exit code 1)."""
    loaded = load_project(path)
    errors = _count(loaded.problems, Severity.ERROR)
    if loaded.project is None or errors:
        for problem in loaded.problems:
            _fail(problem.format())
        _fail(f"{_plural(errors, 'error')}; nothing was written.")
        return None, 1
    return loaded, 0


def _finish(problems: Sequence[Problem], outputs: Sequence[BudgetOutput], strict: bool) -> int:
    """The same ending for every computing command: print the findings (errors) and the warnings
    that need a person, then the banner of the first incomplete output and one summary line.
    Load problems count like any other, so `--strict` means the same everywhere."""
    ordered = sort_problems(dict.fromkeys(problems))
    errors = [p for p in ordered if p.severity is Severity.ERROR]
    warnings = [p for p in ordered if p.severity is Severity.WARNING]
    for problem in ordered:
        if problem.severity is Severity.ERROR:
            _fail(problem.format())
        elif problem.severity is Severity.WARNING and problem.code not in _COUNTED_ONLY:
            print(problem.format())
    banner = next((o.document.banner for o in outputs if o.document.banner), "")
    if banner:
        print(banner)
    print(f"{_plural(len(errors), 'error')}, {_plural(len(warnings), 'warning')}.")
    return 1 if errors or (strict and warnings) else 0


def _choose_scenario(project: Project, requested: str | None) -> tuple[str | None, int]:
    """The scenario id to compute, or None after printing why there is none (exit code)."""
    if requested is not None:
        return requested, 0
    ids = sorted(project.scenarios)
    if not ids:
        _fail("The project has no scenarios (scenarios/*.yaml); nothing to compute.")
        return None, 1
    if len(ids) > 1:
        _fail(
            "The project has several scenarios; choose one with --scenario. "
            "Scenarios: " + ", ".join(ids) + "."
        )
        return None, 2
    return ids[0], 0


def _run(args: argparse.Namespace) -> int:
    loaded, code = _load_or_fail(args.project)
    if loaded is None or loaded.project is None:
        return code
    project = loaded.project
    if args.budget == "link" and not project.links:
        print("The project has no links (links/*.yaml); no link budget was computed.")
        return 1
    provenance = make_provenance(project, user=args.user, generated_at=args.date)
    outputs: list[BudgetOutput] = []
    problems: list[Problem] = list(loaded.problems)
    if args.budget in ("power", "all"):
        power = static_power_budget(project)
        outputs.append(power_output(project, power, provenance, loaded.problems))
        problems += power.problems
    if args.budget in ("mass", "all"):
        mass = static_mass_budget(project)
        outputs.append(mass_output(project, mass, provenance, loaded.problems))
        problems += mass.problems

    if args.budget in ("thermal", "all"):
        thermal = static_thermal_budget(project)
        outputs.append(thermal_output(project, thermal, provenance, loaded.problems))
        problems += thermal.problems

    if args.budget in ("link", "all") and project.links:
        link = link_static_budget(project)
        outputs.append(link_output(project, link, provenance, loaded.problems))
        problems += link.problems

    wanted = set(args.report or ["all"])
    if "all" in wanted:
        wanted = set(REPORTS)
    out_dir = args.out or (args.project / "results")
    written = write_outputs(outputs, out_dir, wanted)
    for path in written:
        print(f"Wrote {path}")
    return _finish(problems, outputs, args.strict)


def _scenario(args: argparse.Namespace) -> int:
    loaded, code = _load_or_fail(args.project)
    if loaded is None or loaded.project is None:
        return code
    project = loaded.project
    scenario_id, code = _choose_scenario(project, args.scenario)
    if scenario_id is None:
        return code
    try:
        run = run_scenario(project, scenario_id)
    except ScenarioRunError as exc:
        _fail(exc.problem.format())
        return 1
    provenance = make_provenance(
        project, scenario=run.scenario_id, user=args.user, generated_at=args.date
    )
    written = write_scenario_outputs(run, provenance, args.out or (args.project / "results"))
    env = run.env
    passes = ", ".join(f"{sid} {len(v.passes)}" for sid, v in sorted(env.sites.items()))
    print(
        f"Scenario {run.scenario_id} ({env.source}): {len(env.eclipses)} eclipse(s)"
        + (f"; passes: {passes}" if passes else "")
        + f"; {len(run.timeline)} timeline segment(s)."
    )
    for note in run.notes:
        print(f"Note: {note}")
    for problem in run.problems:
        print(problem.format())
    for path in written:
        print(f"Wrote {path}")
    return 0


def _link_passes(args: argparse.Namespace) -> int:
    loaded, code = _load_or_fail(args.project)
    if loaded is None or loaded.project is None:
        return code
    project = loaded.project
    if not project.links:
        _fail("The project has no links (links/*.yaml); nothing to compute.")
        return 1
    scenario_id, code = _choose_scenario(project, args.scenario)
    if scenario_id is None:
        return code
    try:
        run = run_scenario(project, scenario_id)
    except ScenarioRunError as exc:
        _fail(exc.problem.format())
        return 1
    static = link_static_budget(project)
    passes = link_pass_series(project, run)
    provenance = make_provenance(
        project, scenario=run.scenario_id, user=args.user, generated_at=args.date
    )
    output = link_output(
        project, static, provenance, loaded.problems, passes, plots=not args.no_plots
    )
    wanted = set(args.report or ["all"])
    if "all" in wanted:
        wanted = set(REPORTS)
    written = write_outputs([output], args.out or (args.project / "results"), wanted)
    for path in written:
        print(f"Wrote {path}")
    for s in passes.series:
        if s.volume_bits is None:
            print(f"{s.link_id}: n/a (inputs missing, see the problems below).")
        else:
            per_day = (
                "n/a"
                if s.volume_per_day_bits is None
                else f"{s.volume_per_day_bits / 8e6:.2f} MByte"
            )
            print(
                f"{s.link_id}: {len(s.passes)} pass(es) over {s.site}, "
                f"{s.volume_bits / 8e6:.2f} MByte in the scenario ({per_day} per day)."
            )
    return _finish([*loaded.problems, *static.problems, *passes.problems], [output], args.strict)


def _power_timeline(args: argparse.Namespace) -> int:
    loaded, code = _load_or_fail(args.project)
    if loaded is None or loaded.project is None:
        return code
    project = loaded.project
    scenario_id, code = _choose_scenario(project, args.scenario)
    if scenario_id is None:
        return code
    try:
        run = run_scenario(project, scenario_id)
    except ScenarioRunError as exc:
        _fail(exc.problem.format())
        return 1
    cases = ("bol", "eol") if args.case == "both" else (args.case,)
    result = time_domain_budget(
        project, run, load_basis=args.load_basis, cases=cases, mission_phase=args.phase
    )
    provenance = make_provenance(
        project, scenario=run.scenario_id, user=args.user, generated_at=args.date
    )
    output = timeline_output(
        project,
        result,
        provenance,
        loaded.problems,
        plots=not args.no_plots,
        series_every=args.series_every,
    )
    wanted = set(args.report or ["all"])
    if "all" in wanted:
        wanted = set(REPORTS)
    written = write_outputs([output], args.out or (args.project / "results"), wanted)
    for path in written:
        print(f"Wrote {path}")
    for case in result.cases:
        s = case.summary
        if s.generated_wh is None:
            print(f"{case.case.upper()}: n/a (inputs missing, see the problems below).")
            continue
        soc = "n/a" if s.minimum_soc_ratio is None else f"{s.minimum_soc_ratio * 100:.1f} %"
        print(
            f"{case.case.upper()}: generated {s.generated_wh:.1f} Wh, lowest state of charge "
            f"{soc}, {result.violation_count(case.case)} violation(s)."
        )
    if result.not_evaluated:
        print(f"Not evaluated: {result.not_evaluated_text()}.")
    problems = [*loaded.problems, *result.problems, *violation_problems(result)]
    return _finish(problems, [output], args.strict)


def _compare(args: argparse.Namespace) -> int:
    other = args.other or args.project
    scenario_a = args.scenario_a or args.scenario
    scenario_b = args.scenario_b or args.scenario
    if args.other is None and (
        scenario_a is None or scenario_b is None or scenario_a == scenario_b
    ):
        _fail(
            "Give a second project folder, or two different scenarios "
            "(--scenario-a and --scenario-b) of the same project."
        )
        return 2
    sides: list[Side] = []
    for path, scenario in ((args.project, scenario_a), (other, scenario_b)):
        loaded = load_project(path)
        errors = _count(loaded.problems, Severity.ERROR)
        if loaded.project is None or errors:
            for problem in loaded.problems:
                _fail(problem.format())
            _fail(f"{_plural(errors, 'error')}; nothing was written.")
            return 1
        sides.append(Side(loaded.project, scenario))
    a, b = sides
    wanted = args.budget or ["all"]
    kinds = (
        default_kinds(a, b, same_project=args.other is None)
        if "all" in wanted
        else tuple(k for k in ALL_KINDS if k in wanted)
    )
    try:
        output, notes = compare_sides(
            a, b, kinds, user=args.user, generated_at=args.date, max_rows=args.max_rows
        )
    except ScenarioRunError as exc:
        _fail(exc.problem.format())
        return 1
    reports = set(args.report or ["all"])
    if "all" in reports:
        reports = set(REPORTS)
    written = write_outputs([output], args.out or (args.project / "results"), reports)
    for path in written:
        print(f"Wrote {path}")
    for note in notes:
        print(f"Note: {note}")
    for result in output.result:
        print(f"{result.name}: {result.summary_line}")
    if output.document.banner:
        print(output.document.banner)
    return 0


def _guide(args: argparse.Namespace) -> int:
    from budget_core.guide.build import build_guide

    project = None
    if args.project is not None:
        loaded = load_project(args.project)
        errors = _count(loaded.problems, Severity.ERROR)
        if loaded.project is None or errors:
            for problem in loaded.problems:
                _fail(problem.format())
            _fail(f"{_plural(errors, 'error')}; nothing was written.")
            return 1
        project = loaded.project
    guide = build_guide(project)
    stem = "system-budget-studio-guide"
    if args.format in ("html", "all"):
        from budget_core.guide.html import render_html

        path = write_file(args.out, f"{stem}.html", render_html(guide), sanitise=False)
        print(f"Wrote {path}")
    if args.format in ("pdf", "all"):
        from budget_core.guide.pdf import render_pdf

        path = write_file(args.out, f"{stem}.pdf", render_pdf(guide), sanitise=False)
        print(f"Wrote {path}")
    return 0


def _new(args: argparse.Namespace) -> int:
    folder: Path = args.folder
    answers = BlankAnswers(
        project_name=args.name if args.name is not None else folder.resolve().name,
        bus_voltage_v=args.bus_voltage_v,
        bus_name=args.bus_name,
        spacecraft_name=args.spacecraft_name,
    )
    try:
        created = create_blank_project(answers, folder)
    except WizardError as exc:
        _fail(str(exc))
        return 1
    print(f"Created the blank project {created}")
    print(f"Next: add units, an orbit and a scenario, then run 'budget validate {created}'.")
    return 0


def _dispatch(
    args: argparse.Namespace, parser: argparse.ArgumentParser, argv: Sequence[str] | None
) -> int:
    if args.command == "new":
        return _new(args)
    if args.command == "validate":
        return _validate(args)
    if args.command == "scenario":
        return _scenario(args)
    if args.command == "link-passes":
        return _link_passes(args)
    if args.command == "guide":
        return _guide(args)
    if args.command == "compare":
        return _compare(args)
    if args.command == "power-timeline":
        return _power_timeline(args)
    if args.command == "self-test":
        failures = run_selftest()
        for failure in failures:
            _fail(f"FAILED: {failure}")
        if failures:
            _fail(f"{len(failures)} check(s) failed.")
        else:
            print("Self-test passed.")
        return 1 if failures else 0
    if args.command == "run":
        return _run(args)
    if args.command == "units-export":
        return _units_export(args)
    if args.command == "units-import":
        return _units_import(args)
    if args.command == "export-schemas":
        for path in export_schemas(args.out_dir):
            print(path.name)
        return 0
    if args.command == "export-examples":
        for name in export_examples(args.out_dir, force=args.force):
            print(name)
        return 0
    parser.print_help(sys.stderr)  # no command: show what there is, and fail like a bad argument
    return 2


def _encode_safely() -> None:
    """A terminal or a redirected stream that cannot encode a character (a cp1252 console and a
    project named in Chinese) must not turn a finished run into an error: the character is
    written as a backslash escape instead."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError, OSError):  # a closed stream, or not text
                reconfigure(errors="backslashreplace")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command. Nothing unexpected reaches the user as a traceback or as project text:
    only the kind of the failure is named (spec constraints 11 and 20)."""
    _encode_safely()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args, parser, argv)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:  # the reader of our output went away (for example `| head`)
        return 1
    except OutputError as exc:
        _fail(str(exc))
        return 1
    except ExportRefusedError as exc:
        _fail(str(exc))
        return 1
    except ProvenanceError as exc:
        _fail(str(exc))
        return 2
    except OSError:
        _fail(
            "A file or folder could not be read or written. Check the paths and that you "
            "may use them."
        )
        return 1
    except Exception as exc:
        advice = (
            "Please report the problem."
            if args.command == "validate"
            else "Run 'budget validate <project folder>' to check the project and report the "
            "problem."
        )
        _fail(f"Internal error ({type(exc).__name__}). {advice}")
        return 1
