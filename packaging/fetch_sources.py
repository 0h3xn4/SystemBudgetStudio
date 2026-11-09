#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Download the source archives of the LGPL components of the installers and check them.

    python packaging/fetch_sources.py --out dist/sources [--notices-out dist/qt-notices]

Reads `packaging/sources.toml`, downloads each archive, checks its SHA-256 against the value in the
file (the Qt project publishes the same value next to each archive) and writes `SOURCES.txt` (what
the archives are, their checksums, and the written offer). With `--notices-out` the licence files of
the third-party code inside Qt (every `3rdparty` licence file, and the `LICENSES` folder) are
extracted from the archives marked `notices = true` for THIRD_PARTY_NOTICES.txt. The program itself
never downloads anything; this is part of the release build. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tarfile
import tomllib
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LICENCE_NAME = re.compile(
    r"^(LICEN[CS]E|LICEN[CS]ING|COPYING|COPYRIGHT|NOTICE|AUTHORS)([-._].*)?$|\.LICEN[CS]E$",
    re.IGNORECASE,
)


def load(path: Path = HERE / "sources.toml") -> list[dict[str, object]]:
    return list(tomllib.loads(path.read_text(encoding="utf-8"))["source"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "system-budget-studio-release"})
    with urllib.request.urlopen(request, timeout=300) as response, target.open("wb") as out:  # noqa: S310
        while chunk := response.read(1 << 20):
            out.write(chunk)


def wanted_notice(member: str) -> bool:
    """A licence file of third-party code inside the archive, or the LICENSES folder."""
    parts = member.split("/")
    if "3rdparty" in parts[:-1] and LICENCE_NAME.match(parts[-1]):
        return True
    return len(parts) >= 3 and parts[1] == "LICENSES" and parts[-1].endswith(".txt")


def extract_notices(archive: Path, out: Path) -> int:
    count = 0
    with tarfile.open(archive, "r:xz") as tar:
        for member in tar:
            if member.isfile() and wanted_notice(member.name) and member.size < 2_000_000:
                target = out / archive.name.split("-everywhere")[0] / member.name.split("/", 1)[1]
                target.parent.mkdir(parents=True, exist_ok=True)
                handle = tar.extractfile(member)
                assert handle is not None
                target.write_bytes(handle.read())
                count += 1
    return count


OFFER = """\
Source code of the LGPL components

The installers contain Qt 6, PySide6 and shiboken6, which are licensed under the GNU Lesser General
Public License version 3. The archives listed below are the exact source code of the versions in
the installers of this release. They are attached to this release on GitHub. Anyone who received
the installers may get them from there. The libraries are separate files in the program folder, so
that a user can replace them with another compatible version (docs/developer/replace-qt.md).
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--notices-out", type=Path)
    parser.add_argument("--manifest", type=Path, default=HERE / "sources.toml")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    lines = [OFFER, "| Archive | SHA-256 | Used for |", "|---|---|---|"]
    notices = 0
    for source in load(args.manifest):
        url = str(source["url"])
        target = args.out / url.rsplit("/", 1)[1]
        if not target.is_file() or sha256(target) != source["sha256"]:
            print(f"downloading {url}")
            download(url, target)
        actual = sha256(target)
        if actual != source["sha256"]:
            print(f"CHECKSUM MISMATCH for {target.name}: {actual} (expected {source['sha256']})")
            target.unlink()
            return 1
        lines.append(f"| {target.name} | {actual} | {source['used_for']} |")
        if args.notices_out and source.get("notices"):
            notices += extract_notices(target, args.notices_out)
    (args.out / "SOURCES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines) - 4} archives checked; {notices} third-party licence files extracted")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
