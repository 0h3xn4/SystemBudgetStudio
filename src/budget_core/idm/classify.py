"""Which equipment of an IDM-CIC model is a battery, a solar array, a wheel, a thruster... (D-254).

The model has no field for the kind of an equipment; it has the name (free text, English or French
in the models seen) and the subsystem it belongs to (Power, AOCS, Propulsion, Communications...).
A kind is proposed when the name contains one of its words (accents and case ignored) and the name
has none of the words of a structural part (a support, a bracket, a cleat...), so that
`Wheel_Support_A_pyramide_configuration` is not a wheel. The proposal is `high` when the subsystem
is the usual one for the kind and `medium` when only the name says so. The subsystem alone proposes
nothing. A proposal is a proposal: it is shown with its reason, nothing is written from it unless
the component library or the rules of D-254 say how, and the user's own library can name a kind for
an equipment the words do not catch (`idm/components.yaml`).

Pure functions: no file is read here.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

BATTERY = "battery"
SOLAR_ARRAY = "solar_array"
REACTION_WHEEL = "reaction_wheel"
MAGNETORQUER = "magnetorquer"
STAR_TRACKER = "star_tracker"
SUN_SENSOR = "sun_sensor"
GYRO = "gyroscope"
MAGNETOMETER = "magnetometer"
GNSS = "gnss_receiver"
THRUSTER = "thruster"
TANK = "tank"
ANTENNA = "antenna"
TRANSCEIVER = "transceiver"

KINDS = (
    BATTERY,
    SOLAR_ARRAY,
    REACTION_WHEEL,
    MAGNETORQUER,
    STAR_TRACKER,
    SUN_SENSOR,
    GYRO,
    MAGNETOMETER,
    ANTENNA,  # before the receivers: a GPS antenna is an antenna
    GNSS,
    THRUSTER,
    TANK,
    TRANSCEIVER,
)
KIND_TITLES = {
    BATTERY: "battery",
    SOLAR_ARRAY: "solar array",
    REACTION_WHEEL: "reaction wheel",
    MAGNETORQUER: "magnetorquer",
    STAR_TRACKER: "star tracker",
    SUN_SENSOR: "sun sensor",
    GYRO: "gyroscope",
    MAGNETOMETER: "magnetometer",
    GNSS: "GNSS receiver",
    THRUSTER: "thruster",
    TANK: "propellant tank",
    ANTENNA: "antenna",
    TRANSCEIVER: "transmitter or receiver",
}

# the words of the name that make a kind (matched on whole words or word starts, accents removed)
_WORDS: dict[str, tuple[str, ...]] = {
    BATTERY: ("battery", "batterie", "accumulat", "li-ion", "lithium"),
    SOLAR_ARRAY: ("solar", "solaire", "photovolt", "sadm"),
    REACTION_WHEEL: (
        "reaction wheel",
        "inertia wheel",
        "roue a reaction",
        "roue d'inertie",
        "momentum wheel",
    ),
    MAGNETORQUER: ("magnetorquer", "magneto-torquer", "magnetocoupleur", "magneto-coupleur", "mtq"),
    STAR_TRACKER: (
        "star tracker",
        "star-tracker",
        "startracker",
        "viseur d'etoile",
        "tracker stellaire",
    ),
    SUN_SENSOR: ("sun sensor", "sun-sensor", "capteur solaire", "css", "dss"),
    GYRO: ("gyro", "imu", "inertial measurement"),
    MAGNETOMETER: ("magnetometer", "magnetometre"),
    GNSS: ("gnss", "gps", "navigation receiver"),
    THRUSTER: ("thruster", "propulseur", "micro-propulseur", "ion engine", "hall effect"),
    TANK: ("tank", "reservoir"),
    ANTENNA: ("antenna", "antenne"),
    TRANSCEIVER: (
        "transmitter",
        "transceiver",
        "receiver",
        "emetteur",
        "recepteur",
        "transpondeur",
        "transponder",
    ),
}
# a lone word that is only a kind in the subsystem that goes with it (a wheel in AOCS)
_SUBSYSTEM_WORDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    REACTION_WHEEL: (("wheel", "roue"), ("aocs", "aoc", "adcs", "gnc", "acs", "attitude")),
    BATTERY: (("pack", "cells"), ("power", "pwr", "eps", "electrical power")),
    SOLAR_ARRAY: (("array", "wing", "panel", "panneau", "generator"), ("power", "pwr", "eps")),
    THRUSTER: (("engine", "moteur", "nozzle"), ("propulsion", "pro", "prop", "rcs")),
}
# the subsystems in which a kind is at home (a match with the name makes the proposal `high`)
_HOME: dict[str, tuple[str, ...]] = {
    BATTERY: ("power", "pwr", "eps"),
    SOLAR_ARRAY: ("power", "pwr", "eps"),
    REACTION_WHEEL: ("aocs", "aoc", "adcs", "gnc", "acs", "attitude"),
    MAGNETORQUER: ("aocs", "aoc", "adcs", "gnc", "acs", "attitude"),
    STAR_TRACKER: ("aocs", "aoc", "adcs", "gnc", "acs", "attitude"),
    SUN_SENSOR: ("aocs", "aoc", "adcs", "gnc", "acs", "attitude"),
    GYRO: ("aocs", "aoc", "adcs", "gnc", "acs", "attitude"),
    MAGNETOMETER: ("aocs", "aoc", "adcs", "gnc", "acs", "attitude"),
    GNSS: ("aocs", "aoc", "adcs", "gnc", "navigation"),
    THRUSTER: ("propulsion", "pro", "prop", "rcs"),
    TANK: ("propulsion", "pro", "prop", "rcs"),
    ANTENNA: ("communication", "com", "ttc", "tmtc", "rf", "band"),
    TRANSCEIVER: ("communication", "com", "ttc", "tmtc", "rf", "band"),
}
# words of a part that holds, covers or connects something: never a battery, a wheel...
_STRUCTURAL = (
    "support",
    "bracket",
    "cleat",
    "equerre",
    "corniere",
    "angle iron",
    "screw",
    "visserie",
    "baffle",
    "bipod",
    "bipode",
    "mount",
    "interface",
    "adapter",
    "harness",
    "faisceau",
    "harnais",
    "plateau",
    "frame",
    "bati",
)

HIGH, MEDIUM = "high", "medium"


@dataclass(frozen=True)
class Detection:
    """One proposal: this equipment looks like this kind of component."""

    kind: str
    confidence: str  # "high" or "medium"
    reason: str  # in words, from the name and the subsystem only


def fold(text: str) -> str:
    """Lower case, accents removed, separators between words turned into spaces (except `-`)."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"[_\s]+", " ", plain).strip()


def _has_word(text: str, word: str) -> bool:
    """`word` appears in `text` as a word or at the start of one (`accumulat` finds `accumulator`),
    not inside another word (`css` is not found in `process`)."""
    return re.search(r"(?<![a-z0-9])" + re.escape(word), text) is not None


def _at_home(kind: str, subsystem: str) -> bool:
    return any(h in subsystem for h in _HOME.get(kind, ()))


def classify(equipment_name: str, subsystem_name: str, subsystem_id: str = "") -> Detection | None:
    """The kind this equipment looks like, or None. Names are matched as written, accents and case
    ignored; the first kind (in the order of `KINDS`) whose words the name has wins."""
    name = fold(equipment_name)
    subsystem = fold(f"{subsystem_name} {subsystem_id}")
    if not name or any(_has_word(name, w) for w in _STRUCTURAL):
        return None
    for kind in KINDS:
        hit = next((w for w in _WORDS[kind] if _has_word(name, w)), None)
        if hit is not None:
            home = _at_home(kind, subsystem)
            reason = f'the name has "{hit}"' + ("; the subsystem is the usual one" if home else "")
            return Detection(kind, HIGH if home else MEDIUM, reason)
        words, homes = _SUBSYSTEM_WORDS.get(kind, ((), ()))
        weak = next((w for w in words if _has_word(name, w)), None)
        if weak is not None and any(h in subsystem for h in homes):
            return Detection(
                kind,
                MEDIUM,
                f'the name has "{weak}", in the subsystem that goes with it',
            )
    return None
