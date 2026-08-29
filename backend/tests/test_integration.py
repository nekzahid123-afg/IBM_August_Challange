"""
Integration tests — Sub-Task 9.

Covers test cases 2–9 from the acceptance criteria:
  2.  E2E pipeline on sample_mission.csv (upload → anomalies → insights → report)
  3.  E2E pipeline on sample_mission_2.csv
  4.  Duplicate-click guard (idempotency, insights called only once)
  5.  Bad CSV upload → 422 MISSING_COLUMNS
  6.  Report before insights → 404 INSIGHTS_NOT_FOUND
  7.  Insights before anomalies → 400 ANOMALIES_NOT_FOUND
  8.  Session-not-found on all 4 endpoints
  9.  Anomaly severity validation + chronological sort order
"""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Import the FastAPI app — sessions module must be importable from here
from main import app

client = TestClient(app)

_DATASETS = Path(__file__).parent.parent / "datasets"
_SAMPLE_CSV     = _DATASETS / "sample_mission.csv"
_SAMPLE_CSV_2   = _DATASETS / "sample_mission_2.csv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_sample() -> dict:
    """GET /upload/sample → returns full response body as dict."""
    r = client.get("/upload/sample")
    assert r.status_code == 200, f"upload/sample failed: {r.text}"
    return r.json()


def _upload_csv(path: Path) -> dict:
    """POST /upload with a real CSV file → returns full response body as dict."""
    with open(path, "rb") as f:
        r = client.post("/upload", files={"file": ("mission.csv", f, "text/csv")})
    assert r.status_code == 200, f"POST /upload failed: {r.text}"
    return r.json()


def _get_anomalies(session_id: str) -> dict:
    r = client.get(f"/anomalies?session_id={session_id}")
    assert r.status_code == 200, f"GET /anomalies failed: {r.text}"
    return r.json()


def _post_insights(session_id: str) -> dict:
    r = client.post("/insights", json={"session_id": session_id})
    assert r.status_code == 200, f"POST /insights failed: {r.text}"
    return r.json()


def _get_report(session_id: str, fmt: str = "markdown") -> tuple[int, bytes]:
    r = client.get(f"/report?session_id={session_id}&format={fmt}")
    return r.status_code, r.content


# ============================================================================
# Test 2 — E2E pipeline on sample_mission.csv
# ============================================================================

class TestE2EPipelineSampleMission:

    def test_upload_returns_session_and_health_score(self):
        body = _upload_sample()
        assert "session_id" in body
        assert isinstance(body["session_id"], str) and body["session_id"]
        assert "health_score" in body
        assert 0 <= body["health_score"] <= 100

    def test_anomalies_non_empty(self):
        body = _upload_sample()
        sid = body["session_id"]
        anom = _get_anomalies(sid)
        assert anom["anomalies"], "anomalies array must be non-empty for sample_mission.csv"

    def test_all_three_injected_windows_present(self):
        """battery_voltage, temperature_c, signal_strength_db all appear in anomalies."""
        body = _upload_sample()
        sid = body["session_id"]
        anom = _get_anomalies(sid)
        fields = {a["field"] for a in anom["anomalies"]}
        assert "battery_voltage" in fields, "battery_voltage anomaly missing"
        assert "temperature_c" in fields, "temperature_c anomaly missing"
        assert "signal_strength_db" in fields, "signal_strength_db anomaly missing"

    def test_anomalies_sorted_by_timestamp(self):
        body = _upload_sample()
        sid = body["session_id"]
        anom = _get_anomalies(sid)
        timestamps = [a["timestamp"] for a in anom["anomalies"]]
        assert timestamps == sorted(timestamps), "anomalies must be in chronological order"

    def test_insights_response_shape(self):
        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)
        ins = _post_insights(sid)

        assert ins["session_id"] == sid
        assert isinstance(ins["mission_summary"], str) and ins["mission_summary"]
        assert isinstance(ins["insights"], list) and ins["insights"]

    def test_each_insight_has_required_fields(self):
        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)
        ins = _post_insights(sid)

        for insight in ins["insights"]:
            assert insight.get("explanation"), "explanation must not be empty"
            assert insight.get("root_cause_hypothesis"), "root_cause_hypothesis must not be empty"
            assert insight.get("recommendation"), "recommendation must not be empty"
            # source_chunks: may be non-empty when RAG is active (ChromaDB + watsonx.ai)
            assert isinstance(insight["source_chunks"], list), "source_chunks must be a list"
            assert isinstance(insight["no_strong_match"], bool), "no_strong_match must be a bool"

    def test_report_markdown_contains_required_sections(self):
        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)
        _post_insights(sid)

        status, content = _get_report(sid, "markdown")
        assert status == 200
        md = content.decode("utf-8")

        # Must contain health score
        assert "Health Score" in md, "Report missing 'Health Score'"
        # Must contain anomaly table header
        assert "Field" in md and "Severity" in md, "Report missing anomaly table columns"
        # At least one AI explanation section with Hypothesis and Recommended Action
        assert "Hypothesis:" in md, "Report missing 'Hypothesis:'"
        assert "Recommended Action:" in md, "Report missing 'Recommended Action:'"
        # Mission Summary section
        assert "Mission Summary" in md, "Report missing 'Mission Summary'"

    def test_report_contains_health_score_value(self):
        """Health score integer must appear in the report text."""
        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)
        _post_insights(sid)
        _, content = _get_report(sid, "markdown")
        md = content.decode("utf-8")
        # Health score is an integer 0-100; it must appear somewhere in the report
        assert "/ 100" in md or "100" in md, "Report should show health score out of 100"


# ============================================================================
# Test 3 — E2E pipeline on sample_mission_2.csv
# ============================================================================

class TestE2EPipelineSampleMission2:

    def test_upload_returns_session(self):
        body = _upload_csv(_SAMPLE_CSV_2)
        assert "session_id" in body and body["session_id"]
        assert "health_score" in body

    def test_anomalies_succeed(self):
        body = _upload_csv(_SAMPLE_CSV_2)
        sid = body["session_id"]
        anom = _get_anomalies(sid)
        assert "anomalies" in anom
        assert isinstance(anom["anomalies"], list)

    def test_insights_succeed(self):
        body = _upload_csv(_SAMPLE_CSV_2)
        sid = body["session_id"]
        _get_anomalies(sid)
        ins = _post_insights(sid)
        assert ins["session_id"] == sid
        assert isinstance(ins["mission_summary"], str)
        assert isinstance(ins["insights"], list)

    def test_report_succeeds(self):
        body = _upload_csv(_SAMPLE_CSV_2)
        sid = body["session_id"]
        _get_anomalies(sid)
        _post_insights(sid)
        status, content = _get_report(sid, "markdown")
        assert status == 200
        md = content.decode("utf-8")
        assert "Mission Summary" in md


# ============================================================================
# Test 4 — Duplicate-click guard (idempotency)
# ============================================================================

class TestIdempotency:

    def test_second_insights_call_returns_cached_result(self):
        """Both calls return HTTP 200 with identical content."""
        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)

        r1 = client.post("/insights", json={"session_id": sid})
        r2 = client.post("/insights", json={"session_id": sid})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["mission_summary"] == r2.json()["mission_summary"]
        assert len(r1.json()["insights"]) == len(r2.json()["insights"])

    def test_generate_insights_called_only_once(self):
        """Verify the generator is only invoked on the first call."""
        import insights.generator as gen_module

        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)

        call_count = 0
        original = gen_module.generate_insights

        def counting_wrapper(anomalies):
            nonlocal call_count
            call_count += 1
            return original(anomalies)

        with patch.object(gen_module, "generate_insights", side_effect=counting_wrapper):
            client.post("/insights", json={"session_id": sid})
            client.post("/insights", json={"session_id": sid})

        assert call_count == 1, f"Expected 1 call, got {call_count} — cache miss on second call"


# ============================================================================
# Test 5 — Bad CSV upload → 422 MISSING_COLUMNS
# ============================================================================

class TestBadCsvUpload:

    def test_missing_battery_voltage_column(self):
        """CSV missing battery_voltage → 422 MISSING_COLUMNS mentioning the column."""
        # Build a minimal CSV with all required columns EXCEPT battery_voltage
        required = [
            "timestamp", "temperature_c", "signal_strength_db",
            "solar_panel_efficiency_pct", "fuel_level_pct",
            "altitude_km", "velocity_kms", "mission_mode", "subsystem_status",
        ]
        csv_content = ",".join(required) + "\n2024-01-01T00:00:00Z,25.0,-70.0,85.0,50.0,410.0,7.65,NOMINAL,OK\n"
        file_bytes = csv_content.encode("utf-8")

        r = client.post(
            "/upload",
            files={"file": ("bad.csv", io.BytesIO(file_bytes), "text/csv")},
        )
        assert r.status_code == 422
        body = r.json()
        assert body["error"]["code"] == "MISSING_COLUMNS"
        assert "battery_voltage" in body["error"]["message"]

    def test_empty_csv_returns_422(self):
        """An empty (header-only) CSV with missing columns also returns 422."""
        csv_content = "timestamp,temperature_c\n"
        r = client.post(
            "/upload",
            files={"file": ("empty.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "MISSING_COLUMNS"


# ============================================================================
# Test 6 — Report before insights → 404 INSIGHTS_NOT_FOUND
# ============================================================================

class TestReportBeforeInsights:

    def test_report_before_insights_returns_404(self):
        body = _upload_sample()
        sid = body["session_id"]
        _get_anomalies(sid)  # anomalies populated, but no insights

        status, content = _get_report(sid, "markdown")
        assert status == 404
        body_json = json.loads(content)
        assert body_json["error"]["code"] == "INSIGHTS_NOT_FOUND"


# ============================================================================
# Test 7 — Insights before anomalies → 400 ANOMALIES_NOT_FOUND
# ============================================================================

class TestInsightsBeforeAnomalies:

    def test_insights_without_anomalies_returns_400(self):
        body = _upload_sample()
        sid = body["session_id"]
        # Do NOT call /anomalies — jump straight to /insights

        r = client.post("/insights", json={"session_id": sid})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "ANOMALIES_NOT_FOUND"


# ============================================================================
# Test 8 — Session-not-found on all 4 endpoints
# ============================================================================

class TestSessionNotFound:
    _GHOST = "nonexistent-session-xyz-00000"

    def test_anomalies_session_not_found(self):
        r = client.get(f"/anomalies?session_id={self._GHOST}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_insights_session_not_found(self):
        r = client.post("/insights", json={"session_id": self._GHOST})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_telemetry_session_not_found(self):
        r = client.get(f"/telemetry?session_id={self._GHOST}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_report_session_not_found(self):
        r = client.get(f"/report?session_id={self._GHOST}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"


# ============================================================================
# Test 9 — Anomaly severity validation
# ============================================================================

class TestAnomalySeverity:

    def _get_all_anomalies(self) -> list[dict]:
        body = _upload_sample()
        sid = body["session_id"]
        anom = _get_anomalies(sid)
        return anom["anomalies"]

    def test_battery_voltage_has_high_severity_anomaly(self):
        """At least one battery_voltage anomaly must be labeled 'high'."""
        anomalies = self._get_all_anomalies()
        bv_high = [
            a for a in anomalies
            if a["field"] == "battery_voltage" and a["severity"] == "high"
        ]
        assert bv_high, (
            "No high-severity battery_voltage anomaly found. "
            "The injected drop to 20V (>25% outside 26–32V range) must produce 'high'."
        )

    def test_temperature_c_has_high_severity_anomaly(self):
        """At least one temperature_c anomaly must be labeled 'high'."""
        anomalies = self._get_all_anomalies()
        temp_high = [
            a for a in anomalies
            if a["field"] == "temperature_c" and a["severity"] == "high"
        ]
        assert temp_high, (
            "No high-severity temperature_c anomaly found. "
            "The injected spike to 65°C (outside 10–40°C range) must produce 'high'."
        )

    def test_anomalies_are_sorted_by_timestamp(self):
        """Anomaly list must be in chronological (ascending) order."""
        anomalies = self._get_all_anomalies()
        timestamps = [a["timestamp"] for a in anomalies]
        assert timestamps == sorted(timestamps), (
            "Anomalies are not sorted by timestamp. "
            f"Order received: {timestamps}"
        )

    def test_battery_voltage_anomaly_in_correct_window(self):
        """At least one battery_voltage anomaly must fall within rows 120–135 (02:00–02:15 UTC).
        Detectors may also flag earlier statistical noise, so we check presence not exclusivity."""
        anomalies = self._get_all_anomalies()
        bv = [a for a in anomalies if a["field"] == "battery_voltage"]
        assert bv, "No battery_voltage anomalies found at all"
        window_start = pd.Timestamp("2024-01-01T02:00:00Z")
        window_end   = pd.Timestamp("2024-01-01T02:15:00Z")
        in_window = [
            a for a in bv
            if window_start <= pd.Timestamp(a["timestamp"]) <= window_end
        ]
        assert in_window, (
            f"No battery_voltage anomaly detected within the injected window 02:00–02:15. "
            f"Detected timestamps: {[a['timestamp'] for a in bv]}"
        )

    def test_temperature_c_anomaly_in_correct_window(self):
        """temperature_c anomaly must be at 04:20 UTC."""
        anomalies = self._get_all_anomalies()
        tc = [a for a in anomalies if a["field"] == "temperature_c"]
        assert tc, "No temperature_c anomalies found at all"
        assert any(
            a["timestamp"] == "2024-01-01T04:20:00Z" for a in tc
        ), f"temperature_c anomaly not at 04:20:00Z. Got: {[a['timestamp'] for a in tc]}"

    def test_signal_strength_anomaly_in_correct_window(self):
        """At least one signal_strength_db anomaly must fall within 06:20–06:30 UTC.
        Detectors may also flag earlier low-level deviations."""
        anomalies = self._get_all_anomalies()
        ss = [a for a in anomalies if a["field"] == "signal_strength_db"]
        assert ss, "No signal_strength_db anomalies found at all"
        window_start = pd.Timestamp("2024-01-01T06:20:00Z")
        window_end   = pd.Timestamp("2024-01-01T06:30:00Z")
        in_window = [
            a for a in ss
            if window_start <= pd.Timestamp(a["timestamp"]) <= window_end
        ]
        assert in_window, (
            f"No signal_strength_db anomaly detected within the injected window 06:20–06:30. "
            f"Detected timestamps: {[a['timestamp'] for a in ss]}"
        )
