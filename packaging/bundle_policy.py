#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The licence and Qt policy of the installers (standard library only).

The rules are in `bundle_policy.toml`. This module reads them and answers three questions:
is a licence expression acceptable (`licence_verdict`), is a Qt library or plugin to be kept
(`qt_library_wanted`, `qt_plugin_wanted`), and what SPDX expression does a package manager's
licence field mean (`normalise_licence`).
"""

from __future__ import annotations

import fnmatch
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

POLICY_FILE = Path(__file__).with_name("bundle_policy.toml")


def load(path: Path = POLICY_FILE) -> dict[str, dict]:  # type: ignore[type-arg]
    return tomllib.loads(path.read_text(encoding="utf-8"))


POLICY = load()


# ---- SPDX expressions ------------------------------------------------------------------------
_TOKEN = re.compile(r"\(|\)|[^\s()]+")


@dataclass
class Verdict:
    ok: bool
    reason: str


def _atom_ok(identifier: str, exception: str | None, policy: dict) -> tuple[bool, str]:  # type: ignore[type-arg]
    lic = policy["licences"]
    plus = identifier.removesuffix("+")
    for pattern in lic["deny_patterns"]:
        if re.search(pattern, identifier):
            if exception is not None and exception in lic["gpl_exceptions_allowed"]:
                return True, f"{identifier} WITH {exception}"
            return False, f"{identifier} is on the deny list"
    if identifier in lic["allow"] or plus in lic["allow"]:
        return True, identifier
    return False, f"{identifier} is not on the allow list"


class _Parser:
    def __init__(self, tokens: list[str], policy: dict) -> None:  # type: ignore[type-arg]
        self.tokens, self.pos, self.policy = tokens, 0, policy

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def expr(self) -> tuple[bool, str]:  # OR
        ok, why = self.term()
        while self.peek() == "OR":
            self.take()
            ok2, why2 = self.term()
            if ok2 and not ok:
                why = why2
            ok = ok or ok2
            if not ok:
                why = f"{why}; {why2}"
        return ok, why

    def term(self) -> tuple[bool, str]:  # AND
        ok, why = self.factor()
        while self.peek() == "AND":
            self.take()
            ok2, why2 = self.factor()
            if ok and not ok2:
                why = why2
            ok = ok and ok2
        return ok, why

    def factor(self) -> tuple[bool, str]:
        token = self.take()
        if token == "(":
            ok, why = self.expr()
            if self.peek() == ")":
                self.take()
            return ok, why
        exception = None
        if self.peek() == "WITH":
            self.take()
            exception = self.take()
        return _atom_ok(token, exception, self.policy)


def licence_verdict(expression: str, policy: dict | None = None) -> Verdict:  # type: ignore[type-arg]
    """Is the SPDX expression acceptable under the policy? An empty or unknown one is not."""
    policy = policy or POLICY
    text = (expression or "").strip()
    if not text:
        return Verdict(False, "no licence given")
    tokens = _TOKEN.findall(text)
    try:
        parser = _Parser(tokens, policy)
        ok, why = parser.expr()
        if parser.pos != len(tokens):
            return Verdict(False, f"cannot read the licence expression: {text}")
    except IndexError:
        return Verdict(False, f"cannot read the licence expression: {text}")
    return Verdict(ok, why)


def normalise_licence(field: str, policy: dict | None = None) -> str:
    """An SPDX expression for the licence field of a package manager.

    Whole-field aliases are tried first ("GPLv3+ with exceptions"); then each name between
    "and" / "or" and parentheses. A name that is not known becomes "UNKNOWN-<name>", which no
    policy accepts."""
    policy = policy or POLICY
    aliases = policy["licences"]["aliases"]
    text = field.strip()
    if text in aliases:
        return str(aliases[text])
    spdx_like = re.fullmatch(r"[A-Za-z0-9.+\- ()]*(AND|OR|WITH)[A-Za-z0-9.+\- ()]*", text)
    if spdx_like and " and " not in text and " or " not in text:
        return text
    out: list[str] = []
    for part in re.split(r"(\(|\)|\s+and\s+|\s+or\s+)", text, flags=re.IGNORECASE):
        low = part.strip().lower()
        if not part.strip():
            continue
        if low == "and":
            out.append("AND")
        elif low == "or":
            out.append("OR")
        elif part.strip() in ("(", ")"):
            out.append(part.strip())
        else:
            name = part.strip()
            out.append(str(aliases.get(name, name if _looks_spdx(name) else f"UNKNOWN-{name}")))
    return " ".join(out)


def _looks_spdx(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9.+-]+(-[0-9.]+)?(-only|-or-later)?", name)) and (
        "-" in name or name in ("MIT", "ISC", "Zlib", "FTL", "IJG", "HPND", "curl", "ICU")
    )


# ---- Qt -------------------------------------------------------------------------------------
def _qt_stem(name: str) -> str | None:
    """'Qt6Core' for libQt6Core.so.6 or Qt6Core.dll or Qt6Core.framework; None for other names."""
    match = re.match(r"^(?:lib)?(Qt6[A-Za-z0-9]+)(?:\.so.*|\.dll|\.dylib|\.\d.*)?$", name)
    return match.group(1) if match else None


def qt_library_wanted(name: str, policy: dict | None = None) -> bool:
    """False for a Qt library the program does not use (and always for a GPL-only module)."""
    policy = policy or POLICY
    stem = _qt_stem(name)
    return stem is not None and stem in policy["qt"]["keep_libraries"]


def is_qt_library(name: str) -> bool:
    return _qt_stem(name) is not None


def is_gpl_only_qt(name: str, policy: dict | None = None) -> bool:
    policy = policy or POLICY
    return _qt_stem(name) in policy["qt"]["gpl_only_modules"]


def qt_plugin_wanted(relative: str, policy: dict | None = None) -> bool:
    """`relative` is the path below the Qt plugin folder, with forward slashes."""
    policy = policy or POLICY
    rel = relative.replace("\\", "/").lstrip("/")
    return not any(fnmatch.fnmatch(rel, pattern) for pattern in policy["qt"]["deny_plugins"])


def qt_data_wanted(relative: str, policy: dict | None = None) -> bool:
    policy = policy or POLICY
    parts = relative.replace("\\", "/").split("/")
    return not any(part in policy["qt"]["deny_data"] for part in parts)


def keep_python_module(name: str, policy: dict | None = None) -> bool:
    """False for a PySide6 extension module (QtSvg.abi3.so, QtDBus.pyd...) that is not imported."""
    policy = policy or POLICY
    match = re.match(r"^(Qt[A-Za-z0-9]+)\.(?:abi3|cpython-[^.]+|cp\d+[^.]*)?\.?(?:so|pyd)$", name)
    return match is None or match.group(1) in policy["qt"]["keep_python_modules"]


def keep_entry(dest: str, policy: dict | None = None) -> bool:
    """For the PyInstaller spec: keep the file at `dest` (its path inside the bundle)?"""
    policy = policy or POLICY
    path = dest.replace("\\", "/")
    base = path.rsplit("/", 1)[-1]
    if "/plugins/" in f"/{path}" and "PySide6/" in path:
        return qt_plugin_wanted(path.split("plugins/", 1)[1], policy)
    if is_gpl_only_qt(base, policy):
        return False
    if is_qt_library(base):
        return qt_library_wanted(base, policy)
    if "PySide6/" in path and "translations" in path.split("/"):
        return qt_data_wanted(path, policy)
    if path.startswith("PySide6/") and path.count("/") == 1:
        return keep_python_module(base, policy)
    return True
