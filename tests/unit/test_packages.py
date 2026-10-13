"""The .deb and .rpm packages: built from a small stand-in bundle and read back (D-149)."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import lzma
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Linux packages")

ROOT = Path(__file__).resolve().parents[2]
LINUX = ROOT / "packaging" / "linux"


def load_make_deb() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_deb", LINUX / "make_deb.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_deb"] = module
    spec.loader.exec_module(module)
    return module


make_deb = load_make_deb()


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    folder = tmp_path / "system-budget-studio"
    icons = folder / "_internal" / "budget_core" / "assets" / "icons"
    icons.mkdir(parents=True)
    for size in (16, 256):
        (icons / f"logo-{size}.png").write_bytes(f"png {size}".encode())
    (icons / "logo.ico").write_bytes(b"not a png")
    (folder / "_internal" / "libfoo.so.1.2").write_bytes(b"lib")
    (folder / "_internal" / "libfoo.so.1").symlink_to("libfoo.so.1.2")
    for name in ("system-budget-studio", "budget"):
        (folder / name).write_text("#!/bin/sh\n")
        (folder / name).chmod(0o755)
    for name in ("install.sh", "uninstall.sh"):
        (folder / name).write_text("#!/bin/sh\n")
    (folder / "LICENSE").write_text("MIT licence text\n")
    (folder / "licences.md").write_text("# licences\n")
    return folder


def read_ar(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()
    assert data[:8] == b"!<arch>\n"
    members: dict[str, bytes] = {}
    at = 8
    while at < len(data):
        header = data[at : at + 60]
        assert header[58:60] == b"`\n"
        name, size = header[:16].decode().strip(), int(header[48:58])
        members[name] = data[at + 60 : at + 60 + size]
        at += 60 + size + (size % 2)
    return members


def open_tar(blob: bytes) -> tarfile.TarFile:
    return tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")


@pytest.fixture
def deb(bundle: Path, tmp_path: Path) -> Path:
    return make_deb.build(bundle, tmp_path / "out", "1.0.0-1", mtime=1_700_000_000)


# ---- .deb ------------------------------------------------------------------------------------
def test_the_deb_is_an_ar_archive_of_the_three_members_in_order(deb: Path) -> None:
    assert deb.name == "system-budget-studio_1.0.0-1_amd64.deb"
    members = read_ar(deb)
    assert list(members) == ["debian-binary", "control.tar.gz", "data.tar.xz"]
    assert members["debian-binary"] == b"2.0\n"


def test_the_control_file_names_the_package_and_what_it_needs(deb: Path) -> None:
    control = open_tar(read_ar(deb)["control.tar.gz"])
    fields = control.extractfile("./control").read().decode()  # type: ignore[union-attr]
    assert fields.startswith("Package: system-budget-studio\nVersion: 1.0.0-1\n")
    for line in (
        "Architecture: amd64",
        "Section: science",
        "Homepage: https://github.com/0h3xn4/SystemBudgetStudio",
    ):
        assert line in fields
    depends = next(x for x in fields.splitlines() if x.startswith("Depends: "))
    for needed in ("libegl1", "libgl1", "libxkbcommon-x11-0", "libxcb-cursor0", "libfontconfig1"):
        assert needed in depends
    for script in ("postinst", "postrm"):
        assert control.getmember(f"./{script}").mode == 0o755
    assert "Installed-Size: " in fields
    for line in fields.splitlines():  # a field or a continuation line, nothing else
        assert line.startswith(" ") or ": " in line


def test_the_data_holds_the_bundle_the_links_the_entry_and_the_icons(deb: Path) -> None:
    data = open_tar(read_ar(deb)["data.tar.xz"])
    names = set(data.getnames())
    for path in (
        "./opt/system-budget-studio/budget",
        "./opt/system-budget-studio/LICENSE",
        "./opt/system-budget-studio/_internal/libfoo.so.1.2",
        "./usr/share/applications/system-budget-studio.desktop",
        "./usr/share/icons/hicolor/16x16/apps/system-budget-studio.png",
        "./usr/share/icons/hicolor/256x256/apps/system-budget-studio.png",
        "./usr/share/doc/system-budget-studio/copyright",
    ):
        assert path in names, path
    assert "./opt/system-budget-studio/install.sh" not in names  # the per-user installer
    assert "./opt/system-budget-studio/uninstall.sh" not in names
    assert not any("logo.ico" in n and "hicolor" in n for n in names)
    link = data.getmember("./usr/bin/budget")
    assert link.issym() and link.linkname == "/opt/system-budget-studio/budget"
    kept = data.getmember("./opt/system-budget-studio/_internal/libfoo.so.1")
    assert kept.issym() and kept.linkname == "libfoo.so.1.2"
    assert data.getmember("./opt/system-budget-studio/budget").mode == 0o755
    assert data.getmember("./opt/system-budget-studio/LICENSE").mode == 0o644
    assert data.getmember("./opt").isdir()
    assert all(m.uid == 0 and m.gid == 0 for m in data.getmembers())
    copyright_text = data.extractfile("./usr/share/doc/system-budget-studio/copyright").read()  # type: ignore[union-attr]
    assert b"MIT licence text" in copyright_text


def test_the_md5sums_match_the_files(deb: Path) -> None:
    members = read_ar(deb)
    sums = open_tar(members["control.tar.gz"]).extractfile("./md5sums").read().decode()  # type: ignore[union-attr]
    data = open_tar(members["data.tar.xz"])
    listed = dict(line.split("  ", 1)[::-1] for line in sums.splitlines())
    files = [m for m in data.getmembers() if m.isfile()]
    assert len(listed) == len(files)
    for member in files:
        content = data.extractfile(member).read()  # type: ignore[union-attr]
        assert listed[member.name[2:]] == hashlib.md5(content).hexdigest()


def test_the_same_bundle_gives_the_same_package(bundle: Path, tmp_path: Path) -> None:
    first = make_deb.build(bundle, tmp_path / "a", "1.0.0-1", mtime=5)
    second = make_deb.build(bundle, tmp_path / "b", "1.0.0-1", mtime=5)
    assert first.read_bytes() == second.read_bytes()


def test_a_folder_that_is_not_a_bundle_is_refused(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit):
        make_deb.build(tmp_path / "empty", tmp_path / "out", "1.0.0-1")


def test_the_version_is_the_one_of_the_tool() -> None:
    from budget_core import __version__

    assert make_deb.version_of() == __version__


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb not installed")
def test_dpkg_accepts_the_package_and_unpacks_it(deb: Path, tmp_path: Path) -> None:
    info = subprocess.run(["dpkg-deb", "--info", str(deb)], capture_output=True, text=True)
    assert info.returncode == 0, info.stderr
    assert "Package: system-budget-studio" in info.stdout
    target = tmp_path / "unpacked"
    done = subprocess.run(["dpkg-deb", "-x", str(deb), str(target)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (target / "opt/system-budget-studio/budget").is_file()
    assert (target / "usr/bin/budget").is_symlink()
    check = subprocess.run(["dpkg-deb", "-e", str(deb), str(tmp_path / "ctl")], check=False)
    assert check.returncode == 0
    assert (tmp_path / "ctl" / "postinst").stat().st_mode & 0o111


def test_xz_is_what_the_data_member_uses(deb: Path) -> None:
    assert lzma.decompress(read_ar(deb)["data.tar.xz"])[:2] != b""


# ---- the files both packages share ------------------------------------------------------------
def test_the_system_menu_entry_points_at_the_linked_program_and_the_icon() -> None:
    entry = (LINUX / "system-budget-studio.desktop").read_text(encoding="utf-8")
    lines = dict(line.split("=", 1) for line in entry.splitlines() if "=" in line)
    assert lines["Exec"] == "/usr/bin/system-budget-studio %f"
    assert lines["Icon"] == "system-budget-studio" and lines["Terminal"] == "false"
    assert lines["Type"] == "Application" and lines["Categories"].endswith(";")
    if shutil.which("desktop-file-validate"):
        done = subprocess.run(
            ["desktop-file-validate", str(LINUX / "system-budget-studio.desktop")],
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stdout + done.stderr


def test_the_two_packages_need_the_same_things_of_the_system() -> None:
    spec = (LINUX / "system-budget-studio.spec").read_text(encoding="utf-8")
    requires = {
        line.split(None, 1)[1].strip() for line in spec.splitlines() if line.startswith("Requires:")
    }
    # the window needs OpenGL, the keyboard and font libraries, D-Bus and the xcb helpers
    for needed in ("mesa-libEGL", "mesa-libGL", "libxkbcommon-x11", "fontconfig", "dbus-libs"):
        assert needed in requires
    assert "xcb-util-cursor" in requires and "AutoReqProv:    no" in spec
    assert "install.sh" in spec  # the per-user scripts are taken out of the package


def test_the_rpm_script_is_valid_shell() -> None:
    assert subprocess.run(["sh", "-n", str(LINUX / "make_rpm.sh")]).returncode == 0
    assert subprocess.run(["sh", "-n", str(LINUX / "test_package.sh")]).returncode == 0


# ---- .rpm (only where rpmbuild is installed) ---------------------------------------------------
@pytest.mark.skipif(shutil.which("rpmbuild") is None, reason="rpmbuild not installed")
def test_the_rpm_lists_the_same_files_and_requirements(bundle: Path, tmp_path: Path) -> None:
    out = tmp_path / "rpms"
    done = subprocess.run(
        ["sh", str(LINUX / "make_rpm.sh"), str(bundle), str(out), "1.0.0"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    rpm = out / "system-budget-studio-1.0.0-1.x86_64.rpm"
    assert rpm.is_file()
    listing = subprocess.run(["rpm", "-qlp", str(rpm)], capture_output=True, text=True).stdout
    for path in (
        "/opt/system-budget-studio/budget",
        "/usr/bin/budget",
        "/usr/bin/system-budget-studio",
        "/usr/share/applications/system-budget-studio.desktop",
        "/usr/share/icons/hicolor/16x16/apps/system-budget-studio.png",
        "/usr/share/icons/hicolor/256x256/apps/system-budget-studio.png",
    ):
        assert path in listing.splitlines(), path
    assert "install.sh" not in listing
    needs = subprocess.run(["rpm", "-qp", "--requires", str(rpm)], capture_output=True, text=True)
    assert "mesa-libEGL" in needs.stdout and "xcb-util-cursor" in needs.stdout
    info = subprocess.run(["rpm", "-qpi", str(rpm)], capture_output=True, text=True).stdout
    assert "License     : MIT" in info and "Architecture: x86_64" in info
