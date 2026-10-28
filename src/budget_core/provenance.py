"""Provenance carried by every report, plot and export (spec constraint 19).

For byte-identical regeneration (constraint 14) the generation time comes from, in order: the
`generated_at` argument, the SOURCE_DATE_EPOCH environment variable, the clock. The user comes from
the `user` argument, then BUDGET_USER, then the operating-system account.
"""

from __future__ import annotations

import getpass
import os
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from budget_core import APP_NAME, __version__
from budget_core.io.project_digest import project_digest
from budget_core.manifest import ManifestEntry, files_digest
from budget_core.model import Project
from budget_core.timeutil import MAX_YEAR, format_utc

# Every runtime library that shapes an output (all of `[project.dependencies]` except the window
# toolkit, which only draws the GUI). The PyInstaller spec ships the metadata of each, so a
# packaged build reports the same versions (tests keep this list, pyproject.toml and the spec in
# step).
LIBRARIES = (
    "numpy",
    "openpyxl",
    "Pillow",
    "pint",
    "pydantic",
    "python-docx",
    "reportlab",
    "ruamel.yaml",
    "sgp4",
)


@dataclass(frozen=True)
class Provenance:
    tool: str
    tool_version: str
    python_version: str
    libraries: tuple[tuple[str, str], ...]
    project_name: str
    project_revision: str
    scenario: str
    generated: str  # ISO 8601 UTC, seconds resolution
    user: str
    # What the numbers were computed from (D-204). Empty on a provenance built by hand.
    inputs_digest: str = ""  # sha256 of the loaded model, comments and key order gone
    input_files: tuple[ManifestEntry, ...] = ()  # every project file read, with its hash
    parameters: tuple[tuple[str, str], ...] = ()  # run options that change a number (name, value)

    def rows(self) -> list[tuple[str, str]]:
        libs = ", ".join(f"{n} {v}" for n, v in self.libraries)
        rows = [
            ("Tool", f"{self.tool} {self.tool_version}"),
            ("Python", self.python_version),
            ("Libraries", libs),
            ("Project", self.project_name),
            ("Project revision", self.project_revision),
            ("Scenario", self.scenario),
        ]
        if self.parameters:
            rows.append(("Run parameters", "; ".join(f"{n} {v}" for n, v in self.parameters)))
        if self.inputs_digest:
            rows.append(("Inputs digest (model)", self.inputs_digest))
        if self.input_files:
            count = len(self.input_files)
            rows.append(
                (
                    "Input files",
                    f"{count} file{'s' if count != 1 else ''}, {files_digest(self.input_files)}",
                )
            )
        rows += [("Generated (UTC)", self.generated), ("User", self.user)]
        return rows


def _lib_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


class ProvenanceError(ValueError):
    """The generation time cannot be determined; the message is plain language."""


def resolve_time(generated_at: datetime | None = None) -> datetime:
    """The generation time: the argument, else SOURCE_DATE_EPOCH, else the clock. A set but
    unusable SOURCE_DATE_EPOCH is an error, not a reason to quietly use the clock: the output
    would then differ from run to run although the caller asked for reproducible output."""
    if generated_at is not None:
        try:
            return generated_at.astimezone(UTC).replace(microsecond=0)
        except OverflowError, ValueError:
            raise ProvenanceError("The generation time cannot be converted to UTC.") from None
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None:
        text = epoch.strip()
        if not (text.isascii() and text.isdigit()):
            raise ProvenanceError(
                "SOURCE_DATE_EPOCH must be a whole number of seconds since 1970-01-01 "
                "(for example 1767323045); it is set to something else. Unset it or correct it."
            )
        try:
            moment = datetime.fromtimestamp(int(text), UTC)
        except OverflowError, OSError, ValueError:
            moment = None
        if moment is None or moment.year > MAX_YEAR:
            raise ProvenanceError(
                f"SOURCE_DATE_EPOCH is outside the supported dates (up to the year {MAX_YEAR})."
            )
        return moment
    return datetime.now(UTC).replace(microsecond=0)


def resolve_user(user: str | None = None) -> str:
    if user:
        return user
    env = os.environ.get("BUDGET_USER")
    if env:
        return env
    try:
        return getpass.getuser()
    except Exception:  # no account name available (containers, restricted accounts)
        return "unknown"


def make_provenance(
    project: Project,
    scenario: str = "static (no scenario)",
    *,
    user: str | None = None,
    generated_at: datetime | None = None,
) -> Provenance:
    return Provenance(
        tool=APP_NAME,
        tool_version=__version__,
        python_version=platform.python_version(),
        libraries=tuple((n, _lib_version(n)) for n in LIBRARIES),
        project_name=project.meta.name,
        project_revision=project.meta.revision,
        scenario=scenario,
        generated=format_utc(resolve_time(generated_at)),
        user=resolve_user(user),
        inputs_digest=project_digest(project),
        input_files=project.manifest,
    )
