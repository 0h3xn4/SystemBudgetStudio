# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""Equations whose source was checked against the published text, and an independent check of each.

A source is set only after the formula was compared with the text it names (D-270); the others
stay SOURCE_MISSING. Each test recomputes the relation from the cited text, not from the code.
"""

from __future__ import annotations

import math

import pytest

from budget_core.equations import EQUATIONS
from budget_core.link.budget import eirp_dbw, free_space_path_loss_db

CHECKED = {
    "LNK-FSPL": "ITU-R P.525-5",
    "LNK-EIRP": "ITU RR No. 1.161",
}


@pytest.mark.parametrize(("equation_id", "cited"), sorted(CHECKED.items()))
def test_the_checked_sources_name_the_text(equation_id: str, cited: str) -> None:
    source = EQUATIONS[equation_id].source
    assert source is not None and cited in source


@pytest.mark.parametrize(
    ("freq_mhz", "distance_km"), [(2245.0, 1000.0), (8200.0, 2500.0), (437.0, 600.0)]
)
def test_free_space_loss_agrees_with_itu_r_p525_equation_6(
    freq_mhz: float, distance_km: float
) -> None:
    # P.525-5, Annex, 2.3, equation (6): Lbf = 32.4 + 20 log10 f + 20 log10 d (f in MHz, d in km).
    # The constant is rounded to one decimal in the text (20 log10(4 pi 1e9 / c) = 32.45).
    itu = 32.4 + 20.0 * math.log10(freq_mhz) + 20.0 * math.log10(distance_km)
    ours = float(free_space_path_loss_db(distance_km * 1e3, freq_mhz * 1e6))
    assert ours == pytest.approx(itu, abs=0.05)


def test_eirp_is_the_power_supplied_to_the_antenna_times_its_gain() -> None:
    # RR No. 1.161: e.i.r.p. = power supplied to the antenna x isotropic gain. 10 W through a line
    # of 1 dB into a 6 dBi antenna: 10 W x 10^(-0.1) x 10^(0.6) in watts.
    expected_w = 10.0 * 10 ** (-1.0 / 10) * 10 ** (6.0 / 10)
    assert eirp_dbw(10.0, 1.0, 6.0) == pytest.approx(10 * math.log10(expected_w), abs=1e-12)
