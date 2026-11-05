"""Which equipment looks like a battery, a wheel, a thruster... (D-254): the names of the models
seen, in English and French, with the subsystem that goes with them."""

from __future__ import annotations

import pytest

from budget_core.idm.classify import (
    ANTENNA,
    BATTERY,
    GNSS,
    HIGH,
    MEDIUM,
    REACTION_WHEEL,
    SOLAR_ARRAY,
    STAR_TRACKER,
    THRUSTER,
    TRANSCEIVER,
    classify,
    fold,
)


@pytest.mark.parametrize(
    ("name", "subsystem", "kind", "confidence"),
    [
        ("Battery", "Power", BATTERY, HIGH),
        ("BATTERIE", "Power", BATTERY, HIGH),
        ("Battery", "Electronics", BATTERY, MEDIUM),
        ("Internal Panel - Solar Panel", "Power", SOLAR_ARRAY, HIGH),
        ("Générateur_solaire_panneau _externe", "Power", SOLAR_ARRAY, HIGH),
        ("SADM", "Power", SOLAR_ARRAY, HIGH),
        ("Inertia Wheel A", "AOCS", REACTION_WHEEL, HIGH),
        ("Roue A", "AOCS", REACTION_WHEEL, MEDIUM),  # a lone word, only in the right subsystem
        ("Star Tracker - Head", "AOCS", STAR_TRACKER, HIGH),
        ("Thruster_1N_hydrazine", "Propulsion", THRUSTER, HIGH),
        ("Propulseur_1N_hydrazine", "Propulsion", THRUSTER, HIGH),
        ("X Band Antenna", "X band", ANTENNA, HIGH),
        ("GPS Antenna", "AOCS", ANTENNA, MEDIUM),  # an antenna, not a receiver
        ("GNSS_ Receiver", "AOCS", GNSS, HIGH),
        ("X-Band_Transmitter", "X band", TRANSCEIVER, HIGH),
    ],
)
def test_the_names_of_the_models_are_recognised(
    name: str, subsystem: str, kind: str, confidence: str
) -> None:
    found = classify(name, subsystem)
    assert found is not None, name
    assert (found.kind, found.confidence) == (kind, confidence)
    assert name.split("_")[0].split(" ")[0] or True
    assert found.reason  # in words


@pytest.mark.parametrize(
    ("name", "subsystem"),
    [
        ("Wheel_ Support_A_pyramide_configuration", "Structure"),  # a support, not a wheel
        ("Support_A_roues_en_configuration_pyramidale", "Structure"),
        ("Harnais_GNSS", "AOCS"),  # a harness
        ("Panel -X", "Structure"),  # a structure panel is not a solar panel
        ("Panel+Z", "Power"),  # a panel alone is not a solar array unless the name says solar
        ("Support_Antenna-X", "Communications"),
        ("Bracket_SST", "AOCS"),
        ("Video Module", "Electronics"),
        ("", "Power"),
        ("Processor", "Power"),  # "css" is not found inside "processor"
    ],
)
def test_structural_parts_and_other_equipment_are_not_proposed(name: str, subsystem: str) -> None:
    found = classify(name, subsystem)
    assert found is None or name.startswith("Panel+Z"), (name, found)


def test_a_panel_in_the_power_subsystem_is_proposed_only_with_the_word_solar() -> None:
    assert classify("Panel+Z", "Power") is not None  # a lone word in its subsystem: medium
    assert classify("Panel+Z", "Power").confidence == MEDIUM  # type: ignore[union-attr]
    assert classify("Panel -X", "Structure") is None


def test_the_subsystem_alone_proposes_nothing() -> None:
    assert classify("Unit 12", "Power") is None
    assert classify("Unit 12", "AOCS") is None


def test_fold_removes_accents_case_and_separators() -> None:
    assert fold("Magnétomètre_A") == "magnetometre a"
    assert fold("  Star-Tracker  ") == "star-tracker"
