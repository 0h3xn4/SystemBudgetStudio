#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Write the compliance record of one release (D-263).

    python packaging/compliance_record.py <folder> --tag v1.2.3 --out COMPLIANCE-RECORD.md
        [--commit <sha>] [--run-id <id>] [--repo owner/name] [--checks <folder>]

`<folder>` holds the files that are attached to the release. The record lists every file with its
size and SHA-256, names the SBOM, licence and notice files and the source code of the LGPL parts,
gives the result of the checks that ran before the release (`--checks` holds `reuse.exit` and
`pip-audit.exit`, each with the exit code of the check, and the text the check printed), and gives
the commands that verify the files. A check that did not run is written as "not run", never as
"passed". The record says nothing about the content of a project; it holds file names, sizes and
hashes. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

CHECKS = (
    ("reuse", "REUSE (licence and copyright of every file)", "reuse.txt"),
    ("pip-audit", "pip-audit (known vulnerabilities in the locked packages)", "pip-audit.txt"),
)
GROUPS = (
    ("Installers and packages", (".exe", ".zip", ".tar.gz", ".deb", ".rpm")),
    ("Software bill of materials (CycloneDX)", (".cdx.json",)),
    ("Licences and notices", ("licences", "THIRD_PARTY_NOTICES")),
    ("Checksums", ("SHA256SUMS",)),
    ("Source code of the LGPL parts (Qt, PySide6, shiboken6)", ("sources", "qt", "pyside")),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_result(folder: Path | None, key: str) -> str:
    """`passed`, `FAILED (exit code n)` or `not run`."""
    if folder is None:
        return "not run"
    code_file = folder / f"{key}.exit"
    if not code_file.is_file():
        return "not run"
    text = code_file.read_text(encoding="utf-8").strip()
    if text == "0":
        return "passed"
    return f"FAILED (exit code {text or 'unknown'})"


def group_of(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("sha256sums"):
        return "Checksums"
    if ".cdx.json" in lowered:
        return GROUPS[1][0]
    if lowered.startswith(("licences", "third_party_notices")):
        return GROUPS[2][0]
    if lowered.endswith(GROUPS[0][1]):
        return GROUPS[0][0]
    return GROUPS[4][0]


def render(
    folder: Path,
    tag: str,
    commit: str = "unknown",
    run_id: str = "unknown",
    repo: str = "OWNER/REPOSITORY",
    checks: Path | None = None,
) -> str:
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.name != "COMPLIANCE-RECORD.md")
    lines = [
        f"# Compliance record of {tag}",
        "",
        "This file is made by the release workflow (`packaging/compliance_record.py`). It lists",
        "what is attached to the release and which checks ran. It is not legal advice.",
        "",
        f"- Tag: `{tag}`",
        f"- Commit: `{commit}`",
        f"- Build run (workflow Installers): `{run_id}`",
        "",
        "## Checks that ran before the release",
        "",
    ]
    for key, title, _ in CHECKS:
        lines.append(f"- {title}: **{check_result(checks, key)}**")
    lines += ["", "## Files", ""]
    by_group: dict[str, list[Path]] = {}
    for path in files:
        by_group.setdefault(group_of(path.name), []).append(path)
    for group in [g for g, _ in GROUPS if g in by_group]:
        lines += [f"### {group}", "", "| File | Size (bytes) | SHA-256 |", "| --- | ---: | --- |"]
        lines += [f"| `{p.name}` | {p.stat().st_size} | `{sha256(p)}` |" for p in by_group[group]]
        lines.append("")
    lines += [
        "## How to check the files",
        "",
        "Compare a file with its checksum, then check where it was built (a signed build",
        "attestation made by GitHub for this repository):",
        "",
        "```bash",
        "sha256sum --check SHA256SUMS-linux.txt --ignore-missing",
        f"gh attestation verify <file> --repo {repo}",
        "```",
        "",
        "The attestation says which workflow, on which commit, built the file. It does not say",
        "who wrote the code. The installers are not signed by a code-signing certificate; see",
        "`docs/legal/signing-options.md`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--run-id", default="unknown")
    parser.add_argument("--repo", default="OWNER/REPOSITORY")
    parser.add_argument("--checks", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    if not args.folder.is_dir():
        print(f"{args.folder} is not a folder.", file=sys.stderr)
        return 2
    text = render(args.folder, args.tag, args.commit, args.run_id, args.repo, args.checks)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
