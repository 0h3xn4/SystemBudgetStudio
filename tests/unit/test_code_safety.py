# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""What the program code must never do, found by reading the code (D-263).

The program reads files from strangers. Nothing it reads may become code, a command or a network
call. These tests read every `.py` file under `src/` as a syntax tree and fail on:

- `eval`, `exec`, `compile` (the built-ins), `__import__`, and `importlib` other than `.metadata`;
- `pickle`, `marshal`, `shelve`, `dill`, `cloudpickle`;
- `subprocess`, `os.system`, `os.popen`, `os.exec*`, `os.spawn*`, anything with `shell=True`;
- `socket`, `urllib`, `http`, `ftplib`, `smtplib`, `requests`, `httpx` (the program has no network
  code; the offline test proves it at run time, this test finds it at the source);
- a YAML reader that is not the round-trip reader (`YAML(typ="rt")`), and any use of PyYAML;
- Qt's `QProcess`, `QDesktopServices` and network classes (no program or web page is started from
  project content).

An entry in `ALLOWED` needs a reason. Keep that list short.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {
    "pickle",
    "cPickle",
    "marshal",
    "shelve",
    "dill",
    "cloudpickle",
    "subprocess",
    "socket",
    "socketserver",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "requests",
    "httpx",
    "aiohttp",
    "webbrowser",
    "ctypes",
    "xmlrpc",
}
FORBIDDEN_OS = {"system", "popen", "execv", "execve", "execvp", "execl", "spawnl", "spawnv"}
FORBIDDEN_QT = {"QProcess", "QDesktopServices", "QNetworkAccessManager", "QTcpSocket"}

# (path relative to the repository, name) -> reason
ALLOWED: dict[tuple[str, str], str] = {
    ("src/budget_gui/reports_view.py", "from PySide6.QtGui import QDesktopServices"): (
        "opens the folder the user just wrote reports to in the file manager (a local folder "
        "the user chose; no web address, no program from project content)"
    ),
}


def _files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _findings(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_MODULES:
                    found.append((node.lineno, f"import {alias.name}"))
                if alias.name == "importlib" or (
                    alias.name.startswith("importlib.") and alias.name != "importlib.metadata"
                ):
                    found.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            if top in FORBIDDEN_MODULES:
                found.append((node.lineno, f"from {module} import"))
            if top == "importlib" and module != "importlib.metadata":
                found.append((node.lineno, f"from {module} import"))
            if top == "os":
                for alias in node.names:
                    if alias.name in FORBIDDEN_OS:
                        found.append((node.lineno, f"from os import {alias.name}"))
            if top.startswith("PySide6"):
                for alias in node.names:
                    if alias.name in FORBIDDEN_QT:
                        found.append((node.lineno, f"from {module} import {alias.name}"))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                found.append((node.lineno, f"{func.id}()"))
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
                and func.attr in FORBIDDEN_OS
            ):
                found.append((node.lineno, f"os.{func.attr}()"))
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                found.append((node.lineno, "import_module()"))
            for keyword in node.keywords:
                if (
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    found.append((node.lineno, "shell=True"))
    return found


def test_the_source_tree_is_found() -> None:
    assert len(_files()) > 100


@pytest.mark.parametrize("path", _files(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_dangerous_construct(path: Path) -> None:
    rel = path.relative_to(ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    bad = [(line, what) for line, what in _findings(tree) if (rel, what) not in ALLOWED]
    assert bad == [], f"{rel}: {bad}"


def test_yaml_is_read_with_the_round_trip_reader_only() -> None:
    """`YAML(typ=...)` must be `"rt"` (it builds plain containers and never runs code), and PyYAML
    must not be used at all."""
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                a.name.split(".")[0] == "yaml" for a in node.names
            ):
                pytest.fail(f"{rel}:{node.lineno} imports PyYAML")
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "yaml":
                pytest.fail(f"{rel}:{node.lineno} imports PyYAML")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "YAML"
            ):
                kinds = [
                    k.value.value
                    for k in node.keywords
                    if k.arg == "typ" and isinstance(k.value, ast.Constant)
                ]
                assert kinds == ["rt"], f"{rel}:{node.lineno} YAML() without typ='rt'"


def test_xml_is_parsed_with_defusedxml_only() -> None:
    """The standard library XML parsers are open to entity attacks; only types may be imported."""
    parsers = {"parse", "fromstring", "XML", "iterparse", "XMLParser", "XMLPullParser"}
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in {"xml.dom", "xml.dom.minidom", "xml.sax", "xml.parsers.expat"}:
                    pytest.fail(f"{rel}:{node.lineno} imports {module}")
                if module == "xml.etree.ElementTree" and any(a.name in parsers for a in node.names):
                    pytest.fail(
                        f"{rel}:{node.lineno} imports an XML parser from the standard library"
                    )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {
                        "xml.dom.minidom",
                        "xml.sax",
                        "xml.parsers.expat",
                        "lxml.etree",
                    }:
                        pytest.fail(f"{rel}:{node.lineno} imports {alias.name}")
            if (
                isinstance(node, ast.Attribute)
                and node.attr in parsers
                and isinstance(node.value, ast.Name)
                and node.value.id == "ET"
            ):
                pytest.fail(f"{rel}:{node.lineno} calls ET.{node.attr} (use defusedxml)")
