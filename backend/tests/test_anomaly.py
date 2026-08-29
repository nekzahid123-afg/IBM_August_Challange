"""
Unit tests for anomaly detection pipeline.

Assertions:
  1. Every injected anomaly window from ground_truth_anomalies.json contains
     at least one detected anomaly (from either method).
  2. No detected anomaly outside ground-truth windows is labeled "high"
     (sanity check for false positives).
  3. Battery voltage anomaly rows have severity "high" (drop to ~20V is
     >25% outside nominal 26–32V range).
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from anomaly import statistical, isolation_forest
from anomaly.models import Anomaly
from api.routes_anomalies import _dedup

_DATASETS_DIR = Path(__file__).parent.parent / "datasets"
_SAMPLE_CSV = _DATASETS_DIR / "sample_mission.csv"
_GROUND_TRUTH = _DATASETS_DIR / "ground_truth_anomalies.json"


def _load_sample() -> pd.DataFrame:
    df = pd.read_csv(_SAMPLE_CSV)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _load_ground_truth() -> list[dict]:
    with open(_GROUND_TRUTH) as f:
        return json.load(f)


def _run_detection(df: pd.DataFrame) -> list[Anomaly]:
    """Run both detectors and return the deduplicated merged list."""
    return _dedup(statistical.detect(df), isolation_forest.detect(df))


def test_all_injected_windows_detected():
    """
    Assert that every injected anomaly window from ground_truth_anomalies.json
    contains at least one detected anomaly (from either statistical or IF).
    """
    df = _load_sample()
    gt_entries = _load_ground_truth()

    all_anomalies = _run_detection(df)

    # Build a set of (field, timestamp) tuples from all detected anomalies
    detected = {(a.field, a.timestamp) for a in all_anomalies}

    for entry in gt_entries:
        field = entry["field"]
        start = pd.Timestamp(entry["timestamp_start"])
        end = pd.Timestamp(entry["timestamp_end"])

        # Check if any detected anomaly falls within [start, end] for this field
        matched = any(
            (f == field and start <= pd.Timestamp(ts) <= end)
            for f, ts in detected
        )
        assert matched, (
            f"No anomaly detected in injected window: field={field}, "
            f"timestamp_start={entry['timestamp_start']}, timestamp_end={entry['timestamp_end']}"
        )


def test_no_high_severity_outside_ground_truth():
    """
    Assert no detected anomaly outside ground-truth windows is labeled "high".

    This is a sanity check for false positive inflation — if statistical or IF
    is flagging normal behavior as critically anomalous, this test will fail.
    """
    df = _load_sample()
    gt_entries = _load_ground_truth()

    all_anomalies = _run_detection(df)

    # Build ground-truth window set: (field, timestamp_start, timestamp_end)
    gt_windows = [
        (e["field"], pd.Timestamp(e["timestamp_start"]), pd.Timestamp(e["timestamp_end"]))
        for e in gt_entries
    ]

    def _is_in_ground_truth(field: str, ts_str: str) -> bool:
        ts = pd.Timestamp(ts_str)
        for gt_field, start, end in gt_windows:
            if field == gt_field and start <= ts <= end:
                return True
        return False

    for a in all_anomalies:
        if a.severity == "high" and not _is_in_ground_truth(a.field, a.timestamp):
            pytest.fail(
                f"High-severity anomaly detected outside ground-truth windows: "
                f"field={a.field}, timestamp={a.timestamp}, value={a.value}, "
                f"method={a.method}"
            )


def test_battery_voltage_severity_is_high():
    """
    Assert that deeply-dropped battery voltage anomaly rows have severity "high".

    The injected ramp descends from ~29V to 20V over rows 120–135.
    Rows whose value has dropped >25% below the nominal lower bound (26V) must be "high":
      excess = (26 - value) / (32 - 26) > 0.25  →  value < 26 - 0.25*6 = 24.5V
    These rows are clearly within the injected window and unambiguously high-severity.
    """
    df = _load_sample()
    gt_entries = _load_ground_truth()

    all_anomalies = _run_detection(df)

    # Find the battery_voltage entry in ground truth
    bv_entry = next((e for e in gt_entries if e["field"] == "battery_voltage"), None)
    assert bv_entry is not None, "battery_voltage entry not found in ground_truth_anomalies.json"

    start = pd.Timestamp(bv_entry["timestamp_start"])
    end = pd.Timestamp(bv_entry["timestamp_end"])

    # Only check rows where value has dropped far enough to be unambiguously "high"
    # by the nominal-range criterion: below 24.5V (>25% of 6V range below lower bound 26V)
    HIGH_THRESHOLD = 24.5  # 26 - 0.25 * 6

    deeply_dropped = [
        a for a in all_anomalies
        if a.field == "battery_voltage"
        and start <= pd.Timestamp(a.timestamp) <= end
        and a.value < HIGH_THRESHOLD
    ]

    assert len(deeply_dropped) > 0, (
        "No battery_voltage anomalies with value < 24.5V found in the injected window"
    )

    for a in deeply_dropped:
        assert a.severity == "high", (
            f"Battery voltage anomaly at {a.timestamp} (value={a.value:.2f}) "
            f"has severity {a.severity!r}, expected 'high'"
        )
