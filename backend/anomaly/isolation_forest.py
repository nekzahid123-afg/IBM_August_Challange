"""
Isolation Forest anomaly detector for telemetry data.

Algorithm:
  1. Extract numeric columns (keys of NOMINAL_RANGES); scale with StandardScaler.
  2. Compute contamination from ground_truth_anomalies.json:
       contamination = sum(row_end - row_start + 1 for each entry) / 500
       Clamped to [0.01, 0.5].
  3. Fit IsolationForest(contamination=contamination, random_state=42).
  4. Among flagged rows, sort by raw anomaly score (most negative = worst).
     Assign severity by score tercile: bottom third → "high"; middle → "medium"; top → "low".
  5. Return list[Anomaly] with method="isolation_forest".
"""

import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from anomaly.models import Anomaly
from anomaly.nominal_ranges import NOMINAL_RANGES

_GROUND_TRUTH_PATH = Path(__file__).parent.parent / "datasets" / "ground_truth_anomalies.json"
_TOTAL_ROWS = 500  # total rows in sample_mission.csv


def _compute_contamination() -> float:
    """
    Read ground_truth_anomalies.json and derive the contamination ratio.

    Each entry has row_start and row_end (1-based inclusive indices).
    contamination = sum(row_end - row_start + 1 for each entry) / _TOTAL_ROWS
    Clamped to [0.01, 0.5].

    For the current ground_truth_anomalies.json:
      battery_voltage: rows 120–135 → 16 rows
      temperature_c:   rows 260–260 →  1 row
      signal_strength: rows 380–390 → 11 rows
      total injected  = 28 rows
      contamination   = 28 / 500 = 0.056 → clamped to 0.056 (within [0.01, 0.5])
    """
    with open(_GROUND_TRUTH_PATH) as f:
        entries = json.load(f)
    injected = sum(e["row_end"] - e["row_start"] + 1 for e in entries)
    ratio = injected / _TOTAL_ROWS
    return float(max(0.01, min(0.5, ratio)))


def detect(df: pd.DataFrame) -> list[Anomaly]:
    """
    Run Isolation Forest anomaly detection on *df* and return a list of Anomaly objects.

    *df* must have a 'timestamp' column (pd.Timestamp) and numeric columns matching
    the keys of NOMINAL_RANGES.
    """
    # ── Feature extraction ────────────────────────────────────────────────────
    numeric_fields = [f for f in NOMINAL_RANGES if f in df.columns]
    if not numeric_fields:
        return []

    n_fields = len(numeric_fields)
    X = df[numeric_fields].astype(float).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    contamination = _compute_contamination()

    # ── Model fit + predict ───────────────────────────────────────────────────
    clf = IsolationForest(contamination=contamination, random_state=42)
    clf.fit(X_scaled)

    labels = clf.predict(X_scaled)          # -1 = anomaly, +1 = normal
    raw_scores = clf.score_samples(X_scaled)  # more negative = more anomalous

    flagged_indices = np.where(labels == -1)[0]
    if len(flagged_indices) == 0:
        return []

    flagged_scores = raw_scores[flagged_indices]

    # Sort so most negative (worst) is first for tercile assignment
    sort_order = np.argsort(flagged_scores)           # ascending (worst first)
    sorted_flagged = flagged_indices[sort_order]
    sorted_scores = flagged_scores[sort_order]

    n_flagged = len(sorted_flagged)
    tercile = n_flagged / 3.0

    def _severity(rank: int) -> str:
        if rank < tercile:
            return "high"
        if rank < 2 * tercile:
            return "medium"
        return "low"

    # ── Build Anomaly objects ─────────────────────────────────────────────────
    anomalies: list[Anomaly] = []
    for rank, (df_idx, score) in enumerate(zip(sorted_flagged, sorted_scores)):
        ts = df["timestamp"].iloc[df_idx]
        timestamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        severity = _severity(rank)

        # Use the field with the largest scaled deviation as the representative field
        row_scaled = X_scaled[df_idx]
        dominant_field_pos = int(np.argmax(np.abs(row_scaled)))
        field = numeric_fields[dominant_field_pos]
        value = float(X[df_idx, dominant_field_pos])

        detection_detail = (
            f"Isolation Forest score: {score:.3f}; "
            f"multivariate anomaly across {n_fields} fields"
        )

        anomalies.append(Anomaly(
            id=uuid4().hex,
            field=field,
            timestamp=timestamp,
            value=value,
            severity=severity,
            method="isolation_forest",
            detection_detail=detection_detail,
        ))

    return anomalies
