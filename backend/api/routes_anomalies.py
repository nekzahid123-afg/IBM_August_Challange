"""
GET /anomalies?session_id=<id>

Runs both detectors (statistical + Isolation Forest), deduplicates overlapping
detections by (field, timestamp), caches the result on the session, and returns
the Canonical API Contract shape.

Dedup rule (when both methods flag the same (field, timestamp)):
  - method   = "statistical+isolation_forest"
  - severity = max(stat, if) via SEVERITY_ORDER; tie → statistical wins
  - detection_detail = stat_detail + " | " + if_detail
  - id = statistical_anomaly.id  (IF id is discarded)
"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import sessions
from anomaly import statistical, isolation_forest
from anomaly.models import Anomaly, SEVERITY_ORDER

router = APIRouter()


def _dedup(stat_anomalies: list[Anomaly], if_anomalies: list[Anomaly]) -> list[Anomaly]:
    """
    Merge and dedup anomalies from both detectors.

    Groups by (field, timestamp). When both methods flag the same pair, merges
    into a single "statistical+isolation_forest" anomaly following the canonical rule.
    """
    from collections import defaultdict

    # key: (field, timestamp) → {"stat": Anomaly|None, "if": Anomaly|None}
    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {"stat": None, "if": None})

    for a in stat_anomalies:
        groups[(a.field, a.timestamp)]["stat"] = a

    for a in if_anomalies:
        groups[(a.field, a.timestamp)]["if"] = a

    merged: list[Anomaly] = []

    for (field, timestamp), pair in groups.items():
        stat = pair["stat"]
        ifo = pair["if"]

        if stat is not None and ifo is None:
            merged.append(stat)
        elif ifo is not None and stat is None:
            merged.append(ifo)
        else:
            # Both fired — merge
            stat_rank = SEVERITY_ORDER[stat.severity]
            if_rank = SEVERITY_ORDER[ifo.severity]
            # Tie → statistical wins (more directly explainable)
            if if_rank > stat_rank:
                severity = ifo.severity
            else:
                severity = stat.severity

            merged.append(Anomaly(
                id=stat.id,
                field=stat.field,
                timestamp=stat.timestamp,
                value=stat.value,
                severity=severity,
                method="statistical+isolation_forest",
                detection_detail=f"{stat.detection_detail} | {ifo.detection_detail}",
            ))

    return merged


@router.get("/anomalies")
async def get_anomalies(session_id: str):
    session = sessions.get_session(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "SESSION_NOT_FOUND", "message": f"Session '{session_id}' not found or expired."}},
        )

    # Return cached result if available
    if session.get("anomalies") is not None:
        return {
            "session_id": session_id,
            "anomalies": [a.model_dump() for a in session["anomalies"]],
        }

    df = session["dataframe"]

    def _detect():
        return statistical.detect(df), isolation_forest.detect(df)

    stat_anomalies, if_anomalies = await asyncio.to_thread(_detect)

    anomalies = _dedup(stat_anomalies, if_anomalies)

    # Sort by timestamp (ISO string lexicographic sort is equivalent to chronological)
    anomalies.sort(key=lambda a: a.timestamp)

    # Cache on session (update without resetting created_at)
    session["anomalies"] = anomalies
    sessions.set_session(session_id, session)

    return {
        "session_id": session_id,
        "anomalies": [a.model_dump() for a in anomalies],
    }
