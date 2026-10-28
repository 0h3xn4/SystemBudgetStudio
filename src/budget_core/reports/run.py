"""Build and write budget outputs; shared by the CLI and the GUI."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from budget_core.link.evaluate import LinkSeriesResult, StaticLinkResult
from budget_core.mass.static_mass import StaticMassResult
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult
from budget_core.power.time_domain import TimeDomainResult
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.csvutil import provenance_csv
from budget_core.reports.document import ReportDocument
from budget_core.reports.export import (
    mass_csv,
    result_csv,
    result_json,
    thermal_case_csv,
    thermal_mode_csv,
)
from budget_core.reports.files import write_files
from budget_core.reports.link_export import (
    link_json,
    passes_csv,
    static_csv,
)
from budget_core.reports.link_export import (
    series_csv as link_series_csv,
)
from budget_core.reports.link_report import build_link_report
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.power_report import build_power_report
from budget_core.reports.thermal_report import build_thermal_report
from budget_core.reports.timeline_export import (
    balance_csv,
    series_csv,
    timeline_json,
    violations_csv,
)
from budget_core.reports.timeline_report import build_timeline_report
from budget_core.scenario.run import run_parameters
from budget_core.thermal.static_thermal import StaticThermalResult

REPORT_KINDS = ("xlsx", "pdf", "docx", "json", "csv")


@dataclass(frozen=True)
class BudgetOutput:
    """Everything needed to write one budget's files: `<prefix>.xlsx|pdf|json` and CSV parts."""

    prefix: str
    document: ReportDocument
    result: Any
    provenance: Provenance
    csv_files: tuple[tuple[str, str], ...]  # (file name, text)
    json_text: str | None = None  # when the result is not a plain dataclass tree
    load_problems: tuple[Problem, ...] = ()  # found while loading the project (also in JSON)

    @property
    def incomplete(self) -> bool:
        """The report carries the INCOMPLETE banner (placeholders or missing inputs)."""
        return bool(self.document.banner)


def power_output(
    project: Project,
    power: StaticPowerResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
) -> BudgetOutput:
    document = build_power_report(project, power, provenance, list(load_problems))
    csvs = tuple((f"power_static_{m.mode_id}.csv", result_csv(m)) for m in power.modes)
    return BudgetOutput(
        "power_static", document, power, provenance, csvs, load_problems=tuple(load_problems)
    )


def mass_output(
    project: Project,
    mass: StaticMassResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
) -> BudgetOutput:
    document = build_mass_report(project, mass, provenance, list(load_problems))
    csvs = tuple((f"mass_static_{p.phase}.csv", mass_csv(p)) for p in mass.phases)
    return BudgetOutput(
        "mass_static", document, mass, provenance, csvs, load_problems=tuple(load_problems)
    )


def thermal_output(
    project: Project,
    thermal: StaticThermalResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
) -> BudgetOutput:
    document = build_thermal_report(project, thermal, provenance, list(load_problems))
    csvs = tuple((f"thermal_static_{m.mode_id}.csv", thermal_mode_csv(m)) for m in thermal.modes)
    csvs += tuple((f"thermal_case_{c.case}.csv", thermal_case_csv(c)) for c in thermal.cases)
    return BudgetOutput(
        "thermal_static",
        document,
        thermal,
        provenance,
        csvs,
        load_problems=tuple(load_problems),
    )


def timeline_parameters(result: TimeDomainResult) -> tuple[tuple[str, str], ...]:
    """The options of a power timeline: the scenario's, the demand basis, the cases solved and the
    mission phase that picks the depth-of-discharge limit."""
    return (
        *run_parameters(result.run),
        ("Demand basis", result.load_basis),
        ("Cases", ", ".join(c.case for c in result.cases)),
        ("Mission phase", result.mission_phase or "not set"),
    )


def link_output(
    project: Project,
    static: StaticLinkResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
    passes: LinkSeriesResult | None = None,
    *,
    plots: bool = True,
) -> BudgetOutput:
    """Static link table, plus the pass series when a scenario was run."""
    if passes is not None:
        provenance = replace(provenance, parameters=run_parameters(passes.run))
    document = build_link_report(project, static, provenance, load_problems, passes, plots=plots)
    prefix = "link_static" if passes is None else f"link_passes_{passes.run.scenario_id}"
    csvs: list[tuple[str, str]] = [(f"{prefix}_table.csv", static_csv(static))]
    if passes is not None:
        csvs.append((f"{prefix}_summary.csv", passes_csv(passes)))
        csvs += [(f"{prefix}_{s.link_id}.csv", link_series_csv(passes, s)) for s in passes.series]
    return BudgetOutput(
        prefix,
        document,
        static,
        provenance,
        tuple(csvs),
        link_json(
            static,
            passes,
            provenance,
            incomplete=bool(document.banner),
            load_problems=load_problems,
        ),
        tuple(load_problems),
    )


def timeline_output(
    project: Project,
    result: TimeDomainResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
    *,
    plots: bool = True,
    series_every: int = 1,
) -> BudgetOutput:
    """Time-domain power budget: report, JSON summary, and CSV files (series per case, the
    violations and the orbit balances). `series_every` thins the series CSV (every n-th step)."""
    provenance = replace(provenance, parameters=timeline_parameters(result))
    document = build_timeline_report(project, result, provenance, list(load_problems), plots=plots)
    scenario = result.run.scenario_id
    csvs = [
        (f"power_time_{scenario}_{c.case}.csv", series_csv(result, c.case, series_every))
        for c in result.cases
    ]
    csvs.append((f"power_time_{scenario}_violations.csv", violations_csv(result)))
    csvs.append((f"power_time_{scenario}_orbits.csv", balance_csv(result)))
    return BudgetOutput(
        f"power_time_{scenario}",
        document,
        result,
        provenance,
        tuple(csvs),
        timeline_json(
            result, provenance, incomplete=bool(document.banner), load_problems=load_problems
        ),
        tuple(load_problems),
    )


def write_outputs(
    outputs: Sequence[BudgetOutput], out_dir: Path, kinds: Collection[str] = REPORT_KINDS
) -> list[Path]:
    """Write the selected kinds of every output into `out_dir` (created if needed).

    Names are reduced to plain file names (they may be built from project text). All files are
    staged under temporary names first and moved into place together (see `write_files`), so a
    failing write does not leave a mix of new and old files; two outputs that would end up in
    the same file, also when only the case differs, are refused."""
    files: list[tuple[str, bytes | str]] = []
    for out in outputs:
        # Renderers are imported only when needed: ReportLab pulls in networking modules.
        if "xlsx" in kinds:
            from budget_core.reports.xlsx import render_xlsx

            files.append((f"{out.prefix}.xlsx", render_xlsx(out.document)))
        if "pdf" in kinds:
            from budget_core.reports.pdf import render_pdf

            files.append((f"{out.prefix}.pdf", render_pdf(out.document)))
        if "docx" in kinds:
            from budget_core.reports.docx import render_docx

            files.append((f"{out.prefix}.docx", render_docx(out.document)))
        if "json" in kinds:
            files.append(
                (
                    f"{out.prefix}.json",
                    out.json_text
                    if out.json_text is not None
                    else result_json(
                        out.result,
                        out.provenance,
                        incomplete=out.incomplete,
                        load_problems=out.load_problems,
                    ),
                )
            )
        if "csv" in kinds and out.csv_files:
            files.extend(out.csv_files)
            files.append(
                (
                    f"{out.prefix}_provenance.csv",
                    provenance_csv(out.provenance, incomplete=out.incomplete),
                )
            )
    return write_files(Path(out_dir), files)
