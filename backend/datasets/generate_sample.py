"""
Generate simulated satellite telemetry CSVs with known injected anomalies.

Run from the backend/ directory:
    python -m datasets.generate_sample

Two files are produced:
    datasets/sample_mission.csv       — primary dataset, 3 injected anomalies
    datasets/sample_mission_2.csv     — variant dataset, 2 different anomaly types
    datasets/ground_truth_anomalies.json — row-range index of injected windows
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from anomaly.nominal_ranges import NOMINAL_RANGES

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
N_ROWS = 500
START_TS = pd.Timestamp("2024-01-01T00:00:00Z")
OUT_DIR = Path(__file__).parent

# Field order for output columns (matches API contract)
NUMERIC_FIELDS = [
    "battery_voltage",
    "temperature_c",
    "signal_strength_db",
    "solar_panel_efficiency_pct",
    "fuel_level_pct",
    "altitude_km",
    "velocity_kms",
]


# ---------------------------------------------------------------------------
# Helper: build a smooth baseline signal within nominal bounds
# ---------------------------------------------------------------------------
def _baseline(
    rng: np.random.Generator,
    lo: float,
    hi: float,
    n: int,
    sine_amp_frac: float = 0.08,
    drift_frac: float = 0.05,
    noise_frac: float = 0.015,
) -> np.ndarray:
    """Return `n` values inside [lo, hi] using sine + drift + Gaussian noise."""
    mid = (lo + hi) / 2.0
    width = hi - lo

    t = np.linspace(0, 2 * np.pi, n)
    sine = np.sin(t) * sine_amp_frac * width
    drift = np.linspace(0, drift_frac * width, n)
    noise = rng.normal(0, noise_frac * width, n)

    raw = mid + sine + drift + noise
    # Clip tightly so no baseline value escapes nominal range
    margin = noise_frac * width
    return np.clip(raw, lo + margin, hi - margin)


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------
def build_dataset(
    rng: np.random.Generator,
    *,
    # ---- anomaly #1: battery voltage drop (ramp down) ----
    batt_drop_rows: tuple[int, int] = (120, 135),
    batt_drop_value: float = 20.0,
    # ---- anomaly #2: temperature spike (single row) ----
    temp_spike_row: int = 260,
    temp_spike_value: float = 65.0,
    # ---- anomaly #3: signal dropout (sustained drop) ----
    sig_drop_rows: tuple[int, int] = (380, 390),
    sig_drop_value: float = -110.0,
    # ---- extra anomalies for dataset-2 (None = skip) ----
    solar_drop_rows: tuple[int, int] | None = None,
    solar_drop_value: float = 30.0,
    alt_drop_row: int | None = None,
    alt_drop_value: float = 385.0,
) -> pd.DataFrame:
    """Build a single telemetry DataFrame with injected anomalies."""

    # 1. Timestamps
    timestamps = [
        (START_TS + pd.Timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(N_ROWS)
    ]

    # 2. Baseline signals
    data: dict[str, np.ndarray] = {}
    for field in NUMERIC_FIELDS:
        lo, hi = NOMINAL_RANGES[field]
        data[field] = _baseline(rng, lo, hi, N_ROWS)

    # 3. Inject anomaly #1 — battery voltage drop (rows 120-135, ramp to ~20 V)
    r0, r1 = batt_drop_rows
    baseline_batt = data["battery_voltage"][r0]
    ramp = np.linspace(baseline_batt, batt_drop_value, r1 - r0 + 1)
    data["battery_voltage"][r0 : r1 + 1] = ramp

    # 4. Inject anomaly #2 — temperature spike (row 260, ~65 °C)
    data["temperature_c"][temp_spike_row] = temp_spike_value

    # 5. Inject anomaly #3 — signal dropout (rows 380-390, ~-110 dB)
    r0s, r1s = sig_drop_rows
    data["signal_strength_db"][r0s : r1s + 1] = sig_drop_value

    # 6. Optional anomaly — solar efficiency drop (dataset-2 only)
    if solar_drop_rows is not None:
        sr0, sr1 = solar_drop_rows
        data["solar_panel_efficiency_pct"][sr0 : sr1 + 1] = solar_drop_value

    # 7. Optional anomaly — altitude deviation (dataset-2 only)
    if alt_drop_row is not None:
        data["altitude_km"][alt_drop_row] = alt_drop_value

    # 8. mission_mode: nominal → maneuver → nominal → safe_mode → nominal
    mission_mode = np.full(N_ROWS, "nominal", dtype=object)
    # maneuver window around battery anomaly
    mission_mode[batt_drop_rows[0] : batt_drop_rows[1] + 1] = "maneuver"
    # safe_mode window around signal dropout
    mission_mode[sig_drop_rows[0] : sig_drop_rows[1] + 1] = "safe_mode"
    # also safe_mode for temperature spike (brief)
    mission_mode[temp_spike_row] = "safe_mode"

    # 9. subsystem_status: nominal / warning / critical
    subsystem_status = np.full(N_ROWS, "nominal", dtype=object)

    # battery anomaly window → warning; deepest point → critical
    subsystem_status[batt_drop_rows[0] : batt_drop_rows[1] + 1] = "warning"
    subsystem_status[batt_drop_rows[1]] = "critical"  # peak (lowest voltage)

    # temperature spike → critical
    subsystem_status[temp_spike_row] = "critical"

    # signal dropout window → warning; first row → critical
    subsystem_status[sig_drop_rows[0] : sig_drop_rows[1] + 1] = "warning"
    subsystem_status[sig_drop_rows[0]] = "critical"

    # dataset-2 extra anomalies
    if solar_drop_rows is not None:
        sr0, sr1 = solar_drop_rows
        subsystem_status[sr0 : sr1 + 1] = "warning"
        subsystem_status[(sr0 + sr1) // 2] = "critical"
    if alt_drop_row is not None:
        subsystem_status[alt_drop_row] = "critical"

    # 10. Assemble DataFrame
    df = pd.DataFrame({"timestamp": timestamps, **data})
    df["mission_mode"] = mission_mode
    df["subsystem_status"] = subsystem_status
    return df


# ---------------------------------------------------------------------------
# Ground-truth anomaly index (primary dataset only)
# ---------------------------------------------------------------------------
def _ts(row: int) -> str:
    return (START_TS + pd.Timedelta(minutes=row)).strftime("%Y-%m-%dT%H:%M:%SZ")


GROUND_TRUTH = [
    {
        "field": "battery_voltage",
        "row_start": 120,
        "row_end": 135,
        "timestamp_start": _ts(120),
        "timestamp_end": _ts(135),
    },
    {
        "field": "temperature_c",
        "row_start": 260,
        "row_end": 260,
        "timestamp_start": _ts(260),
        "timestamp_end": _ts(260),
    },
    {
        "field": "signal_strength_db",
        "row_start": 380,
        "row_end": 390,
        "timestamp_start": _ts(380),
        "timestamp_end": _ts(390),
    },
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    rng = np.random.default_rng(SEED)

    # ---- Dataset 1 (primary) ----
    df1 = build_dataset(rng)
    csv1 = OUT_DIR / "sample_mission.csv"
    df1.to_csv(csv1, index=False)
    print(f"[generate_sample] wrote {csv1}  ({len(df1)} rows, {len(df1.columns)} cols)")

    # ---- Ground truth ----
    gt_path = OUT_DIR / "ground_truth_anomalies.json"
    gt_path.write_text(json.dumps(GROUND_TRUTH, indent=2))
    print(f"[generate_sample] wrote {gt_path}  ({len(GROUND_TRUTH)} anomaly windows)")

    # ---- Dataset 2 (variant — different anomaly types, fresh rng) ----
    rng2 = np.random.default_rng(SEED + 1)
    df2 = build_dataset(
        rng2,
        solar_drop_rows=(200, 220),
        solar_drop_value=30.0,
        alt_drop_row=340,
        alt_drop_value=385.0,
    )
    csv2 = OUT_DIR / "sample_mission_2.csv"
    df2.to_csv(csv2, index=False)
    print(f"[generate_sample] wrote {csv2}  ({len(df2)} rows, {len(df2.columns)} cols)")

    # ---- Quick sanity check ----
    _verify(df1, "sample_mission.csv")
    _verify(df2, "sample_mission_2.csv")


def _verify(df: pd.DataFrame, name: str) -> None:
    required_cols = [
        "timestamp", "battery_voltage", "temperature_c", "signal_strength_db",
        "solar_panel_efficiency_pct", "fuel_level_pct", "altitude_km", "velocity_kms",
        "mission_mode", "subsystem_status",
    ]
    assert len(df) == N_ROWS, f"{name}: expected {N_ROWS} rows, got {len(df)}"
    missing = [c for c in required_cols if c not in df.columns]
    assert not missing, f"{name}: missing columns {missing}"
    print(f"[verify] {name} OK — {len(df)} rows, columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
