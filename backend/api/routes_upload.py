"""
POST /upload          — parse a user-supplied telemetry CSV, compute health score, cache session.
GET  /upload/sample   — run the same pipeline on the bundled sample_mission.csv.

Both endpoints return the same Canonical API Contract shape.
"""

import asyncio
import io
import time
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

import sessions
from anomaly.nominal_ranges import NOMINAL_RANGES
from knowledge_base.document_extractor import DocumentExtractionError, SUPPORTED_DOCUMENT_EXTENSIONS, extract_document_text

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB hard limit for CSV uploads

router = APIRouter()

REQUIRED_COLUMNS = [
    "timestamp",
    "battery_voltage",
    "temperature_c",
    "signal_strength_db",
    "solar_panel_efficiency_pct",
    "fuel_level_pct",
    "altitude_km",
    "velocity_kms",
    "mission_mode",
    "subsystem_status",
]

SAMPLE_CSV_PATH = Path(__file__).parent.parent / "datasets" / "sample_mission.csv"


def _format_ts(ts: pd.Timestamp) -> str:
    """Serialise a pandas Timestamp to the canonical 'YYYY-MM-DDTHH:MM:SSZ' string."""
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_response(df: pd.DataFrame) -> dict:
    """
    Given a validated, timestamp-parsed DataFrame, compute all response fields
    and return a dict matching the Canonical API Contract for POST /upload.
    """
    # ── Mission Health Score ──────────────────────────────────────────────────
    fractions = []
    for field, (lo, hi) in NOMINAL_RANGES.items():
        if field in df.columns:
            in_range = df[field].between(lo, hi).sum()
            fractions.append(in_range / len(df))
    health_score = int(round(sum(fractions) / len(fractions) * 100)) if fractions else 0

    # ── Session ───────────────────────────────────────────────────────────────
    session_id = uuid.uuid4().hex
    sessions.set_session(session_id, {
        "dataframe": df,
        "anomalies": None,
        "insights": None,
        "created_at": time.time(),
    })

    # ── Summary stats ─────────────────────────────────────────────────────────
    ts_col = df["timestamp"]  # already pd.Timestamp after parse
    time_range = {
        "start": _format_ts(ts_col.min()),
        "end":   _format_ts(ts_col.max()),
    }
    fields = [c for c in df.columns if c != "timestamp"]

    # ── Preview rows (first 10) ───────────────────────────────────────────────
    preview_df = df.head(10).copy()
    preview_df["timestamp"] = preview_df["timestamp"].apply(_format_ts)
    preview_rows = preview_df.to_dict(orient="records")

    return {
        "session_id":    session_id,
        "health_score":  health_score,
        "summary_stats": {
            "row_count":  len(df),
            "fields":     fields,
            "time_range": time_range,
        },
        "preview_rows": preview_rows,
    }


class _CsvParseError(Exception):
    """Carries a ready-made JSONResponse to return directly from the route."""
    def __init__(self, response: JSONResponse):
        self.response = response


def _parse_csv(raw_bytes: bytes) -> pd.DataFrame:
    """
    Decode bytes → parse CSV → validate columns → parse timestamp column.
    Raises _CsvParseError (wrapping a JSONResponse) on any validation failure.
    """
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _CsvParseError(JSONResponse(
            status_code=422,
            content={"error": {"code": "DECODE_ERROR", "message": str(exc)}},
        )) from exc

    df = pd.read_csv(io.StringIO(text))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise _CsvParseError(JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code":    "MISSING_COLUMNS",
                    "message": f"Required columns missing: {missing}",
                }
            },
        ))

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "FILE_TOO_LARGE", "message": "CSV must be 20 MB or smaller."}},
        )
    try:
        df = await asyncio.to_thread(_parse_csv, raw)
    except _CsvParseError as exc:
        return exc.response
    return await asyncio.to_thread(_build_response, df)


@router.get("/upload/sample")
async def upload_sample():
    raw = SAMPLE_CSV_PATH.read_bytes()
    try:
        df = await asyncio.to_thread(_parse_csv, raw)
    except _CsvParseError as exc:
        return exc.response
    return await asyncio.to_thread(_build_response, df)
