"""`budget import idm`: start or update a project from an IDM-CIC model (decisions D-240 to D-243).

Reads models from IDM-CIC (c) CNES. The command reads the model file with this tool's own code,
shows what it would write (a plan) and, with `--apply`, writes it. Without `--apply` nothing is
written. Messages name objects by their ids in the model, never a value read from the file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from budget_core.idm.importer import ImportPlan, apply_plan, plan_import
from budget_core.idm.mapping import MARGINS, MASS_PROPERTIES, ImportOptions, slug
from budget_core.idm.reader import read_idm
from budget_core.idm.summary import counts, plan_summary
from budget_core.io.project_loader import load_project
from budget_core.problems import Problem, Severity


def add_parser(sub: Any) -> None:
    imp = sub.add_parser(
        "import", help="Start or update a project from a model of another program."
    )
    kinds = imp.add_subparsers(dest="import_kind", required=True)
    idm = kinds.add_parser(
        "idm",
        help="Start or update a project from an IDM-CIC model file (.idm). Reads models from "
        "IDM-CIC (c) CNES; shows a plan, and with --apply writes it.",
    )
    idm.add_argument("file", type=Path, help="The IDM-CIC model file (.idm).")
    idm.add_argument(
        "--project",
        type=Path,
        help="The project folder: a folder without a project is created, a project is updated "
        "(default: a new folder named after the model file, in the current folder).",
    )
    idm.add_argument(
        "--margins",
        choices=MARGINS,
        default="raw",
        help="raw (default): masses and powers as the model gives them, margins by the maturity "
        "classes of the project; applied: the model's margins are applied to the values and the "
        "classes carry none. Margins are never applied twice.",
    )
    idm.add_argument(
        "--mass-properties",
        choices=MASS_PROPERTIES,
        default="geometry",
        help="geometry (default): work out the centre of gravity and the inertia of each unit "
        "from the placements and shapes of the model, marked as estimates; none: leave them out.",
    )
    idm.add_argument(
        "--bus", default="main", help="Power bus of every imported unit (default main)."
    )
    idm.add_argument(
        "--bus-voltage-v",
        type=float,
        help="Nominal voltage of the bus; required to create a new project.",
    )
    idm.add_argument("--apply", action="store_true", help="Write the files (default: only show).")
    idm.add_argument("--format", choices=("text", "json"), default="text")


def _fail(text: str) -> int:
    sys.stdout.flush()
    print(text, file=sys.stderr)
    return 1


def run(args: argparse.Namespace) -> int:
    read = read_idm(args.file)
    for problem in read.problems:
        if problem.severity is Severity.ERROR:
            print(problem.format(), file=sys.stderr)
    if not read.ok or read.model is None:
        return _fail("The model could not be read; nothing was written.")
    model = read.model
    root = args.project or Path(slug(args.file.stem))
    options = ImportOptions(
        margins=args.margins, bus=args.bus, mass_properties=args.mass_properties
    )
    plan = plan_import(model, root, options, bus_voltage_v=args.bus_voltage_v)
    errors = [p for p in plan.problems if p.severity is Severity.ERROR]
    if errors:
        for problem in errors:
            print(problem.format(), file=sys.stderr)
        return _fail("The import cannot be done; nothing was written.")
    notes = [*read.problems, *plan.problems]
    if args.format == "json":
        print(json.dumps(_as_json(plan, notes, args.apply), indent=2, sort_keys=True))
    else:
        print(plan_summary(plan, notes, model.source_name, model.sha256))
    if not args.apply:
        if args.format == "text":
            print(f"Nothing was written. Add --apply to write {len(plan.files)} file(s).")
        return 0
    written = apply_plan(plan)
    if args.format == "text":
        print(f"Wrote {len(written)} file(s) into {root}.")
        loaded = load_project(root)
        errors_n = sum(1 for p in loaded.problems if p.severity is Severity.ERROR)
        warnings_n = sum(1 for p in loaded.problems if p.severity is Severity.WARNING)
        print(f"The project check finds {errors_n} error(s) and {warnings_n} warning(s).")
    return 0


def _as_json(plan: ImportPlan, notes: list[Problem], applied: bool) -> dict[str, Any]:
    return {
        "project": str(plan.root),
        "new_project": plan.new_project,
        "applied": applied,
        "counts": counts(plan),
        "files": [{"path": f.path, "action": f.action} for f in plan.files],
        "problems": [p.to_dict() for p in notes],
    }
