"""Current schema version of every file kind. Bump with a migration (see io/migrations.py)."""

CURRENT_VERSIONS: dict[str, int] = {
    "project": 2,
    "spacecraft": 2,
    "unit": 3,
    "expendable": 2,
    "orbit": 2,
    "ground_station": 2,
    "target": 2,
    "scenario": 3,
    "link": 2,
    "spacecraft_mode": 2,
    "margin_policy": 3,
    "power_config": 2,
    "power_system": 2,
    "thermal_model": 2,
    "thermal_environment": 2,
    "mass_limits": 2,
    "ebn0_table": 2,
    "attenuation_table": 2,
}
