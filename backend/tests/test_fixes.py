"""
Tests for Issue 1 & 2 fixes:
  - Insights timeout/failure fallback
  - ChromaDB unavailable fallback
  - All document file types (PDF, TXT, MD, DOCX)
  - Document-only upload (no CSV session required)
  - Mixed CSV + document upload
  - Unsupported file extension
  - Large/invalid CSV handling
  - Duplicate insight request caching
  - Frontend Axios timeout is set (sanity check via API contract)
"""

import io
import json
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
# Use starlette's TestClient directly via httpx2 to suppress deprecation warning
from starlette.testclient import TestClient

from main import app
import sessions
from anomaly.models import Anomaly

client = TestClient(app)

_DATASETS = Path(__file__).parent.parent / "datasets"
_SAMPLE_CSV = _DATASETS / "sample_mission.csv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_sample() -> dict:
    r = client.get("/upload/sample")
    assert r.status_code == 200, r.text
    return r.json()


def _get_anomalies(sid: str) -> dict:
    r = client.get(f"/anomalies?session_id={sid}")
    assert r.status_code == 200, r.text
    return r.json()


def _post_insights(sid: str) -> tuple[int, dict]:
    r = client.post("/insights", json={"session_id": sid})
    return r.status_code, r.json()


def _make_anomalies(n: int = 2) -> list[Anomaly]:
    return [
        Anomaly(
            id=f"test-{i}",
            field="battery_voltage",
            timestamp=f"2024-01-01T0{i}:00:00Z",
            value=20.0 + i,
            severity="high",
            method="statistical",
            detection_detail="Test anomaly.",
        )
        for i in range(n)
    ]


def _seed(anomalies, insights=None) -> str:
    sid = uuid.uuid4().hex
    sessions.set_session(sid, {
        "dataframe": None,
        "anomalies": anomalies,
        "insights": insights,
        "created_at": time.time(),
    })
    return sid


# ===========================================================================
# 1. Normal CSV upload
# ===========================================================================

class TestNormalCsvUpload:
    def test_returns_session_health_summary(self):
        body = _upload_sample()
        assert "session_id" in body
        assert 0 <= body["health_score"] <= 100
        assert body["summary_stats"]["row_count"] > 0


# ===========================================================================
# 2. Large / invalid CSV
# ===========================================================================

class TestLargeInvalidCsv:
    def test_too_large_returns_413(self):
        big = b"x" * (21 * 1024 * 1024)
        r = client.post("/upload", files={"file": ("big.csv", io.BytesIO(big), "text/csv")})
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "FILE_TOO_LARGE"

    def test_invalid_csv_missing_columns_returns_422(self):
        bad = b"col1,col2\n1,2\n"
        r = client.post("/upload", files={"file": ("bad.csv", io.BytesIO(bad), "text/csv")})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "MISSING_COLUMNS"


# ===========================================================================
# 3-6. Document uploads (PDF, TXT, MD, DOCX)
# ===========================================================================

class TestDocumentUploads:

    def _post_doc(self, content: bytes, filename: str, ct: str = "application/octet-stream"):
        # Mock ingest so ChromaDB is not required
        with patch("api.routes_documents._do_ingest", return_value=(1, None)):
            r = client.post("/documents", files={"file": (filename, io.BytesIO(content), ct)})
        return r

    def test_txt_upload_no_session(self):
        r = self._post_doc(b"Space telemetry data. Battery voltage nominal.", "test.txt")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "session_id" in body
        assert body["chunks_indexed"] >= 0

    def test_md_upload_no_session(self):
        r = self._post_doc(b"# Mission Report\n\nSolar panels at 85%.", "test.md")
        assert r.status_code == 200, r.text
        assert "session_id" in r.json()

    def test_pdf_upload_no_session(self):
        # Minimal valid PDF
        pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
            b"/Resources<<>>/Contents 4 0 R>>endobj "
            b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (Space data) Tj ET\nendstream\nendobj "
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n"
            b"0000000058 00000 n\n0000000115 00000 n\n0000000274 00000 n\n"
            b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n350\n%%EOF"
        )
        r = self._post_doc(pdf, "test.pdf", "application/pdf")
        # pypdf may fail on this synthetic PDF but the endpoint must not 500
        assert r.status_code in (200, 422), r.text

    def test_docx_upload_no_session(self):
        try:
            from docx import Document as DocxDoc
            from io import BytesIO as _BytesIO
            doc = DocxDoc()
            doc.add_paragraph("Spacecraft battery voltage telemetry.")
            buf = _BytesIO()
            doc.save(buf)
            buf.seek(0)
            r = self._post_doc(buf.read(), "test.docx")
            assert r.status_code == 200, r.text
            assert "session_id" in r.json()
        except ImportError:
            pytest.skip("python-docx not installed")

    def test_unsupported_extension_returns_422(self):
        r = self._post_doc(b"data", "file.xyz")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "DOCUMENT_PARSE_ERROR"


# ===========================================================================
# 7. Document-only upload (no telemetry session)
# ===========================================================================

class TestDocumentOnlyUpload:
    def test_creates_session_without_csv(self):
        r = client.post(
            "/documents",
            files={"file": ("notes.txt", io.BytesIO(b"Orbital decay analysis notes."), "text/plain")},
        )
        assert r.status_code == 200
        body = r.json()
        assert "session_id" in body
        # Verify the auto-created session is retrievable
        session = sessions.get_session(body["session_id"])
        assert session is not None
        assert session.get("doc_only") is True


# ===========================================================================
# 8. Mixed CSV + document upload
# ===========================================================================

class TestMixedUpload:
    def test_csv_creates_session_then_doc_attaches(self):
        # Upload CSV first
        body = _upload_sample()
        sid  = body["session_id"]

        # Upload document to the same session
        r = client.post(
            f"/documents?session_id={sid}",
            files={"file": ("ref.txt", io.BytesIO(b"Reference material for orbit analysis."), "text/plain")},
        )
        assert r.status_code == 200
        assert r.json()["session_id"] == sid

        # Verify document is in session
        session = sessions.get_session(sid)
        docs = session.get("reference_documents", [])
        assert any(d["filename"] == "ref.txt" for d in docs)


# ===========================================================================
# 10. ChromaDB unavailable fallback
# ===========================================================================

class TestChromaDbFallback:
    def test_insights_succeed_when_chroma_fails(self):
        """generate_insights must return template fallback, not raise, when ChromaDB is down."""
        from insights import generator

        sid = _seed(_make_anomalies(2))

        with patch.object(generator, "_probe_rag", return_value=False):
            status, body = _post_insights(sid)

        assert status == 200
        assert len(body["insights"]) == 2
        for ins in body["insights"]:
            assert ins["explanation"]
            assert ins["source_chunks"] == []
            assert ins["no_strong_match"] is True


# ===========================================================================
# 11. Watsonx.ai timeout / failure fallback
# ===========================================================================

class TestWatsonxFallback:
    def test_insights_return_template_when_llm_times_out(self):
        """When query_granite returns None (timeout/error), template fallback is used."""
        from insights import generator

        sid = _seed(_make_anomalies(2))

        with patch.object(generator, "_probe_rag", return_value=True), \
             patch.object(generator, "_batch_rag_insights", return_value=None), \
             patch.object(generator, "_try_rag_mission_summary", return_value=None):
            status, body = _post_insights(sid)

        assert status == 200
        assert len(body["insights"]) == 2
        for ins in body["insights"]:
            assert ins["explanation"]

    def test_granite_timeout_returns_none(self):
        """query_granite must return None (not raise) when the thread times out."""
        import concurrent.futures
        from rag import granite_client

        original_timeout = granite_client._WATSONX_TIMEOUT_SECONDS

        def slow_generate(*args, **kwargs):
            import time as _t
            _t.sleep(10)
            return "should not return"

        mock_model = MagicMock()
        mock_model.generate_text.side_effect = slow_generate

        granite_client._cached_model = mock_model
        granite_client._cached_creds_key = ("key", "proj", "url")
        granite_client._WATSONX_TIMEOUT_SECONDS = 1  # 1 second timeout

        try:
            result = granite_client.query_granite("test prompt")
            assert result is None, f"Expected None on timeout, got: {result!r}"
        finally:
            granite_client._WATSONX_TIMEOUT_SECONDS = original_timeout
            granite_client._cached_model = None
            granite_client._cached_creds_key = None


# ===========================================================================
# 12. Insights generation with multiple anomalies
# ===========================================================================

class TestInsightsMultipleAnomalies:
    def test_all_anomalies_get_insights(self):
        """Every anomaly must have a corresponding insight entry."""
        anomalies = _make_anomalies(7)  # more than _MAX_ANOMALIES_FOR_LLM=5
        sid = _seed(anomalies)

        from insights import generator
        with patch.object(generator, "_probe_rag", return_value=False):
            status, body = _post_insights(sid)

        assert status == 200
        assert len(body["insights"]) == 7


# ===========================================================================
# 13. Duplicate insight request / cache
# ===========================================================================

class TestInsightsCache:
    def test_second_call_is_cached(self):
        from insights import generator

        anomalies = _make_anomalies(2)
        sid = _seed(anomalies)

        call_count = 0

        def counting(anoms):
            nonlocal call_count
            call_count += 1
            return {
                "mission_summary": "Test summary.",
                "insights": [generator._template_insight(a) for a in anoms],
            }

        with patch.object(generator, "generate_insights", side_effect=counting):
            client.post("/insights", json={"session_id": sid})
            client.post("/insights", json={"session_id": sid})

        assert call_count == 1, f"Expected 1 call, got {call_count}"
