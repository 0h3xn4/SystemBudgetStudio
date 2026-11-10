# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""The user of a report: never the login name of the operating system (D-262)."""

from __future__ import annotations

import getpass

import pytest

from budget_core import provenance


@pytest.fixture(autouse=True)
def clean(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("BUDGET_USER", raising=False)
    provenance.set_default_user("")
    yield
    provenance.set_default_user("")


def test_the_default_is_unknown_and_the_account_is_never_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: object, **_k: object) -> str:
        raise AssertionError("the operating-system account must not be read")

    monkeypatch.setattr(getpass, "getuser", boom)
    monkeypatch.setattr("os.getlogin", boom)
    assert provenance.resolve_user() == "unknown"


def test_the_order_is_argument_environment_setting_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance.set_default_user("From settings")
    assert provenance.resolve_user() == "From settings"
    monkeypatch.setenv("BUDGET_USER", "From env")
    assert provenance.resolve_user() == "From env"
    assert provenance.resolve_user("From argument") == "From argument"


def test_a_name_is_cleaned_and_limited() -> None:
    provenance.set_default_user("  A. Engineer\x00\n\t ")
    assert provenance.default_user() == "A. Engineer"
    provenance.set_default_user("x" * 200)
    assert len(provenance.default_user()) == 64
    provenance.set_default_user("")
    assert provenance.resolve_user() == "unknown"
