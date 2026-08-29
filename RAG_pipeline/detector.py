import pandas as pd
from statistical import detect_statistical_anomalies
from isolation_forest import detect_isolation_anomalies

def run_anomaly_pipeline(df: pd.DataFrame) -> dict:
    """
    Executes both statistical and Isolation Forest detectors, deduplicates results, 
    and returns anomalies along with a Mission Health Score (0-100).
    """
    stat_anomalies = detect_statistical_anomalies(df)
    iso_anomalies = detect_isolation_anomalies(df)

    # Combine and deduplicate by field and timestamp
    all_anomalies = list(stat_anomalies)
    existing_keys = {(a["field"], a["timestamp"]) for a in stat_anomalies}

    for iso_a in iso_anomalies:
        key = (iso_a["field"], iso_a["timestamp"])
        if key not in existing_keys:
            all_anomalies.append(iso_a)

    # Compute Mission Health Score (100 - weighted penalty for anomalies)
    total_rows = max(len(df), 1)
    critical_count = sum(1 for a in all_anomalies if a["severity"] == "CRITICAL")
    warning_count = sum(1 for a in all_anomalies if a["severity"] == "WARNING")

    penalty = ((critical_count * 10) + (warning_count * 3)) / total_rows * 100
    health_score = max(0.0, round(100.0 - penalty, 1))

    return {
        "health_score": health_score,
        "total_anomalies": len(all_anomalies),
        "anomalies": all_anomalies
    }

if __name__ == "__main__":
    # Test with dummy telemetry data
    sample_data = {
        "timestamp": ["2026-08-22T10:00:00Z", "2026-08-22T10:01:00Z", "2026-08-22T10:02:00Z"],
        "battery_voltage": [28.2, 28.1, 21.0],  # Injected battery voltage drop
        "temperature_c": [22.0, 22.5, 48.0]      # Injected temperature spike
    }
    test_df = pd.DataFrame(sample_data)
    results = run_anomaly_pipeline(test_df)
    
    print(f"Mission Health Score: {results['health_score']}/100")
    print(f"Detected Anomalies: {results['total_anomalies']}")
    for a in results["anomalies"]:
        print(f" - [{a['severity']}] {a['field']} @ {a['timestamp']}: {a['detection_method_explanation']}")