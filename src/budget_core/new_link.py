"""A new RF link from a few answers (D-199): what the window's *Add link* turns into a link file.

Only the structure of a link is asked for: the direction, the ground station at the other end, the
frequency, the modulation, the coding and the data rates. Every number that comes from a data
sheet, a policy or a standard (transmit power, line loss, antenna gain, G/T, the required margin
and the pointing, polarisation and implementation losses) is written as a placeholder
(`source: TBD`) and filled in the inputs grid with its source; until then the results that need it
are n/a and the Problems panel lists each one. The frequency is asked in MHz and stored in hertz.
The modulation and coding must be a pair of `config/ebn0_table.yaml` when that table has entries
(the loader refuses a link whose pair is not listed, `REF_UNKNOWN_MODULATION`); with an empty table
(a blank project) any text is accepted. The id is the file name `links/<id>.yaml`.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import ValidationError

from budget_core.io.project_loader import model_to_data
from budget_core.model import Antenna, Link, Receiver, Sourced, Transmitter
from budget_core.new_unit import ID_PATTERN, MAX_ID, MAX_TEXT, id_from_name
from budget_core.reports.files import same_name_key
from budget_core.wizard import Issue

__all__ = [
    "DIRECTIONS",
    "FREQUENCY_RANGE_MHZ",
    "LinkAnswers",
    "check_link",
    "id_from_name",
    "link_data",
]

DIRECTIONS = ("downlink", "uplink")
# a sanity range, not a standard: it catches a frequency typed in hertz in a megahertz field
FREQUENCY_RANGE_MHZ = (1.0, 1.0e6)


@dataclass(frozen=True)
class LinkAnswers:
    link_id: str
    name: str
    direction: str  # "downlink" or "uplink"
    peer: str  # the id of the ground station at the other end
    frequency_mhz: float | None
    modulation: str
    coding: str
    data_rates_bps: Sequence[float]  # NaN stands for an entry that is not a number


def _number(value: float | None) -> bool:
    return value is not None and not isinstance(value, bool) and math.isfinite(value)


def check_link(
    answers: LinkAnswers,
    *,
    existing_ids: Collection[str],
    ground_station_ids: Collection[str],
    ebn0_pairs: Collection[tuple[str, str]] = (),
) -> list[Issue]:
    """What is wrong with the answers, in words, by field (the first issue is the one to show)."""
    issues: list[Issue] = []
    link_id = answers.link_id.strip()
    if not link_id:
        issues.append(Issue("link_id", "Give the link an id, for example uhf_down."))
    elif len(link_id) > MAX_ID or not ID_PATTERN.fullmatch(link_id):
        issues.append(
            Issue(
                "link_id",
                "The id is the file name: use letters, digits, _ and -, starting with a letter "
                f"or digit, at most {MAX_ID} characters.",
            )
        )
    elif same_name_key(link_id) in {same_name_key(known) for known in existing_ids}:
        issues.append(
            Issue("link_id", "A link with this id (or one that differs only in capitals) exists.")
        )
    if not answers.name.strip():
        issues.append(Issue("name", "Give the link a name."))
    elif len(answers.name.strip()) > MAX_TEXT:
        issues.append(Issue("name", f"The name can have at most {MAX_TEXT} characters."))
    if answers.direction not in DIRECTIONS:
        issues.append(Issue("direction", "Choose downlink or uplink."))
    if answers.peer not in set(ground_station_ids):
        issues.append(Issue("peer", "Choose the ground station at the other end of the link."))
    low, high = FREQUENCY_RANGE_MHZ
    frequency = answers.frequency_mhz
    if not _number(frequency):
        issues.append(Issue("frequency_mhz", "Give the frequency in megahertz."))
    elif frequency is not None and not low <= frequency <= high:
        issues.append(
            Issue(
                "frequency_mhz",
                f"The frequency is in megahertz, between {low:g} and {high:g} MHz "
                "(2200 MHz is 2.2 GHz).",
            )
        )
    for field, label, text in (
        ("modulation", "modulation, for example QPSK", answers.modulation),
        ("coding", "coding, for example rate 1/2", answers.coding),
    ):
        if not text.strip():
            issues.append(Issue(field, f"Give the {label}."))
        elif len(text.strip()) > MAX_TEXT:
            issues.append(Issue(field, f"The {field} can have at most {MAX_TEXT} characters."))
    pair = (answers.modulation.strip(), answers.coding.strip())
    if ebn0_pairs and all(pair) and pair not in set(ebn0_pairs):
        issues.append(
            Issue(
                "modulation",
                "This modulation and coding are not in config/ebn0_table.yaml: choose a pair of "
                "the table (or add the pair there first).",
            )
        )
    rates = list(answers.data_rates_bps)
    if not rates:
        issues.append(Issue("data_rates_bps", "Give at least one data rate in bits per second."))
    elif any(not _number(rate) or rate <= 0.0 for rate in rates):
        issues.append(
            Issue("data_rates_bps", "Every data rate must be a number above 0 (bits per second).")
        )
    return issues


def _placeholder() -> Sourced:
    return Sourced(value=None, source="TBD", note="Placeholder: supply the project's value.")


def link_data(answers: LinkAnswers) -> dict[str, Any]:
    """The plain data of the link file. The answers must have passed `check_link`; the model is
    the last check (a ValueError says the answers do not make a valid link)."""
    assert answers.frequency_mhz is not None
    try:
        link = Link(
            name=answers.name.strip(),
            direction=cast(Literal["downlink", "uplink"], answers.direction),
            peer=answers.peer,
            frequency_hz=answers.frequency_mhz * 1.0e6,
            transmitter=Transmitter(
                power_w=_placeholder(),
                line_loss_db=_placeholder(),
                antenna=Antenna(gain_dbi=_placeholder()),
            ),
            receiver=Receiver(g_over_t_dbk=_placeholder()),
            modulation=answers.modulation.strip(),
            coding=answers.coding.strip(),
            data_rates_bps=[float(rate) for rate in answers.data_rates_bps],
            required_margin_db=_placeholder(),
            pointing_loss_db=_placeholder(),
            polarisation_loss_db=_placeholder(),
            implementation_loss_db=_placeholder(),
        )
    except ValidationError as exc:
        raise ValueError("the answers do not make a valid link") from exc
    return model_to_data(link)
