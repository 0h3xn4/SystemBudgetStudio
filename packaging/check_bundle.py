#!/usr/bin/env python3
"""Check a built bundle folder before it is released (standard library only).

    python packaging/check_bundle.py dist/system-budget-studio

Fails (exit 1) when development code such as hypothesis, mypy or pytest was bundled, or when the
licence material the licences require is missing: the licence texts, `licences.md` and the SBOM,
or when the application icon or the user-interface icons (assets/icons) were not bundled.
"""

from __future__ import annotations

import sys
from pathlib import Path

FORBIDDEN = (
    "hypothesis",
    "mypy",
    "mypyc",
    "pytest",
    "_pytest",
    "pytestqt",
    "pip",
    "setuptools",
    "PyInstaller",
    "ruff",
    "IPython",
    "chardet",  # not a dependency of the tool; pulled in only because it was installed
)
REQUIRED_FILES = (
    "LICENSE",
    "licences.md",
    "sbom.cdx.json",
    "licences/INDEX.md",
    "licences/pyside6-essentials/LGPL-3.0.txt",
)


# the window icon (D-148), the fonts and images of the window (D-169, D-170); the data files are in
# `_internal` of a PyInstaller bundle
ICONS = (
    "budget_core/assets/icons/logo-256.png",
    "budget_core/assets/icons/ui/circle-check-24.png",  # the user-interface icons (D-150)
    "budget_core/assets/icons/ui/theme/chevron-down-light.png",  # arrows of the style sheet
    "budget_core/assets/fonts/Inter-Regular.ttf",
    "budget_core/assets/fonts/JetBrainsMono-Regular.ttf",
)
EXECUTABLES = ("system-budget-studio", "budget")
# the private Python of the bundle: the installers need no Python on the machine (D-184)
INTERPRETER_PATTERNS = ("libpython3*.so*", "python3*.dll", "libpython3*.dylib")


def has_executable(bundle: Path, name: str) -> bool:
    """The program file, with the .exe suffix on Windows."""
    return (bundle / name).is_file() or (bundle / f"{name}.exe").is_file()


def check(bundle: Path) -> list[str]:
    problems: list[str] = []
    internal = bundle / "_internal"
    roots = [internal, bundle]
    for name in FORBIDDEN:
        for root in roots:
            if (root / name).exists() or (root / f"{name}.py").exists():
                problems.append(f"development code in the bundle: {name}")
                break
    for rel in REQUIRED_FILES:
        if not (bundle / rel).is_file():
            problems.append(f"missing from the bundle: {rel}")
    for icon in ICONS:
        if not any((root / icon).is_file() for root in roots):
            problems.append(f"missing from the bundle: {icon}")
    for exe in EXECUTABLES:
        if not has_executable(bundle, exe):
            problems.append(f"missing executable: {exe}")
    if not any(list(root.glob(pattern)) for root in roots for pattern in INTERPRETER_PATTERNS):
        problems.append("the bundle holds no Python of its own")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        print("usage: check_bundle.py <bundle folder>")
        return 2
    problems = check(Path(args[0]))
    for problem in problems:
        print(f"FAILED: {problem}")
    print("Bundle check passed." if not problems else f"{len(problems)} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
