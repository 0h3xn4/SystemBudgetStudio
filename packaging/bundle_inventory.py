#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""What is in a built bundle, under which licence, and where its licence text is.

    python packaging/bundle_inventory.py collect dist/system-budget-studio [--qt-notices DIR]
    python packaging/bundle_inventory.py check   dist/system-budget-studio
    python packaging/bundle_inventory.py notices dist/system-budget-studio
    python packaging/bundle_inventory.py sbom    dist/system-budget-studio dist/sbom.cdx.json

`collect` goes through the bundle and writes `licences/COMPONENTS.json` (every component, its SPDX
licence, the files it accounts for, its licence texts) and copies the texts the Python packages do
not carry: the licence of Python, the bootloader exception of PyInstaller, the LGPL and GPL texts
and the third-party notices of Qt, and, on Linux, the licence files of the system libraries that
PyInstaller copied into the bundle (asked from `rpm`; the Linux build runs on Rocky 9).
`check` is the licence gate (packaging/bundle_policy.toml): it fails when a component has no
licence text, a licence on the deny list or an unknown licence, when a file of the bundle belongs to
no component, or when a Qt library outside the policy (or a GPL-only module) is bundled.
`notices` writes THIRD_PARTY_NOTICES.txt from the recorded texts, copied verbatim. `sbom` adds the
components that are not Python packages to the CycloneDX file.
Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bundle_policy as policy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LIB_SUFFIX = re.compile(r"\.(so(\.\d+)*|dll|dylib)$|\.so\.", re.IGNORECASE)
VENDORED = re.compile(r"-[0-9a-f]{8,}\.(so|dll)|\.libs$", re.IGNORECASE)
# Windows files that are no one's package: the C runtime and what Python loads (D-184).
WINDOWS_RUNTIME = ("api-ms-win-*", "ucrtbase.dll", "vcruntime*", "msvcp*", "concrt*")
# components whose licence the policy knows but whose text a package manager cannot give
EXTRAS = {
    "windows-vc-runtime": (
        "Microsoft Visual C++ runtime",
        "LicenseRef-Microsoft-VC-Redistributable",
    ),
    "openssl": ("OpenSSL", "Apache-2.0"),
    "libffi": ("libffi", "MIT"),
    "mesa-opengl32sw": ("Mesa (opengl32sw.dll, software OpenGL of Qt)", "MIT"),
}


# licence texts (verbatim files of the repository) of the extras above
EXTRA_TEXTS = {
    "openssl": ("LICENSES/Apache-2.0.txt", "the Apache-2.0 text; OpenSSL 3 is licensed under it"),
    "libffi": ("packaging/notices/libffi-LICENSE.txt", "LICENSE of libffi (packaging/notices)"),
}


@dataclass
class Component:
    name: str
    version: str
    group: str  # python | qt | runtime | bootloader | system | font | icon | extra
    spdx: str
    files: list[str] = field(default_factory=list)  # paths below the bundle folder
    texts: list[str] = field(default_factory=list)  # paths below the bundle folder
    source: str = ""  # where the licence was read from
    problems: list[str] = field(default_factory=list)
    known_gap: str = ""  # a gap the owner knows about (bundle_policy.toml [known_gaps])


# ---- system packages (Rocky/RHEL 9) -------------------------------------------------------------
@dataclass
class Package:
    name: str
    version: str
    licence: str  # the licence field of the package manager
    licence_files: list[Path]


SYSTEM_LIBRARY_DIRS = ("/usr/lib64", "/lib64", "/usr/lib", "/lib", "/usr/lib/x86_64-linux-gnu")


def system_original(path: Path, dirs: tuple[str, ...] = SYSTEM_LIBRARY_DIRS) -> Path | None:
    """The file of the build machine that PyInstaller copied to `path`: same name, same size.

    The bundle holds copies, which no package owns; the original does. A library that came
    from a wheel (hash in its name) or from anywhere else has no original here."""
    for folder in dirs:
        candidate = Path(folder) / path.name
        try:
            if candidate.exists() and candidate.resolve().stat().st_size == path.stat().st_size:
                return candidate
        except OSError:
            continue
    return None


class RpmBackend:
    """Ask `rpm` which package owns a file, under which licence, with which licence files."""

    def __init__(self) -> None:
        self.available = shutil.which("rpm") is not None
        self._cache: dict[str, Package | None] = {}

    def licence_files(self, name: str) -> list[Path]:
        """The licence texts of a package: `rpm -qL`, else the documents of the package (and of
        its `-common` package) that are named COPYING, LICENSE and so on."""
        out: list[Path] = []
        for query in (["-qL", name], ["-qd", name], ["-ql", name], ["-ql", f"{name}-common"]):
            result = subprocess.run(["rpm", *query], capture_output=True, text=True, check=False)
            for line in result.stdout.split():
                path = Path(line)
                if not path.is_file():
                    continue
                in_docs = "/usr/share/licenses/" in line or "/usr/share/doc/" in line
                if query[0] == "-qL" or (in_docs and LICENCE_LIKE.search(path.name)):
                    out.append(path)
            if out:
                break
        return sorted(set(out))

    def listing(self, name: str) -> str:
        result = subprocess.run(["rpm", "-ql", name], capture_output=True, text=True, check=False)
        return ", ".join(result.stdout.split()[:12])

    def owner(self, path: Path) -> Package | None:
        if not self.available:
            return None
        original = system_original(path)
        if original is None:
            return None
        real = str(original.resolve())
        out = subprocess.run(
            ["rpm", "-qf", "--qf", "%{NAME}\\n", real], capture_output=True, text=True, check=False
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        name = out.stdout.splitlines()[0]
        if name not in self._cache:
            info = subprocess.run(
                ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}|%{LICENSE}\\n", name],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()[0]
            version, _, lic = info.partition("|")
            found = self.licence_files(name)
            if not found and os.environ.get("SBS_REINSTALL_DOCS") == "1":
                # a container image installs without documents (tsflags=nodocs): fetch them again
                subprocess.run(
                    ["dnf", "-y", "--setopt=tsflags=", "reinstall", name],
                    capture_output=True,
                    check=False,
                )
                found = self.licence_files(name)
            if not found:
                print(
                    f"no licence file for {name}: rpm -ql lists {self.listing(name)}",
                    file=sys.stderr,
                )
            self._cache[name] = Package(name, version, lic, found)
        return self._cache[name]


LICENCE_LIKE = re.compile(r"(licen[cs]e|copying|copyright|notice)", re.IGNORECASE)


# ---- helpers ------------------------------------------------------------------------------------
def rel(bundle: Path, path: Path) -> str:
    return path.relative_to(bundle).as_posix()


def library_files(internal: Path) -> list[Path]:
    """Shared libraries and Qt plugins that sit directly in the bundle's `_internal` folder or
    in PySide6 (Python extension modules inside a package belong to that package)."""
    found: list[Path] = []
    for path in sorted(internal.iterdir()):
        if path.is_file() and LIB_SUFFIX.search(path.name):
            found.append(path)
    for folder in ("PySide6", "shiboken6", "numpy.libs", "pillow.libs", "lxml.libs"):
        base = internal / folder
        if base.is_dir():
            found += sorted(p for p in base.rglob("*") if p.is_file() and LIB_SUFFIX.search(p.name))
    return found


def distribution_of_files() -> dict[str, str]:
    """File name (as installed in site-packages) -> the distribution that installed it."""
    owners: dict[str, str] = {}
    for dist in metadata.distributions():
        for file in dist.files or []:
            owners.setdefault(Path(str(file)).name, dist.metadata["Name"] or "")
    return owners


def python_packages(bundle: Path) -> list[Component]:
    """The Python packages, from the table `licences/INDEX.md` (packaging/licence_check.py)."""
    index = bundle / "licences" / "INDEX.md"
    versions = {}
    internal = bundle / "_internal"
    for info in internal.glob("*.dist-info") if internal.is_dir() else []:
        name, _, version = info.name.removesuffix(".dist-info").rpartition("-")
        versions[name.lower().replace("_", "-").replace(".", "-")] = version
    components: list[Component] = []
    if not index.is_file():
        return components
    for line in index.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("Package", "---") or cells[0].startswith("---"):
            continue
        name, lic, names = cells
        folder = bundle / "licences" / name
        texts = [rel(bundle, folder / n.strip()) for n in names.split(",") if n.strip()]
        components.append(
            Component(
                name,
                versions.get(name.lower().replace("_", "-"), "") or _version(name),
                "python",
                policy.normalise_licence(lic),
                [],
                texts,
                "licences/INDEX.md (package metadata)",
            )
        )
    return components


def classify(bundle: Path, backend: RpmBackend, repo: Path = ROOT) -> list[Component]:
    internal = bundle / "_internal"
    components: dict[str, Component] = {}
    packages = {c.name.lower().replace("_", "-"): c for c in python_packages(bundle)}
    owners = distribution_of_files()

    def add(key: str, make: "Component") -> Component:  # noqa: UP037
        return components.setdefault(key, make)

    qt_version = packages.get("pyside6-essentials", Component("", "", "python", "")).version
    qt = add(
        "qt",
        Component(
            "Qt 6 (libraries and plugins of PySide6-Essentials)", qt_version, "qt", "LGPL-3.0-only"
        ),
    )
    qt.source = "PySide6-Essentials wheel; the LGPL-3.0 option of Qt's licences is used"
    for text in ("qt/LGPL-3.0.txt", "qt/GPL-3.0.txt"):
        if (bundle / "licences" / text).is_file():
            qt.texts.append(f"licences/{text}")
    third_party = bundle / "licences" / "qt" / "third-party"
    if third_party.is_dir():
        qt.texts += sorted(rel(bundle, p) for p in third_party.rglob("*") if p.is_file())

    for path in library_files(internal) if internal.is_dir() else []:
        name, relpath = path.name, rel(bundle, path)
        if policy.is_qt_library(name) or "/plugins/" in f"/{relpath}" and "PySide6/" in relpath:
            qt.files.append(relpath)
            continue
        if re.match(r"^(lib)?(pyside6|shiboken6)", name, re.IGNORECASE) or (
            relpath.startswith(("_internal/PySide6/", "_internal/shiboken6/"))
            and name.lower().startswith(("qt", "pyside6", "shiboken6"))
        ):
            owner_pkg = packages.get(
                "pyside6-essentials" if "pyside" in name.lower() else "shiboken6"
            )
            (owner_pkg or qt).files.append(relpath)
            continue
        if re.match(r"^(lib)?python3", name, re.IGNORECASE):
            runtime = add(
                "python", Component("Python", sys.version.split()[0], "runtime", "PSF-2.0")
            )
            runtime.files.append(relpath)
            continue
        dist = owners.get(name)
        if dist and VENDORED.search(relpath + name) or (dist and ".libs/" in relpath):
            pkg = packages.get(dist.lower().replace("_", "-"))
            if pkg is not None:
                pkg.files.append(relpath)
                continue
        if (
            re.match(r"^(libssl|libcrypto)-?\d*", name)
            and os.name == "nt"
            or name.lower() in ("libssl-3.dll", "libcrypto-3.dll")
        ):
            add(
                "openssl", Component(*EXTRAS["openssl"][:1], "3", "extra", EXTRAS["openssl"][1])
            ).files.append(relpath)
            continue
        if name.lower().startswith("libffi-") and name.lower().endswith(".dll"):
            add(
                "libffi", Component(*EXTRAS["libffi"][:1], "", "extra", EXTRAS["libffi"][1])
            ).files.append(relpath)
            continue
        if name.lower() == "opengl32sw.dll":
            add(
                "mesa",
                Component(EXTRAS["mesa-opengl32sw"][0], "", "extra", EXTRAS["mesa-opengl32sw"][1]),
            ).files.append(relpath)
            continue
        if any(fnmatch.fnmatch(name.lower(), pat) for pat in WINDOWS_RUNTIME):
            add(
                "vc",
                Component(
                    EXTRAS["windows-vc-runtime"][0], "", "extra", EXTRAS["windows-vc-runtime"][1]
                ),
            ).files.append(relpath)
            continue
        if name.lower().endswith(".dll"):
            add(
                "unknown-dll", Component("unidentified Windows libraries", "", "extra", "")
            ).files.append(relpath)
            continue
        extra = next(
            (
                e
                for e in policy.POLICY.get("extra_components", [])
                if fnmatch.fnmatch(name, e["pattern"])
            ),
            None,
        )
        if extra is not None and backend.owner(path) is None:
            comp = add(
                f"extra:{extra['pattern']}", Component(extra["name"], "", "extra", extra["spdx"])
            )
            comp.files.append(relpath)
            comp.source = extra.get("note", "")
            if not comp.texts and (repo / extra["text"]).is_file():
                target = bundle / "licences" / "extra" / Path(extra["text"]).name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repo / extra["text"], target)
                comp.texts.append(rel(bundle, target))
            continue
        package = backend.owner(path)
        if package is None:
            add(
                "unidentified", Component("unidentified shared libraries", "", "system", "")
            ).files.append(relpath)
            continue
        key = f"rpm:{package.name}"
        spdx = policy.normalise_licence(package.licence)
        override = policy.POLICY.get("package_overrides", {}).get(package.name)
        if override:
            spdx = str(override["spdx"])
        comp = add(
            key,
            Component(
                package.name, package.version, "system", spdx, [], [], f"rpm: {package.licence}"
            ),
        )
        comp.files.append(relpath)
        if not comp.texts:
            folder = bundle / "licences" / "system" / package.name
            for source in package.licence_files:
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / source.name
                if not target.exists():
                    shutil.copyfile(source, target)
                comp.texts.append(rel(bundle, target))

    # the bootloader is in both executables
    for exe in ("system-budget-studio", "budget", "system-budget-studio.exe", "budget.exe"):
        if (bundle / exe).is_file():
            boot = add(
                "bootloader",
                Component(
                    "PyInstaller bootloader",
                    _version("pyinstaller"),
                    "bootloader",
                    "GPL-2.0-or-later WITH Bootloader-exception",
                ),
            )
            boot.files.append(exe)
            boot.source = "PyInstaller COPYING.txt (GPL-2.0 with the bootloader exception)"
            boot.texts = (
                [
                    f"licences/pyinstaller/{n.name}"
                    for n in sorted((bundle / "licences" / "pyinstaller").glob("*"))
                ]
                if (bundle / "licences" / "pyinstaller").is_dir()
                else []
            )
    if "python" in components:
        components["python"].texts = (
            [
                f"licences/python/{n.name}"
                for n in sorted((bundle / "licences" / "python").glob("*"))
            ]
            if (bundle / "licences" / "python").is_dir()
            else []
        )
    assets = internal / "budget_core" / "assets"
    fonts = sorted((assets / "fonts").glob("OFL-*.txt")) if assets.is_dir() else []
    if fonts:
        add(
            "fonts",
            Component(
                "Fonts: Inter, JetBrains Mono, IBM Plex",
                "",
                "font",
                "OFL-1.1",
                [rel(bundle, p) for p in sorted((assets / "fonts").glob("*.ttf"))],
                [rel(bundle, p) for p in fonts],
                "assets/fonts/README.md",
            ),
        )
    lucide = assets / "icons" / "ui" / "LICENSE-Lucide.txt"
    if lucide.is_file():
        add(
            "icons",
            Component(
                "Lucide icons 0.468.0",
                "0.468.0",
                "icon",
                "ISC AND MIT",
                [rel(bundle, p) for p in sorted((assets / "icons" / "ui").glob("*.png"))][:1],
                [rel(bundle, lucide)],
                "assets/icons/ui/README.md",
            ),
        )
    for extra_key, (source, why) in EXTRA_TEXTS.items():
        if extra_key in components and (repo / source).is_file():
            target = bundle / "licences" / "extra" / f"{extra_key}-{Path(source).name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / source, target)
            components[extra_key].texts.append(rel(bundle, target))
            components[extra_key].source = why
    result = [c for c in packages.values()] + [c for k, c in components.items()]
    return result


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return ""


# ---- collect ------------------------------------------------------------------------------------
def collect(
    bundle: Path, qt_notices: Path | None = None, backend: RpmBackend | None = None
) -> list[Component]:
    licences = bundle / "licences"
    # texts the packages do not carry
    python_license = (
        Path(sys.base_prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "LICENSE.txt"
    )
    candidates = [
        python_license,
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "Lib" / "LICENSE.txt",
    ]
    for source in candidates:
        if source.is_file():
            (licences / "python").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, licences / "python" / "LICENSE.txt")
            break
    try:
        dist = metadata.distribution("pyinstaller")
        for file in dist.files or []:
            if re.search(r"(^|/)COPYING", str(file)):
                (licences / "pyinstaller").mkdir(parents=True, exist_ok=True)
                shutil.copyfile(
                    Path(str(dist.locate_file(file))),
                    licences / "pyinstaller" / Path(str(file)).name,
                )
    except metadata.PackageNotFoundError:
        pass
    (licences / "qt").mkdir(parents=True, exist_ok=True)
    for name in ("LGPL-3.0.txt", "GPL-3.0.txt"):
        shutil.copyfile(ROOT / "assets" / "licences" / name, licences / "qt" / name)
    if qt_notices is not None and qt_notices.is_dir():
        target = licences / "qt" / "third-party"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(qt_notices, target)
    components = classify(bundle, backend or RpmBackend())
    gaps = policy.POLICY.get("known_gaps", {})
    for comp in components:
        for pattern, reason in gaps.items():
            if fnmatch.fnmatch(comp.name, pattern):
                comp.known_gap = str(reason)
    (licences / "COMPONENTS.json").write_text(
        json.dumps([asdict(c) for c in components], indent=2) + "\n", encoding="utf-8"
    )
    return components


# ---- check (the licence gate) --------------------------------------------------------------------
def check(bundle: Path, allow_unresolved: bool = False) -> list[str]:
    problems: list[str] = []
    internal = bundle / "_internal"
    # 1. Qt: nothing outside the policy, nothing GPL-only (looked at in the files, not the record)
    for path in library_files(internal) if internal.is_dir() else []:
        relpath = rel(bundle, path)
        if policy.is_gpl_only_qt(path.name):
            problems.append(f"GPL-only Qt module in the bundle: {relpath}")
        elif policy.is_qt_library(path.name) and not policy.qt_library_wanted(path.name):
            problems.append(f"Qt library the program does not use: {relpath}")
        elif (
            "/plugins/" in f"/{relpath}"
            and "PySide6/" in relpath
            and not policy.qt_plugin_wanted(relpath.split("plugins/", 1)[1])
        ):
            problems.append(f"Qt plugin the program does not use: {relpath}")
    for path in (internal / "PySide6").glob("*") if (internal / "PySide6").is_dir() else []:
        if path.is_file() and not policy.keep_python_module(path.name):
            problems.append(f"PySide6 module the program does not use: {rel(bundle, path)}")
    for translation in (
        (internal / "PySide6").rglob("translations") if (internal / "PySide6").is_dir() else []
    ):
        problems.append(f"Qt translations in the bundle: {rel(bundle, translation)}")
    # 2. the record of `collect`
    record = bundle / "licences" / "COMPONENTS.json"
    if not record.is_file():
        return problems + [
            "missing from the bundle: licences/COMPONENTS.json (run bundle_inventory.py collect)"
        ]
    components = [Component(**c) for c in json.loads(record.read_text(encoding="utf-8"))]
    accounted: set[str] = set()
    for comp in components:
        label = f"{comp.name} {comp.version}".strip()
        accounted.update(comp.files)
        if comp.group in ("system", "extra") and not comp.spdx:
            if allow_unresolved:
                continue
            problems.append(
                f"{label}: no owner or licence known for {len(comp.files)} file(s): "
                f"{', '.join(Path(f).name for f in comp.files[:40])}"
            )
            continue
        verdict = policy.licence_verdict(comp.spdx)
        if not verdict.ok:
            problems.append(f"{label}: licence {comp.spdx!r} is not accepted ({verdict.reason})")
        existing = [
            t for t in comp.texts if (bundle / t).is_file() and (bundle / t).stat().st_size > 0
        ]
        if not existing and not comp.known_gap:
            problems.append(f"{label}: no licence text in the bundle")
        no_notices = comp.group == "qt" and not any("third-party" in t for t in comp.texts)
        if no_notices and not comp.known_gap and not allow_unresolved:
            problems.append(
                "Qt: no third-party notices of Qt in the bundle (licences/qt/third-party)"
            )
    # 3. every shared library belongs to a component
    for path in library_files(internal) if internal.is_dir() else []:
        if rel(bundle, path) not in accounted and not allow_unresolved:
            problems.append(f"file in no component of the record: {rel(bundle, path)}")
    if not (bundle / "THIRD_PARTY_NOTICES.txt").is_file():
        problems.append("missing from the bundle: THIRD_PARTY_NOTICES.txt")
    return problems


# ---- notices ------------------------------------------------------------------------------------
def notices(bundle: Path) -> str:
    components = [
        Component(**c)
        for c in json.loads((bundle / "licences" / "COMPONENTS.json").read_text(encoding="utf-8"))
    ]
    out = [
        "THIRD-PARTY NOTICES",
        "",
        "System Budget Studio contains the components below. Each keeps its own licence. The texts",
        "are copied from the files of each component, without change. The program itself is",
        "licensed under the Apache License 2.0 (see LICENSE and NOTICE).",
        "",
        "Qt, PySide6 and shiboken6 are used under the GNU Lesser General Public License,",
        "version 3 (LGPL-3.0).",
        "The libraries stay separate files of this folder, so you can replace them with another",
        "compatible version (docs/developer/replace-qt.md in the source). The exact source code of",
        "the Qt and PySide6 versions in this release is attached to the release on GitHub.",
        "",
    ]
    out.append("CONTENTS")
    for c in components:
        out.append(f"  - {c.name} {c.version}".rstrip() + f"  [{c.spdx or 'licence not recorded'}]")
    out.append("")
    for c in components:
        out += ["=" * 78, f"{c.name} {c.version}".strip(), f"Licence: {c.spdx or 'not recorded'}"]
        if c.source:
            out.append(f"Source of the licence information: {c.source}")
        if c.known_gap:
            out.append(f"NOTE: {c.known_gap}")
        shown = 0
        for text in c.texts:
            path = bundle / text
            if path.is_file():
                shown += 1
                out += [
                    "-" * 78,
                    f"[{text}]",
                    "",
                    path.read_text(encoding="utf-8", errors="replace").rstrip(),
                    "",
                ]
        if not shown:
            out += ["(the licence text of this component is not part of this file)", ""]
    return "\n".join(out) + "\n"


# ---- sbom ---------------------------------------------------------------------------------------
def add_to_sbom(bundle: Path, sbom: Path) -> int:
    components = [
        Component(**c)
        for c in json.loads((bundle / "licences" / "COMPONENTS.json").read_text(encoding="utf-8"))
    ]
    data = json.loads(sbom.read_text(encoding="utf-8"))
    present = {c.get("name", "").lower() for c in data.get("components", [])}
    added = 0
    for comp in components:
        if comp.group == "python" and comp.name.lower() in present:
            continue
        entry: dict = {
            "type": "library" if comp.group != "font" else "data",
            "bom-ref": f"sbs:{comp.group}:{re.sub(r'[^A-Za-z0-9_.-]+', '-', comp.name)}",
            "name": comp.name,
            "version": comp.version or "unknown",
            "licenses": [{"expression": comp.spdx}] if comp.spdx else [],
            "properties": [
                {"name": "sbs:group", "value": comp.group},
                {"name": "sbs:files", "value": str(len(comp.files))},
            ],
        }
        if comp.source:
            entry["properties"].append({"name": "sbs:licence-source", "value": comp.source})
        data.setdefault("components", []).append(entry)
        added += 1
    sbom.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return added


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect")
    c.add_argument("bundle", type=Path)
    c.add_argument("--qt-notices", type=Path)
    k = sub.add_parser("check")
    k.add_argument("bundle", type=Path)
    k.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="development build: system libraries need not be identified",
    )
    n = sub.add_parser("notices")
    n.add_argument("bundle", type=Path)
    s = sub.add_parser("sbom")
    s.add_argument("bundle", type=Path)
    s.add_argument("sbom", type=Path)
    args = parser.parse_args(argv)
    if args.command == "collect":
        comps = collect(args.bundle, args.qt_notices)
        print(f"{len(comps)} components recorded in {args.bundle / 'licences' / 'COMPONENTS.json'}")
        return 0
    if args.command == "notices":
        (args.bundle / "THIRD_PARTY_NOTICES.txt").write_text(notices(args.bundle), encoding="utf-8")
        print(f"wrote {args.bundle / 'THIRD_PARTY_NOTICES.txt'}")
        return 0
    if args.command == "sbom":
        print(f"{add_to_sbom(args.bundle, args.sbom)} components added to {args.sbom}")
        return 0
    problems = check(
        args.bundle, args.allow_unresolved or os.environ.get("SBS_ALLOW_UNRESOLVED") == "1"
    )
    for p in problems:
        print(f"PROBLEM: {p}")
    print("Licence gate:", "FAILED" if problems else "passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
