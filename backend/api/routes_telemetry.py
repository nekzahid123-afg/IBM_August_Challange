"""
GET /telemetry?session_id=<id>

Returns all parsed telemetry rows for the session, serialised as JSON records
with timestamps in the canonical "YYYY-MM-DDTHH:MM:SSZ" format.

Kept separate from routes_upload.py to maintain separation of concerns:
upload/parse logic lives in routes_upload.py; retrieval lives here.
"""

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import sessions

router = APIRouter()


def _format_ts(ts: pd.Timestamp) -> str:
    """Serialise a pandas Timestamp to the canonical 'YYYY-MM-DDTHH:MM:SSZ' string."""
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/telemetry")
async def get_telemetry(session_id: str):
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

    df: pd.DataFrame = session["dataframe"]

    # Serialise all rows; convert timestamp column to canonical ISO string.
    serialised = df.copy()
    serialised["timestamp"] = serialised["timestamp"].apply(_format_ts)
    rows = serialised.to_dict(orient="records")

    return {"session_id": session_id, "rows": rows}
