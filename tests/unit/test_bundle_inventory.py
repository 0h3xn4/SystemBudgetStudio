# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The licence policy and the bundle inventory (packaging/bundle_policy.py, bundle_inventory.py)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packaging"))


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "packaging" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load("bundle_policy")
inventory = load("bundle_inventory")
fetch = load("fetch_sources")


# ---- licence expressions -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "expression",
    [
        "MIT",
        "Apache-2.0",
        "LGPL-3.0-only",
        "LGPL-2.1-or-later",
        "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
        "AFL-2.1 OR GPL-2.0-or-later",  # the option used is the allowed one
        "GPL-3.0-or-later WITH GCC-exception-3.1",
        "GPL-2.0-or-later WITH Bootloader-exception",
        "OFL-1.1",
        "ISC AND MIT",
    ],
)
def test_accepted_licences(expression: str) -> None:
    assert policy.licence_verdict(expression).ok, expression


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "GPL-2.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "SSPL-1.0",
        "CC-BY-NC-4.0",
        "CC-BY-ND-4.0",
        "MIT AND GPL-3.0-only",  # both are needed
        "SomethingNew-1.0",  # unknown
        "UNKNOWN-whatever",
        "NOASSERTION",
    ],
)
def test_refused_licences(expression: str) -> None:
    assert not policy.licence_verdict(expression).ok, expression


@pytest.mark.parametrize(
    ("field", "spdx"),
    [
        ("LGPLv2+", "LGPL-2.1-or-later"),
        ("ASL 2.0", "Apache-2.0"),
        ("GPLv3+ with exceptions", "GPL-3.0-or-later WITH GCC-exception-3.1"),
        ("MIT and BSD", "MIT AND BSD-3-Clause"),
        ("BSD License", "BSD-3-Clause"),
        ("Public Domain", "LicenseRef-PublicDomain"),
    ],
)
def test_names_of_the_package_managers_become_spdx(field: str, spdx: str) -> None:
    assert policy.normalise_licence(field) == spdx


def test_an_unknown_name_is_never_accepted() -> None:
    expression = policy.normalise_licence("Weird Licence 9")
    assert not policy.licence_verdict(expression).ok


def test_every_licence_of_the_runtime_lock_is_accepted() -> None:
    """The Python packages of docs/LICENCES.md are all inside the policy."""
    rows = (ROOT / "docs" / "LICENCES.md").read_text(encoding="utf-8").splitlines()
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) == 3 and cells[2] in ("permissive", "lgpl"):
            expression = policy.normalise_licence(cells[1])
            assert policy.licence_verdict(expression).ok, (cells[0], expression)


def test_no_allowed_licence_is_on_the_deny_list() -> None:
    raw = tomllib.loads((ROOT / "packaging" / "bundle_policy.toml").read_text(encoding="utf-8"))
    import re

    for identifier in raw["licences"]["allow"]:
        assert not any(re.search(p, identifier) for p in raw["licences"]["deny_patterns"]), (
            identifier
        )


# ---- Qt -----------------------------------------------------------------------------------------
def test_the_qt_libraries_of_the_policy() -> None:
    assert policy.qt_library_wanted("libQt6Core.so.6")
    assert policy.qt_library_wanted("Qt6Widgets.dll")
    assert not policy.qt_library_wanted("libQt6Svg.so.6")
    assert not policy.qt_library_wanted("Qt6Network.dll")
    assert not policy.qt_library_wanted("libQt6Charts.so.6")
    assert policy.is_gpl_only_qt("libQt6Charts.so.6")
    assert policy.is_gpl_only_qt("Qt6DataVisualization.dll")
    assert policy.is_gpl_only_qt("libQt6VirtualKeyboard.so.6")


def test_no_gpl_only_qt_module_is_among_the_kept_ones() -> None:
    kept = set(policy.POLICY["qt"]["keep_libraries"])
    assert not kept & set(policy.POLICY["qt"]["gpl_only_modules"])


@pytest.mark.parametrize(
    ("path", "wanted"),
    [
        ("platforms/libqxcb.so", True),
        ("platforms/qwindows.dll", True),
        ("platforms/libqoffscreen.so", True),
        ("platforms/libqwayland.so", True),
        ("styles/qmodernwindowsstyle.dll", True),
        ("platformthemes/libqxdgdesktopportal.so", True),
        ("imageformats/libqjpeg.so", False),
        ("iconengines/libqsvgicon.so", False),
        ("platforms/libqeglfs.so", False),
        ("platforms/qdirect2d.dll", False),
        ("generic/libqevdevmouseplugin.so", False),
        ("tls/qcertonlybackend.dll", False),
        ("wayland-decoration-client/libadwaita.so", False),
    ],
)
def test_qt_plugins(path: str, wanted: bool) -> None:
    assert policy.qt_plugin_wanted(path) is wanted


def test_the_spec_filter_keeps_what_the_program_needs() -> None:
    keep = policy.keep_entry
    assert keep("libQt6Core.so.6") and keep("PySide6/QtCore.abi3.so") and keep("PySide6/QtGui.pyd")
    assert not keep("libQt6Svg.so.6") and not keep("PySide6/QtSvg.abi3.so")
    assert not keep("PySide6/Qt/translations/qt_de.qm")
    assert keep("PySide6/Qt/plugins/platforms/libqxcb.so")
    assert not keep("PySide6/Qt/plugins/imageformats/libqsvg.so")
    assert keep("numpy/_core/_multiarray_umath.so") and keep("libz.so.1")


def test_the_window_imports_only_the_qt_modules_of_the_policy() -> None:
    """src/ imports no PySide6 module that the bundle leaves out (QtSvg: build scripts only)."""
    import re

    allowed = {f"Qt{m.removeprefix('Qt')}" for m in policy.POLICY["qt"]["keep_python_modules"]}
    used: set[str] = set()
    for path in (ROOT / "src").rglob("*.py"):
        used |= set(re.findall(r"from PySide6\.(Qt[A-Za-z]+)", path.read_text(encoding="utf-8")))
    assert used <= allowed, f"modules the bundle leaves out: {sorted(used - allowed)}"


# ---- the inventory and the gate on a fake bundle -----------------------------------------
class FakeRpm:
    available = True

    def __init__(
        self, table: dict[str, tuple[str, str, str]], files: dict[str, list[Path]]
    ) -> None:
        self.table, self.files = table, files

    def owner(self, path: Path):  # type: ignore[no-untyped-def]
        entry = self.table.get(path.name)
        if entry is None:
            return None
        name, version, lic = entry
        return inventory.Package(name, version, lic, self.files.get(name, []))


def make_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    internal = bundle / "_internal"
    for rel in (
        "libQt6Core.so.6",
        "libz.so.1",
        "libweird.so.1",
        "libpython3.14.so.1.0",
        "PySide6/Qt/plugins/platforms/libqxcb.so",
    ):
        path = internal / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    (bundle / "licences").mkdir()
    (bundle / "licences" / "INDEX.md").write_text(
        "# x\n\n| Package | Licence | Files |\n|---|---|---|\n", encoding="utf-8"
    )
    (bundle / "THIRD_PARTY_NOTICES.txt").write_text("x", encoding="utf-8")
    (bundle / "budget").write_bytes(b"x")
    return bundle


def test_the_inventory_gate_on_a_fake_bundle(tmp_path: Path) -> None:
    licence_dir = tmp_path / "rpmlicenses"
    licence_dir.mkdir()
    zlib_text = licence_dir / "LICENSE"
    zlib_text.write_text("zlib licence text\n", encoding="utf-8")
    bundle = make_bundle(tmp_path)
    backend = FakeRpm(
        {"libz.so.1": ("zlib", "1.2", "zlib"), "libweird.so.1": ("weird", "1", "Weird Licence 9")},
        {"zlib": [zlib_text]},
    )
    components = inventory.collect(bundle, backend=backend)  # type: ignore[arg-type]
    by_name = {c.name: c for c in components}
    assert by_name["zlib"].spdx == "Zlib" and by_name["zlib"].texts
    assert (bundle / by_name["zlib"].texts[0]).read_text(encoding="utf-8") == "zlib licence text\n"
    assert by_name["weird"].spdx.startswith("UNKNOWN-")
    problems = inventory.check(bundle)
    assert any("weird" in p and "not accepted" in p for p in problems)
    assert not any("zlib" in p for p in problems)
    assert any("Qt: no third-party notices" in p for p in problems)
    # the notices copy the texts without change
    notices = inventory.notices(bundle)
    assert "zlib licence text" in notices and "Licence: Zlib" in notices


def test_a_file_that_belongs_to_no_component_fails_the_gate(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    inventory.collect(bundle, backend=FakeRpm({}, {}))  # type: ignore[arg-type]
    (bundle / "_internal" / "libnew.so.1").write_bytes(b"x")
    problems = inventory.check(bundle)
    assert any("libnew.so.1" in p for p in problems)


def test_a_component_without_a_licence_text_fails_the_gate(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    backend = FakeRpm({"libz.so.1": ("zlib", "1.2", "zlib")}, {"zlib": []})
    inventory.collect(bundle, backend=backend)  # type: ignore[arg-type]
    assert any("zlib" in p and "no licence text" in p for p in inventory.check(bundle))


def test_a_gpl_only_qt_module_fails_the_gate_whatever_the_record_says(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    inventory.collect(bundle, backend=FakeRpm({}, {}))  # type: ignore[arg-type]
    (bundle / "_internal" / "libQt6Charts.so.6").write_bytes(b"x")
    (bundle / "_internal" / "libQt6Svg.so.6").write_bytes(b"x")
    problems = inventory.check(bundle)
    assert any("GPL-only Qt module" in p and "Charts" in p for p in problems)
    assert any("does not use" in p and "Svg" in p for p in problems)


def test_a_qt_plugin_outside_the_policy_fails_the_gate(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    inventory.collect(bundle, backend=FakeRpm({}, {}))  # type: ignore[arg-type]
    plugin = bundle / "_internal" / "PySide6" / "Qt" / "plugins" / "imageformats" / "libqsvg.so"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(b"x")
    assert any("Qt plugin the program does not use" in p for p in inventory.check(bundle))


def test_the_sbom_gets_the_components_that_are_not_python_packages(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    inventory.collect(bundle, backend=FakeRpm({"libz.so.1": ("zlib", "1.2", "zlib")}, {}))  # type: ignore[arg-type]
    sbom = tmp_path / "sbom.json"
    sbom.write_text(json.dumps({"components": [{"name": "numpy"}]}), encoding="utf-8")
    assert inventory.add_to_sbom(bundle, sbom) >= 2
    names = {c["name"] for c in json.loads(sbom.read_text(encoding="utf-8"))["components"]}
    assert {"zlib", "Python"} <= names


# ---- the sources of the LGPL components -------------------------------------------------
def test_the_sources_match_the_locked_pyside6_version() -> None:
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    version = next(
        line.split("==")[1].split()[0]
        for line in lock.splitlines()
        if line.startswith("pyside6-essentials==")
    )
    sources = fetch.load()
    assert {s["name"] for s in sources} == {"qtbase", "qtwayland", "pyside-setup"}
    for source in sources:
        assert source["version"] == version, source["name"]
        assert version in str(source["url"])
        assert len(str(source["sha256"])) == 64
        assert str(source["url"]).startswith("https://download.qt.io/")
        assert str(source["sha256_published_at"]).endswith(".sha256")


@pytest.mark.parametrize(
    ("member", "wanted"),
    [
        ("qtbase-everywhere-src-6.10.3/src/3rdparty/harfbuzz-ng/COPYING", True),
        ("qtbase-everywhere-src-6.10.3/src/3rdparty/freetype/LICENSE.TXT", True),
        ("qtbase-everywhere-src-6.10.3/src/3rdparty/pcre2/LICENCE.md", True),
        ("qtbase-everywhere-src-6.10.3/LICENSES/LGPL-3.0-only.txt", True),
        ("qtbase-everywhere-src-6.10.3/src/corelib/io/qfile.cpp", False),
        ("qtbase-everywhere-src-6.10.3/src/3rdparty/harfbuzz-ng/src/hb.cc", False),
    ],
)
def test_which_files_of_the_qt_archive_are_third_party_notices(member: str, wanted: bool) -> None:
    assert fetch.wanted_notice(member) is wanted


def test_the_original_of_a_copied_library_is_found_by_name_and_size(tmp_path: Path) -> None:
    system = tmp_path / "lib64"
    system.mkdir()
    (system / "libz.so.1.2.11").write_bytes(b"12345")
    (system / "libz.so.1").symlink_to("libz.so.1.2.11")
    (system / "libother.so.1").write_bytes(b"1234567")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "libz.so.1").write_bytes(b"12345")  # a copy, as PyInstaller makes it
    (bundle / "libother.so.1").write_bytes(b"12")  # a different file with the same name
    (bundle / "libwheel-1a2b3c4d.so.1").write_bytes(b"1")  # not on the system
    found = inventory.system_original(bundle / "libz.so.1", (str(system),))
    assert found == system / "libz.so.1"
    assert inventory.system_original(bundle / "libother.so.1", (str(system),)) is None
    assert inventory.system_original(bundle / "libwheel-1a2b3c4d.so.1", (str(system),)) is None


def test_every_package_override_of_the_policy_is_accepted_and_explained() -> None:
    overrides = policy.POLICY["package_overrides"]
    assert overrides, "the Rocky 9 libraries need them"
    for name, entry in overrides.items():
        assert entry["reason"].strip(), name
        assert policy.licence_verdict(entry["spdx"]).ok, name


def test_the_icu_libraries_of_the_wheel_get_their_own_component_and_text(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    (bundle / "_internal" / "libicudata.so.73").write_bytes(b"x")
    components = inventory.collect(bundle, backend=FakeRpm({}, {}))  # type: ignore[arg-type]
    icu = next(c for c in components if c.name.startswith("ICU"))
    assert icu.files == ["_internal/libicudata.so.73"]
    assert icu.texts and (bundle / icu.texts[0]).read_text(encoding="utf-8").startswith("UNICODE")
    assert policy.licence_verdict(icu.spdx).ok
    assert not any("libicudata" in p for p in inventory.check(bundle))


def test_a_rhel_licence_field_with_zlib_acknowledgement_is_accepted() -> None:
    field = "(FTL or GPLv2+) and BSD and MIT and Public Domain and zlib with acknowledgement"
    assert policy.licence_verdict(policy.normalise_licence(field)).ok


FAKE_RPM = """#!/usr/bin/env python3
import json, os, sys
db = json.load(open(os.environ["FAKE_RPM_DB"]))
args = sys.argv[1:]
if args[0] == "-qa":
    for name, info in db.items():
        print(f"{name}\\t{info['srpm']}")
elif args[0] == "-q" and "--qf" in args:
    fmt, name = args[args.index("--qf") + 1], args[-1]
    info = db.get(name)
    if info is None:
        sys.exit(1)
    print(fmt.replace("%{SOURCERPM}", info["srpm"]).replace("%{NAME}", name), end="")
elif args[0] in ("-qL", "-qd", "-ql"):
    info = db.get(args[1])
    if info is None:
        sys.exit(1)
    for path in info["files"][args[0]]:
        print(path)
else:
    sys.exit(1)
"""


def test_the_licence_text_of_a_source_package_is_found_in_a_sibling(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """libX11-xcb has no licence file; libX11-common, built from the same source, has."""
    import os
    import stat

    text = tmp_path / "COPYING"
    text.write_text("X11 licence\n", encoding="utf-8")
    db = {
        "libX11-xcb": {"srpm": "libX11-1.8.src.rpm", "files": {"-qL": [], "-qd": [], "-ql": []}},
        "libX11-common": {
            "srpm": "libX11-1.8.src.rpm",
            "files": {"-qL": [str(text)], "-qd": [], "-ql": []},
        },
        "lonely": {"srpm": "lonely-1.src.rpm", "files": {"-qL": [], "-qd": [], "-ql": []}},
    }
    (tmp_path / "db.json").write_text(json.dumps(db), encoding="utf-8")
    fake = tmp_path / "bin" / "rpm"
    fake.parent.mkdir()
    fake.write_text(FAKE_RPM, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_RPM_DB", str(tmp_path / "db.json"))
    backend = inventory.RpmBackend()
    assert backend.available
    assert backend.siblings("libX11-xcb") == ["libX11-xcb", "libX11-common"]
    assert backend.licence_files("libX11-xcb") == [text]
    assert backend.licence_files("lonely") == []
    assert "none listed" in backend.documents("lonely")
