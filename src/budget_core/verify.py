"""Does a project give the result in an export? (D-204)

An export carries the digest of the model it was computed from and the list of project files with
their hashes (`provenance`, in every JSON export; the digest also in the `_provenance.csv` and in
the Provenance table of the documents). `verify_export` loads the project, computes the same
digest and says whether they agree and, if not, which files differ. It answers "is this the
project that produced these numbers?", not "are the numbers right".

Nothing is printed here and no project value is put into a message: file names (paths inside the
project) and digests only.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from budget_core import __version__
from budget_core.io.project_digest import project_digest
from budget_core.io.project_loader import load_project
from budget_core.io.yamlio import read_limited
from budget_core.manifest import ManifestEntry
from budget_core.problems import Severity

MAX_EXPORT_BYTES = 200_000_000  # a result file with long series; far beyond a normal export


class VerifyError(Exception):
    """The export or the project cannot be read; the message is plain language."""


MATCH = "match"
DIFFERENT = "different"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verification:
    status: str  # MATCH, DIFFERENT or UNKNOWN
    lines: tuple[str, ...]


@dataclass(frozen=True)
class _Recorded:
    digest: str
    files: tuple[ManifestEntry, ...]
    tool_version: str


def _recorded_from_json(text: str) -> _Recorded:
    try:
        data = json.loads(text)
    except ValueError:
        raise VerifyError("The export is not valid JSON.") from None
    prov = data.get("provenance") if isinstance(data, dict) else None
    if not isinstance(prov, dict):
        raise VerifyError(
            "The JSON file has no provenance block; it is not an export of this tool."
        )
    files: list[ManifestEntry] = []
    for item in prov.get("input_files") or []:
        try:
            files.append(ManifestEntry(str(item["path"]), int(item["size"]), str(item["sha256"])))
        except KeyError, TypeError, ValueError:
            raise VerifyError("The list of input files in the export is damaged.") from None
    return _Recorded(
        str(prov.get("inputs_digest") or ""), tuple(files), str(prov.get("tool_version") or "")
    )


def _recorded_from_csv(text: str) -> _Recorded:
    rows = {r[0]: r[1] for r in csv.reader(text.splitlines()) if len(r) >= 2}
    digest = rows.get("Inputs digest (model)", "")
    tool = rows.get("Tool", "")
    version = tool.rsplit(" ", 1)[-1] if tool else ""
    return _Recorded(digest, (), version)


def read_recorded(export: Path) -> _Recorded:
    try:
        raw = read_limited(export, MAX_EXPORT_BYTES)
    except OSError:
        raise VerifyError("The export file cannot be read.") from None
    if len(raw) > MAX_EXPORT_BYTES:
        raise VerifyError("The export file is too large to check.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise VerifyError(
            "The export file is not UTF-8 text (use the .json or the .csv)."
        ) from None
    if export.suffix.lower() == ".csv":
        return _recorded_from_csv(text)
    return _recorded_from_json(text)


def verify_export(export: Path, project_root: Path) -> Verification:
    """Compare the digest recorded in `export` (a JSON export, or a `_provenance.csv`) with the
    project in `project_root`."""
    recorded = read_recorded(export)
    if not recorded.digest:
        return Verification(
            UNKNOWN,
            (
                "This export records no input digest. It was made by a version before 1.8.0 "
                "or by hand, so it cannot be checked against a project.",
            ),
        )
    loaded = load_project(project_root)
    if loaded.project is None:
        errors = sum(1 for p in loaded.problems if p.severity is Severity.ERROR)
        return Verification(
            UNKNOWN,
            (
                f"The project cannot be loaded ({errors} error{'s' if errors != 1 else ''}); "
                "run 'budget validate' on it. A project that does not load cannot be compared.",
            ),
        )
    project = loaded.project
    now = project_digest(project)
    notes: list[str] = []
    if recorded.tool_version and recorded.tool_version != __version__:
        notes.append(
            f"The export was made by version {recorded.tool_version}; this is {__version__}. "
            "The same inputs can give different results if an equation or a default changed "
            "between the versions (see docs/changes.md)."
        )
    if now == recorded.digest:
        lines = [f"MATCH: the model digest is {now}."]
        if recorded.files:
            differing = _file_differences(recorded.files, project.manifest)
            if differing:
                lines.append(
                    f"{len(differing)} file(s) differ as text only (comments, key order or "
                    "spacing) and give the same model: "
                    + ", ".join(differing[:10])
                    + (" ..." if len(differing) > 10 else "")
                )
        return Verification(MATCH, (*lines, *notes))
    lines = [
        "DIFFERENT: the project is not the one this export was made from.",
        f"  recorded model digest: {recorded.digest}",
        f"  this project:          {now}",
    ]
    if recorded.files:
        changed, added, removed = _file_changes(recorded.files, project.manifest)
        if changed:
            lines.append(
                "  changed files: "
                + ", ".join(changed[:20])
                + (" ..." if len(changed) > 20 else "")
            )
        if added:
            lines.append(
                "  files not in the export: "
                + ", ".join(added[:20])
                + (" ..." if len(added) > 20 else "")
            )
        if removed:
            lines.append(
                "  files missing now: "
                + ", ".join(removed[:20])
                + (" ..." if len(removed) > 20 else "")
            )
    else:
        lines.append("  (this export does not list the files; use the .json to see which differ)")
    return Verification(DIFFERENT, (*lines, *notes))


def _file_changes(
    recorded: tuple[ManifestEntry, ...], current: tuple[ManifestEntry, ...]
) -> tuple[list[str], list[str], list[str]]:
    before = {e.path: e for e in recorded}
    after = {e.path: e for e in current}
    changed = sorted(p for p in before.keys() & after.keys() if before[p].sha256 != after[p].sha256)
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    return changed, added, removed


def _file_differences(
    recorded: tuple[ManifestEntry, ...], current: tuple[ManifestEntry, ...]
) -> list[str]:
    changed, added, removed = _file_changes(recorded, current)
    return sorted(changed + added + removed)
