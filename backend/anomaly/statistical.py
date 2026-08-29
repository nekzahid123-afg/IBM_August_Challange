"""
Statistical anomaly detector for telemetry data.

Algorithm (per field in NOMINAL_RANGES):
  1. Compute rolling mean and std (window=20 rows).
  2. Flag rows where abs(value - mean) > 2.0 * std.
  3. Assign severity from z-score:
       > 4.0 std → "high"
       2.5–4.0   → "medium"
       2.0–2.5   → "low"
  4. Also check nominal range excess:
       excess = abs(value - nearest_bound) / range_width
       > 25% → "high"; 10–25% → "medium"; < 10% → "low"
  5. Take the higher of the two severity levels.
"""

from uuid import uuid4

import pandas as pd

from anomaly.models import Anomaly, SEVERITY_ORDER
from anomaly.nominal_ranges import NOMINAL_RANGES


def _std_severity(z: float) -> str:
    az = abs(z)
    if az > 4.0:
        return "high"
    if az > 2.5:
        return "medium"
    return "low"


def _nominal_severity(value: float, lo: float, hi: float) -> str | None:
    """
    Return severity based on how far outside the nominal range the value is,
    expressed as a fraction of the range width.  Returns None if value is in range.
    """
    range_width = hi - lo
    if range_width == 0:
        return None
    if lo <= value <= hi:
        return None
    nearest_bound = lo if value < lo else hi
    excess = abs(value - nearest_bound) / range_width
    if excess > 0.25:
        return "high"
    if excess > 0.10:
        return "medium"
    return "low"


def _max_severity(a: str, b: str | None) -> str:
    if b is None:
        return a
    return a if SEVERITY_ORDER[a] >= SEVERITY_ORDER[b] else b


def detect(df: pd.DataFrame) -> list[Anomaly]:
    """
    Run statistical anomaly detection on *df* and return a list of Anomaly objects.

    *df* must have a 'timestamp' column (pd.Timestamp) and numeric columns matching
    the keys of NOMINAL_RANGES.
    """
    anomalies: list[Anomaly] = []

    for field, (lo, hi) in NOMINAL_RANGES.items():
        if field not in df.columns:
            continue

        series = df[field].astype(float)
        rolling = series.rolling(window=20, min_periods=1)
        mean_s = rolling.mean()
        std_s = rolling.std(ddof=0).fillna(0)

        for idx in series.index:
            mean = mean_s.loc[idx]
            std = std_s.loc[idx]
            value = series.loc[idx]

            z = (value - mean) / std if std > 0 else 0.0

            # ── Severity from std (only meaningful when std > 0 and |z| > 2.0) ──
            sev_std = _std_severity(z) if std > 0 and abs(z) > 2.0 else None

            # ── Severity from nominal range ────────────────────────────────────
            sev_nom = _nominal_severity(value, lo, hi)

            # Skip rows not flagged by either criterion
            if sev_std is None and sev_nom is None:
                continue

            # Resolve severity: take higher; when sev_std is None, sev_nom dominates
            if sev_std is not None and sev_nom is not None:
                severity = _max_severity(sev_std, sev_nom)
            elif sev_std is not None:
                severity = sev_std
            else:
                severity = sev_nom  # type: ignore[assignment]

            direction = "above" if value > mean else "below"
            detection_detail = (
                f"{direction} {abs(z):.1f} std from rolling mean "
                f"(mean={mean:.2f}, std={std:.2f}); nominal {lo}–{hi}"
            )

            ts = df["timestamp"].loc[idx]
            timestamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

            anomalies.append(Anomaly(
                id=uuid4().hex,
                field=field,
                timestamp=timestamp,
                value=float(value),
                severity=severity,
                method="statistical",
                detection_detail=detection_detail,
            ))

    return anomalies
