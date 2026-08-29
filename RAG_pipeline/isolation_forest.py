import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

def detect_isolation_anomalies(df: pd.DataFrame, contamination: float = 0.05) -> list[dict]:
    """
    Applies an Isolation Forest cross-check across all numeric fields 
    to flag joint, multi-variable anomalies.
    """
    anomalies = []
    numeric_cols = [col for col in df.select_dtypes(include=[np.number]).columns if col != "timestamp"]

    if len(numeric_cols) < 2 or len(df) < 5:
        return anomalies

    # Handle missing values if any exist
    clean_df = df[numeric_cols].fillna(df[numeric_cols].mean())

    # Fit Isolation Forest
    model = IsolationForest(contamination=contamination, random_state=42)
    predictions = model.fit_predict(clean_df)
    scores = model.decision_function(clean_df)

    # Locate indices flagged as -1 (anomaly)
    anomalous_indices = np.where(predictions == -1)[0]

    for idx in anomalous_indices:
        row = df.iloc[idx]
        anomaly_score = abs(float(scores[idx]))
        
        # Identify which specific feature in the joint state deviated most from median
        deviations = (clean_df.iloc[idx] - clean_df.median()).abs()
        primary_field = str(deviations.idxmax())

        anomalies.append({
            "field": primary_field,
            "timestamp": str(row.get("timestamp", idx)),
            "value": round(float(row[primary_field]), 2),
            "severity": "WARNING",
            "method": "Isolation Forest",
            "detection_method_explanation": (
                f"Multi-variate joint anomaly detected across features "
                f"(Primary driver: {primary_field} = {row[primary_field]:.2f}, Anomaly Score: {anomaly_score:.3f})."
            )
        })

    return anomalies