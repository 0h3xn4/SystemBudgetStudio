#!/usr/bin/env python3
"""Build the Debian package of System Budget Studio from the bundle folder (standard library only).

    python packaging/linux/make_deb.py dist/system-budget-studio --out dist

The package installs the bundle into /opt/system-budget-studio, links `system-budget-studio` and
`budget` into /usr/bin, and adds the menu entry and the icons (system-wide, so it needs
administrator rights, unlike install.sh). It is written without dpkg-deb: a .deb is an `ar`
archive of `debian-binary`, `control.tar.gz` and `data.tar.xz`, which keeps the build free of
extra tools and the file the same for the same bundle (D-149). The package is not signed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import lzma
import os
import re
import stat
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NAME = "system-budget-studio"
PREFIX = f"opt/{NAME}"
MAINTAINER = "0h3xn4 <291340596+0h3xn4@users.noreply.github.com>"
HOMEPAGE = "https://github.com/0h3xn4/SystemBudgetStudio"
SUMMARY = "Power, mass, thermal and link budgets for small satellites"
DESCRIPTION = (
    "Offline desktop and command-line tool that computes power, mass, thermal and radio-link\n"
    "budgets for a small satellite from one spacecraft model kept in plain text files.\n"
    "Every number carries its source, results that depend on an unsourced number say n/a,\n"
    "and the same input always gives the same output files. No network access is needed.\n"
    "The package holds a self-contained build (Python, Qt and every library are included)."
)
# What the window needs from the system (Qt's xcb platform plugin and OpenGL); the bundle holds
# everything else. Names of Ubuntu 22.04 and 24.04 and Debian 12.
DEPENDS = (
    "libc6 (>= 2.28)",
    "libegl1",
    "libgl1",
    "libglib2.0-0",
    "libdbus-1-3",
    "libfontconfig1",
    "libxkbcommon0",
    "libxkbcommon-x11-0",
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-xinerama0",
    "libxcb-xkb1",
)
# bundle files that belong to the per-user installer, not to a package
LEFT_OUT = ("install.sh", "uninstall.sh")
ICON_DIR = Path("_internal/budget_core/assets/icons")

MAINTAINER_SCRIPT = """#!/bin/sh
# refresh the menu and icon caches when the tools exist; never fail the installation over them
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
theme=/usr/share/icons/hicolor
if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -f "$theme/index.theme" ]; then
    gtk-update-icon-cache -q -t -f "$theme" || true
fi
exit 0
"""


def version_of(root: Path = ROOT) -> str:
    text = (root / "src" / "budget_core" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"', text, re.M)
    if match is None:
        raise SystemExit("cannot read __version__ from src/budget_core/__init__.py")
    return match.group(1)


class Entry:
    """One path of the data archive: a directory, a file (with its bytes) or a symbolic link."""

    def __init__(
        self, path: str, mode: int, data: bytes | None = None, link: str | None = None
    ) -> None:
        self.path, self.mode, self.data, self.link = path, mode, data, link

    @property
    def is_dir(self) -> bool:
        return self.data is None and self.link is None


def collect_bundle(bundle: Path) -> list[Entry]:
    entries: list[Entry] = []
    for current, dirs, files in os.walk(bundle):
        dirs.sort()
        here = Path(current)
        relative = here.relative_to(bundle)
        folder = PREFIX if str(relative) == "." else f"{PREFIX}/{relative}"
        entries.append(Entry(folder, 0o755))
        for name in sorted(files) + [d for d in dirs if (here / d).is_symlink()]:
            path = here / name
            rel = f"{PREFIX}/{path.relative_to(bundle)}"
            if rel.count("/") == PREFIX.count("/") + 1 and name in LEFT_OUT:
                continue
            if path.is_symlink():
                entries.append(Entry(rel, 0o777, link=os.readlink(path)))
            else:
                executable = path.stat().st_mode & stat.S_IXUSR
                entries.append(Entry(rel, 0o755 if executable else 0o644, path.read_bytes()))
        dirs[:] = [d for d in dirs if not (here / d).is_symlink()]
    return entries


def system_entries(bundle: Path) -> list[Entry]:
    desktop = (HERE / f"{NAME}.desktop").read_bytes()
    licence = (
        (bundle / "LICENSE").read_text(encoding="utf-8") if (bundle / "LICENSE").exists() else ""
    )
    copyright_text = (
        f"System Budget Studio\n{HOMEPAGE}\n\n"
        "Released under the MIT licence (below). The package also carries third-party libraries,\n"
        f"whose licences are in /{PREFIX}/licences/ and listed in /{PREFIX}/licences.md.\n\n"
        f"{licence}"
    ).encode()
    entries = [
        Entry("usr/bin", 0o755),
        Entry(f"usr/bin/{NAME}", 0o777, link=f"/{PREFIX}/{NAME}"),
        Entry("usr/bin/budget", 0o777, link=f"/{PREFIX}/budget"),
        Entry("usr/share", 0o755),
        Entry("usr/share/applications", 0o755),
        Entry(f"usr/share/applications/{NAME}.desktop", 0o644, desktop),
        Entry("usr/share/doc", 0o755),
        Entry(f"usr/share/doc/{NAME}", 0o755),
        Entry(f"usr/share/doc/{NAME}/copyright", 0o644, copyright_text),
        Entry("usr/share/icons", 0o755),
        Entry("usr/share/icons/hicolor", 0o755),
    ]
    for icon in sorted((bundle / ICON_DIR).glob("logo-*.png")):
        size = icon.stem.split("-")[1]
        if not size.isdigit():
            continue
        folder = f"usr/share/icons/hicolor/{size}x{size}"
        entries += [
            Entry(folder, 0o755),
            Entry(f"{folder}/apps", 0o755),
            Entry(f"{folder}/apps/{NAME}.png", 0o644, icon.read_bytes()),
        ]
    return entries


def tar_bytes(entries: list[Entry], mtime: int, compression: str) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for entry in sorted(entries, key=lambda e: e.path):
            info = tarfile.TarInfo(f"./{entry.path}" if entry.path else ".")
            info.mtime, info.mode = mtime, entry.mode
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            if entry.link is not None:
                info.type, info.linkname = tarfile.SYMTYPE, entry.link
                archive.addfile(info)
            elif entry.data is not None:
                info.size = len(entry.data)
                archive.addfile(info, io.BytesIO(entry.data))
            else:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
    data = raw.getvalue()
    if compression == "xz":
        return lzma.compress(data, format=lzma.FORMAT_XZ, preset=6)
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=mtime, compresslevel=9) as handle:
        handle.write(data)
    return out.getvalue()


def ar_member(name: str, data: bytes, mtime: int) -> bytes:
    header = f"{name:<16}{mtime:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n"
    assert len(header) == 60
    return header.encode("ascii") + data + (b"\n" if len(data) % 2 else b"")


def control_text(version: str, installed_kib: int) -> str:
    extended = "\n".join(f" {line}" for line in DESCRIPTION.splitlines())
    return (
        f"Package: {NAME}\nVersion: {version}\nArchitecture: amd64\nMaintainer: {MAINTAINER}\n"
        f"Installed-Size: {installed_kib}\nDepends: {', '.join(DEPENDS)}\nSection: science\n"
        f"Priority: optional\nHomepage: {HOMEPAGE}\nDescription: {SUMMARY}\n{extended}\n"
    )


def build(bundle: Path, out: Path, version: str, mtime: int | None = None) -> Path:
    if not (bundle / NAME).is_file() or not (bundle / "budget").is_file():
        raise SystemExit(
            f"{bundle} is not a bundle folder (system-budget-studio and budget missing)"
        )
    if mtime is None:
        env = os.environ.get("SOURCE_DATE_EPOCH", "")
        newest = max(int(p.stat().st_mtime) for p in bundle.rglob("*") if not p.is_symlink())
        mtime = int(env) if env.isdigit() else newest
    entries = [Entry("opt", 0o755)] + collect_bundle(bundle) + system_entries(bundle)
    files = [e for e in entries if e.data is not None]
    installed_kib = (sum(len(e.data or b"") for e in files) + 1023) // 1024
    md5 = "".join(
        f"{hashlib.md5(e.data or b'').hexdigest()}  {e.path}\n"
        for e in sorted(files, key=lambda e: e.path)
    )
    script = MAINTAINER_SCRIPT.encode()
    control = [
        Entry("", 0o755),
        Entry("control", 0o644, control_text(version, installed_kib).encode()),
        Entry("md5sums", 0o644, md5.encode()),
        Entry("postinst", 0o755, script),
        Entry("postrm", 0o755, script),
    ]
    package = (
        b"!<arch>\n"
        + ar_member("debian-binary", b"2.0\n", mtime)
        + ar_member("control.tar.gz", tar_bytes(control, mtime, "gz"), mtime)
        + ar_member("data.tar.xz", tar_bytes(entries, mtime, "xz"), mtime)
    )
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{NAME}_{version}_amd64.deb"
    target.write_bytes(package)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the .deb package from the bundle folder.")
    parser.add_argument("bundle", type=Path, help="the bundle folder (dist/system-budget-studio)")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="folder for the package")
    parser.add_argument("--version", help="package version (default: the version of the tool, -1)")
    args = parser.parse_args(argv)
    version = args.version or f"{version_of()}-1"
    print(build(args.bundle, args.out, version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
