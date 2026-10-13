"""packaging/attach_release.sh against a stub `gh`: what it checks, renames and uploads."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell script")

SCRIPT = Path(__file__).resolve().parents[2] / "packaging" / "attach_release.sh"

# A stand-in for the GitHub CLI: `run download` writes the two artefacts the workflow makes, the
# other commands only record what they were asked to do.
FAKE_GH = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$1 $2" in
  "run download")
    dest="$5"   # gh run download <id> --dir <dest>
    for os_name in windows linux; do
      [ -d "$FAKE_FILES/$os_name" ] || continue
      target="$dest/system-budget-studio-$(echo "${os_name:0:1}" | tr a-z A-Z)${os_name:1}"
      mkdir -p "$target"
      cp "$FAKE_FILES/$os_name"/* "$target/"
    done
    ;;
  "release view") [ "${FAKE_RELEASE_EXISTS:-0}" = 1 ] ;;
  "release create") ;;
  "release upload") ;;
  *) echo "unexpected: $*" >&2; exit 9 ;;
esac
"""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def files(tmp_path: Path) -> Path:
    root = tmp_path / "artefacts"
    win, lin = root / "windows", root / "linux"
    win.mkdir(parents=True)
    lin.mkdir()
    for name, folder in (
        ("system-budget-studio-1.0.0-windows-x64-setup.exe", win),
        ("system-budget-studio-1.0.0-windows-x64-portable.zip", win),
        ("system-budget-studio-1.0.0-linux-x86_64.tar.gz", lin),
        ("system-budget-studio_1.0.0-1_amd64.deb", lin),
        ("system-budget-studio-1.0.0-1.x86_64.rpm", lin),
    ):
        (folder / name).write_bytes(name.encode())
    for folder in (win, lin):
        lines = [
            f"{sha(p)}  {p.name}" for p in sorted(folder.iterdir()) if p.name != "SHA256SUMS.txt"
        ]
        (folder / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    (lin / "sbom.cdx.json").write_text("{}")
    (lin / "licences.md").write_text("# licences\n")
    (win / "sbom.cdx.json").write_text("{}")
    (win / "licences.md").write_text("# licences\n")
    return root


def run(
    tmp_path: Path, files: Path, *args: str, exists: bool = False
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOG": str(log),
        "FAKE_FILES": str(files),
        "FAKE_RELEASE_EXISTS": "1" if exists else "0",
    }
    done = subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60
    )
    return done, log.read_text().splitlines()


def test_files_are_checked_renamed_and_uploaded_to_a_new_draft_release(
    tmp_path: Path, files: Path
) -> None:
    done, calls = run(tmp_path, files, "123", "v1.0.0")
    assert done.returncode == 0, done.stderr
    assert any(c.startswith("release create v1.0.0 --draft") for c in calls)
    upload = next(c for c in calls if c.startswith("release upload v1.0.0"))
    assert "--clobber" in upload
    names = sorted(Path(p).name for p in upload.split() if "/upload/" in p)
    assert names == [
        "SHA256SUMS-linux.txt",
        "SHA256SUMS-windows.txt",
        "licences.md",
        "sbom.cdx.json",
        "system-budget-studio-1.0.0-1.x86_64.rpm",
        "system-budget-studio-1.0.0-linux-x86_64.tar.gz",
        "system-budget-studio-1.0.0-windows-x64-portable.zip",
        "system-budget-studio-1.0.0-windows-x64-setup.exe",
        "system-budget-studio_1.0.0-1_amd64.deb",
    ]


def test_an_existing_release_is_not_created_again(tmp_path: Path, files: Path) -> None:
    done, calls = run(tmp_path, files, "123", "v1.0.0", exists=True)
    assert done.returncode == 0, done.stderr
    assert not any(c.startswith("release create") for c in calls)
    assert any(c.startswith("release upload") for c in calls)


def test_a_file_that_does_not_match_its_checksum_is_never_uploaded(
    tmp_path: Path, files: Path
) -> None:
    (files / "linux" / "system-budget-studio-1.0.0-linux-x86_64.tar.gz").write_bytes(b"changed")
    done, calls = run(tmp_path, files, "123", "v1.0.0")
    assert done.returncode != 0
    assert not any(c.startswith("release") for c in calls)


def test_a_run_without_the_windows_artefact_is_refused(tmp_path: Path, files: Path) -> None:
    for item in (files / "windows").iterdir():
        item.unlink()
    (files / "windows").rmdir()
    done, calls = run(tmp_path, files, "123", "v1.0.0")
    assert done.returncode == 1 and "system-budget-studio-Windows" in done.stderr
    assert not any(c.startswith("release") for c in calls)


@pytest.mark.parametrize("args", [(), ("123",), ("123", "1.0.0"), ("123", "latest")])
def test_wrong_arguments_are_refused(tmp_path: Path, files: Path, args: tuple[str, ...]) -> None:
    done, calls = run(tmp_path, files, *args)
    assert done.returncode == 2
    assert not calls
