# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The licence is named the same way everywhere (protection programme, phase 3)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from budget_core import about

ROOT = Path(__file__).resolve().parents[2]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_license_file_is_the_unmodified_apache_text() -> None:
    text = read("LICENSE")
    assert "Apache License" in text and "Version 2.0, January 2004" in text
    assert "END OF TERMS AND CONDITIONS" in text
    # the licences folder holds the same text for the REUSE tool
    assert read("LICENSES/Apache-2.0.txt") == text


def test_pyproject_names_the_licence_and_ships_the_notice() -> None:
    project = tomllib.loads(read("pyproject.toml"))["project"]
    assert project["license"] == about.PROJECT_LICENCE_SPDX == "Apache-2.0"
    assert "NOTICE" in project["license-files"] and "LICENSE" in project["license-files"]
    assert not any("License ::" in c for c in project["classifiers"])


def test_notice_names_the_project_the_holder_and_the_old_releases() -> None:
    notice = read("NOTICE")
    assert "System Budget Studio" in notice
    assert about.COPYRIGHT_LINE in notice
    assert about.OWNERSHIP_STATEMENT.replace("\n", " ") in " ".join(notice.split())
    assert f"up to and including {about.LAST_MIT_RELEASE}" in notice
    assert (ROOT / "docs/legal/MIT-licence-releases-up-to-2.11.1.txt").is_file()


def test_readme_badge_text_and_ownership_statement() -> None:
    readme = read("README.md")
    assert "licence-Apache--2.0" in readme and "licence-MIT" not in readme
    assert about.OWNERSHIP_STATEMENT in readme
    assert "Apache License 2.0" in readme and about.LAST_MIT_RELEASE in readme


def test_packages_name_the_licence() -> None:
    spec = read("packaging/linux/system-budget-studio.spec")
    assert re.search(r"^License:\s+Apache-2\.0\s*$", spec, flags=re.M)
    assert "LicenseFile=" in read("packaging/windows/system_budget_studio.iss")
    assert "Apache License, Version 2.0" in read("packaging/linux/make_deb.py")


def test_no_file_still_says_the_project_is_mit_licensed() -> None:
    # only the history may call the project MIT: "up to and including 2.11.1"
    for name in ("README.md", "docs/faq.md", "pyproject.toml", "packaging/linux/make_deb.py"):
        text = read(name)
        assert "[MIT licence](LICENSE)" not in text and "[MIT licence](../LICENSE)" not in text
        assert "Released under the MIT licence (below)" not in text, name


def test_about_text_carries_version_owner_and_licence() -> None:
    text = about.about_text()
    assert about.OWNERSHIP_STATEMENT in text
    assert about.PROJECT_LICENCE_SPDX in text
    assert about.COPYRIGHT_LINE in text
