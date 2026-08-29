"""
Canonical nominal ranges for all telemetry fields.

Single source of truth — do NOT redefine or inline these values anywhere else
in the codebase. Always import from this module:

    from anomaly.nominal_ranges import NOMINAL_RANGES

Range tuples are (min_nominal, max_nominal).
"""

NOMINAL_RANGES: dict[str, tuple[float, float]] = {
    "battery_voltage":            (26.0, 32.0),
    "temperature_c":              (10.0, 40.0),
    "signal_strength_db":         (-90.0, -60.0),
    "solar_panel_efficiency_pct": (70.0, 100.0),
    "fuel_level_pct":             (0.0, 100.0),
    "altitude_km":                (400.0, 420.0),
    "velocity_kms":               (7.6, 7.7),
}
