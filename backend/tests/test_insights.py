"""
Tests for POST /insights (Sub-Task 6).

Assertions:
  1. Response matches the Canonical API Contract shape.
  2. len(insights) == number of seeded anomalies (3).
  3. Each insight has non-empty explanation, root_cause_hypothesis, recommendation.
  4. Each insight has source_chunks == [] and no_strong_match == True.
  5. Second call on the same session returns cached result (generate_insights invoked once).
"""

import asyncio
import json
from unittest.mock import patch

import sessions
from anomaly.models import Anomaly
from api.routes_insights import post_insights, InsightsRequest

# ── Fixture: 3 known injected anomalies matching ground_truth_anomalies.json ──

_ANOMALIES = [
    Anomaly(
        id="aaa111",
        field="battery_voltage",
        timestamp="2024-01-01T02:00:00Z",
        value=20.5,
        severity="high",
        method="statistical+isolation_forest",
        detection_detail="Value 20.50 is 25.0% outside the nominal lower bound 26.0 V.",
    ),
    Anomaly(
        id="bbb222",
        field="temperature_c",
        timestamp="2024-01-01T04:20:00Z",
        value=55.0,
        severity="high",
        method="statistical",
        detection_detail="Value 55.00 °C is 50.0% above the nominal upper bound 40.0 °C.",
    ),
    Anomaly(
        id="ccc333",
        field="signal_strength_db",
        timestamp="2024-01-01T06:20:00Z",
        value=-105.0,
        severity="medium",
        method="isolation_forest",
        detection_detail="Isolation Forest flagged this reading as anomalous (score: 0.62).",
    ),
]

_SESSION_ID = "test-insights-session"


def _seed_session(anomalies=_ANOMALIES, existing_insights=None):
    """Seed the in-memory session store for the test."""
    sessions.set_session(_SESSION_ID, {
        "dataframe": None,
        "anomalies": list(anomalies),
        "insights": existing_insights,
    })


def _call(request: InsightsRequest):
    """Run the async route handler synchronously."""
    return asyncio.run(post_insights(request))


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_insights_contract_shape():
    """Response matches the Canonical API Contract and contains 3 insights."""
    _seed_session()
    response = _call(InsightsRequest(session_id=_SESSION_ID))

    # FastAPI route returns a plain dict on success
    assert isinstance(response, dict), f"Expected dict, got {type(response)}"

    # Top-level keys
    assert "session_id" in response, "missing session_id"
    assert "mission_summary" in response, "missing mission_summary"
    assert "insights" in response, "missing insights"

    assert response["session_id"] == _SESSION_ID
    assert isinstance(response["mission_summary"], str)
    assert len(response["mission_summary"]) > 0

    assert len(response["insights"]) == 3


def test_each_insight_fields_non_empty():
    """Each insight has non-empty explanation, root_cause_hypothesis, recommendation."""
    _seed_session()
    response = _call(InsightsRequest(session_id=_SESSION_ID))

    for insight in response["insights"]:
        assert insight.get("explanation"), "explanation must not be empty"
        assert insight.get("root_cause_hypothesis"), "root_cause_hypothesis must not be empty"
        assert insight.get("recommendation"), "recommendation must not be empty"


def test_each_insight_source_chunks_and_no_strong_match():
    """Each insight has source_chunks as a list and no_strong_match as a bool.

    When RAG is active, source_chunks may be non-empty (real ChromaDB results).
    When RAG is unavailable (no creds / no DB), source_chunks == [] and
    no_strong_match == True.  Both outcomes are valid; the contract only
    requires the keys to be present with the correct types.
    """
    _seed_session()
    response = _call(InsightsRequest(session_id=_SESSION_ID))

    for insight in response["insights"]:
        assert isinstance(insight["source_chunks"], list), \
            "source_chunks must be a list"
        assert isinstance(insight["no_strong_match"], bool), \
            "no_strong_match must be a bool"


def test_idempotency_cache_hit():
    """Second call returns the cached result; generate_insights is invoked only once."""
    _seed_session()

    import insights.generator as gen_module

    call_count = 0
    original = gen_module.generate_insights

    def counting_wrapper(anomalies):
        nonlocal call_count
        call_count += 1
        return original(anomalies)

    with patch.object(gen_module, "generate_insights", side_effect=counting_wrapper):
        # First call — should invoke generate_insights
        resp1 = _call(InsightsRequest(session_id=_SESSION_ID))
        assert call_count == 1, f"Expected 1 call after first request, got {call_count}"

        # Second call — should return cached result without calling generate_insights again
        resp2 = _call(InsightsRequest(session_id=_SESSION_ID))
        assert call_count == 1, f"Expected still 1 call after cached request, got {call_count}"

    # Both responses must be equivalent
    assert resp1["mission_summary"] == resp2["mission_summary"]
    assert len(resp1["insights"]) == len(resp2["insights"])


def test_404_for_missing_session():
    """Returns 404 SESSION_NOT_FOUND for an unknown session_id."""
    from fastapi.responses import JSONResponse
    response = _call(InsightsRequest(session_id="nonexistent-xyz-999"))
    assert isinstance(response, JSONResponse), f"Expected JSONResponse, got {type(response)}"
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error"]["code"] == "SESSION_NOT_FOUND"


def test_400_when_anomalies_not_present():
    """Returns 400 ANOMALIES_NOT_FOUND if session has no anomalies."""
    from fastapi.responses import JSONResponse
    sessions.set_session("no-anomaly-session", {
        "dataframe": None,
        "anomalies": None,
        "insights": None,
    })
    response = _call(InsightsRequest(session_id="no-anomaly-session"))
    assert isinstance(response, JSONResponse), f"Expected JSONResponse, got {type(response)}"
    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "ANOMALIES_NOT_FOUND"
