import pandas as pd
import numpy as np

# Nominal operational thresholds defined in the technical blueprint
NOMINAL_BOUNDS = {
    "battery_voltage": {"min": 26.0, "max": 32.0},
    "temperature_c": {"min": -10.0, "max": 45.0},
    "signal_strength_db": {"min": -90.0, "max": -30.0},
    "solar_panel_efficiency_pct": {"min": 70.0, "max": 100.0},
    "fuel_level_pct": {"min": 5.0, "max": 100.0}
}

def detect_statistical_anomalies(df: pd.DataFrame, window: int = 10, z_threshold: float = 2.5) -> list[dict]:
    """
    Detects anomalies using a combination of fixed nominal bounds 
    and rolling Z-score standard deviation spikes.
    """
    anomalies = []
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        # 1. Check fixed nominal range bounds
        if col in NOMINAL_BOUNDS:
            min_val = NOMINAL_BOUNDS[col]["min"]
            max_val = NOMINAL_BOUNDS[col]["max"]
            
            out_of_bounds = df[(df[col] < min_val) | (df[col] > max_val)]
            for idx, row in out_of_bounds.iterrows():
                val = float(row[col])
                direction = "below" if val < min_val else "above"
                bound_val = min_val if val < min_val else max_val
                
                anomalies.append({
                    "field": col,
                    "timestamp": str(row.get("timestamp", idx)),
                    "value": round(val, 2),
                    "severity": "CRITICAL" if val < min_val * 0.85 or val > max_val * 1.15 else "WARNING",
                    "method": "Fixed Threshold",
                    "detection_method_explanation": f"Value {val:.2f} went {direction} nominal operational bound ({bound_val})."
                })

        # 2. Rolling Z-Score calculation for dynamic drift detection
        rolling_mean = df[col].rolling(window=window, min_periods=1).mean()
        rolling_std = df[col].rolling(window=window, min_periods=1).std().fillna(0.0001)
        z_scores = (df[col] - rolling_mean) / rolling_std

        spikes = df[abs(z_scores) > z_threshold]
        for idx, row in spikes.iterrows():
            # Avoid duplicate flags if already caught by fixed bounds
            if not any(a["field"] == col and a["timestamp"] == str(row.get("timestamp", idx)) for a in anomalies):
                z_val = float(z_scores.loc[idx])
                anomalies.append({
                    "field": col,
                    "timestamp": str(row.get("timestamp", idx)),
                    "value": round(float(row[col]), 2),
                    "severity": "WARNING",
                    "method": "Rolling Z-Score",
                    "detection_method_explanation": f"Value deviated by {z_val:.1f} std-devs from rolling mean."
                })

    return anomalies