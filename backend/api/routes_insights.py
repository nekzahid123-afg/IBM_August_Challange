"""
POST /insights

Generate AI-style insights for every anomaly in a session.

Behaviour:
  - 404 SESSION_NOT_FOUND   if session does not exist or has expired.
  - 400 ANOMALIES_NOT_FOUND if anomaly detection has not been run yet (session["anomalies"]
                             is None or empty).  This edge case is unreachable via the normal
                             UI flow but must be handled for direct API calls (Swagger UI).
  - Idempotency gate: if session["insights"] is already populated, return the cached result
    immediately — no re-generation.
  - On any unexpected error during generation: 500 with a safe message.
"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import sessions
from insights import generator

router = APIRouter()


class InsightsRequest(BaseModel):
    session_id: str


@router.post("/insights")
async def post_insights(body: InsightsRequest):
    session_id = body.session_id

    # ── Session lookup ───────────────────────────────────────────────────────
    session = sessions.get_session(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session '{session_id}' not found or expired.",
                }
            },
        )

    # ── Idempotency gate ─────────────────────────────────────────────────────
    if session.get("insights") is not None:
        cached = dict(session["insights"])
        cached["session_id"] = session_id
        return cached

    # ── Anomalies guard ──────────────────────────────────────────────────────
    anomalies = session.get("anomalies")
    if not anomalies:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "ANOMALIES_NOT_FOUND",
                    "message": "Run anomaly detection first by calling GET /anomalies",
                }
            },
        )

    # ── Generate insights (offloaded to thread — never blocks event loop) ────
    try:
        result = await asyncio.to_thread(generator.generate_insights, anomalies)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INSIGHT_GENERATION_FAILED",
                    "message": "Insight generation failed. Please retry.",
                    "detail": str(exc),
                }
            },
        )

    # Attach session_id, cache on session, return
    result["session_id"] = session_id
    session["insights"] = result
    sessions.set_session(session_id, session)

    return result
