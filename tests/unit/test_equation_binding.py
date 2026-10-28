"""D-206: which registered equations are claimed by the code that applies them.

The list of equations nobody claims yet is written down here. It only gets shorter: binding an
equation (`@computes`) removes it from the list, and the test fails until the list is updated, so
the progress is visible; an equation can never become unbound unnoticed either.
"""

from __future__ import annotations

import budget_core.link.evaluate  # noqa: F401
import budget_core.mass.static_mass  # noqa: F401
import budget_core.power.static_budget  # noqa: F401
import budget_core.power.time_domain  # noqa: F401
import budget_core.thermal.static_thermal  # noqa: F401
from budget_core.equation_binding import BOUND
from budget_core.equations import EQUATIONS

NOT_YET_BOUND = frozenset(
    {
        "ENV-GEODETIC",
        "ENV-GMST",
        "ENV-SHADOW-CON",
        "ENV-SHADOW-CYL",
        "ENV-SUN",
        "ENV-TOPO",
        "LNK-VOLUME",
        "TDP-AGE",
        "TDP-ARRAY",
        "TDP-BALANCE",
        "TDP-CAP",
        "TDP-COS",
        "TDP-DEMAND",
        "TDP-DOD",
        "TDP-LIT",
        "TDP-PEAK",
        "TDP-SOC",
        "TDP-TEMP",
    }
)


def test_the_equations_nobody_claims_are_the_listed_ones() -> None:
    unbound = frozenset(set(EQUATIONS) - set(BOUND))
    assert unbound == NOT_YET_BOUND, (
        "bound now: " + ", ".join(sorted(NOT_YET_BOUND - unbound)),
        "unbound now: " + ", ".join(sorted(unbound - NOT_YET_BOUND)),
    )


def test_no_code_claims_an_equation_the_registry_does_not_have() -> None:
    assert set(BOUND) <= set(EQUATIONS)
