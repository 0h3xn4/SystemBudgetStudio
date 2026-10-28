"""Audit MI-14: unit labels round-trip, no pint exceptions escape, clean degC, no delta units for
absolute temperatures, ASCII digits only, one rule for capitals."""

from __future__ import annotations

import contextlib

import pytest

from budget_core.units import quantity
from budget_core.units.quantity import UnitError, canonical_unit, format_quantity, parse_quantity

FIELD_FOR_KEY = {key: f"x_{key}" for key in quantity._SUFFIXES}


@pytest.mark.parametrize("key", sorted(quantity._SUFFIXES))
def test_every_canonical_label_can_be_read_back(key: str) -> None:
    field = FIELD_FOR_KEY[key]
    text = format_quantity(3.5, field)
    assert parse_quantity(text, field) == pytest.approx(3.5)


@pytest.mark.parametrize(
    ("text", "field", "expected"),
    [
        ("2.5 W/m2", "solar_irradiance_wm2", 2.5),
        ("2.5 W/m^2", "solar_irradiance_wm2", 2.5),
        ("4 cm2", "cell_area_m2", 4e-4),
        ("1.5 kg m2", "ixx_kgm2", 1.5),
        ("1.5 kg m^2", "ixx_kgm2", 1.5),
        ("1 g m2", "ixx_kgm2", 1e-3),
    ],
)
def test_squared_units_may_be_written_with_or_without_a_caret(
    text: str, field: str, expected: float
) -> None:
    assert parse_quantity(text, field) == pytest.approx(expected)


@pytest.mark.parametrize(
    "token", ["dB%", "%", "dB/%", "degC/degC", "dBm/Hz", "deg%", "W%", "dB dB", "%%", "dBHz"]
)
@pytest.mark.parametrize(
    "field", ["elevation_deg", "x_k", "freq_hz", "power_w", "gain_dbi", "loss_db", "ratio_ratio"]
)
def test_odd_unit_tokens_give_a_unit_error_and_nothing_else(token: str, field: str) -> None:
    with contextlib.suppress(UnitError):
        parse_quantity(f"2.5 {token}", field)


def test_celsius_conversion_is_clean() -> None:
    assert parse_quantity("-40 degC", "space_temp_k") == 233.15
    assert parse_quantity("0 degC", "space_temp_k") == 273.15
    assert parse_quantity("25 degC", "space_temp_k") == 298.15
    assert parse_quantity("2.2 GHz", "freq_hz") == 2.2e9


@pytest.mark.parametrize("text", ["5 delta_degC", "5 delta_degF", "5 Δ°C", "5 kelvin delta_degC"])
def test_a_temperature_difference_is_not_an_absolute_temperature(text: str) -> None:
    with pytest.raises(UnitError):
        parse_quantity(text, "space_temp_k")


def test_a_margin_takes_differences_and_refuses_celsius_readings() -> None:
    assert parse_quantity("5 delta_degC", "temperature_margin_k") == pytest.approx(5.0)
    assert parse_quantity("9 delta_degF", "temperature_margin_k") == pytest.approx(5.0)
    assert parse_quantity("5 K", "temperature_margin_k") == pytest.approx(5.0)
    with pytest.raises(UnitError, match="difference"):
        parse_quantity("5 degC", "temperature_margin_k")


@pytest.mark.parametrize("text", ["٣ W", "1٢ W", "１ W", "1.٥ W", "1e٢ W", "١ ٢"])
def test_only_ascii_digits_are_numbers(text: str) -> None:
    with pytest.raises(UnitError):
        parse_quantity(text, "power_w")


@pytest.mark.parametrize("text", ["-3 DBI", "-3 dbi", "3 DBi", "3 Dbi"])
def test_log_units_need_their_exact_capitals(text: str) -> None:
    with pytest.raises(UnitError):
        parse_quantity(text, "gain_dbi")


def test_log_units_with_their_exact_capitals_still_work() -> None:
    assert parse_quantity("3 dBi", "gain_dbi") == 3.0
    assert parse_quantity("30 dBm", "tx_power_dbw") == 0.0
    assert parse_quantity("0 dBW", "tx_power_dbm") == 30.0
    assert parse_quantity("-2 dB/K", "g_over_t_dbk") == -2.0
    assert parse_quantity("-2 dBK", "g_over_t_dbk") == -2.0


def test_a_wrong_capital_is_explained_without_echoing_the_input() -> None:
    with pytest.raises(UnitError) as info:
        parse_quantity("3 DBIsecret", "gain_dbi")
    assert "secret" not in str(info.value).lower()
    with pytest.raises(UnitError) as info:
        parse_quantity("3 dbi", "gain_dbi")
    assert "capital" in str(info.value)


def test_hint_example_is_valid_for_each_field() -> None:
    from budget_core.io.errors import _unit_hint

    for key in quantity._SUFFIXES:
        if key == "ratio":
            continue
        field = FIELD_FOR_KEY[key]
        unit = canonical_unit(field)
        assert unit and f"'2.5 {unit}'" in _unit_hint(field)
        parse_quantity(f"2.5 {unit}", field)


@pytest.mark.parametrize("word", ["ton", "tons", "Ton"])
def test_the_ambiguous_word_ton_is_refused_and_the_message_names_the_alternatives(
    word: str,
) -> None:
    """pint reads 'ton' as the US short ton (907 kg); it is refused (docs/changes.md)."""
    with pytest.raises(UnitError) as info:
        parse_quantity(f"5 {word}", "mass_kg")
    message = str(info.value)
    assert "ambiguous" in message and "'t'" in message and "lb" in message
    assert "5" not in message  # the message never carries the value read from the file


def test_the_unambiguous_mass_units_still_parse() -> None:
    assert parse_quantity("1 t", "mass_kg") == 1000.0
    assert parse_quantity("1 tonne", "mass_kg") == 1000.0
    assert parse_quantity("1 lb", "mass_kg") == pytest.approx(0.45359237)
