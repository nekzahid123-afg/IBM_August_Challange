"""
Canonical Anomaly Object Schema.

Single source of truth — import this model everywhere anomaly data is produced or consumed.
Do NOT define inline anomaly dicts anywhere else in the codebase.
"""

from typing import Literal

from pydantic import BaseModel


class Anomaly(BaseModel):
    id: str                   # uuid4().hex, assigned at detection time
    field: str                # telemetry column name, e.g. "battery_voltage"
    timestamp: str            # ISO 8601 UTC, e.g. "2024-01-01T02:00:00Z"
    value: float              # raw value at the flagged point
    severity: Literal["high", "medium", "low"]
    method: Literal["statistical", "isolation_forest", "statistical+isolation_forest"]
    detection_detail: str     # human-readable basis; used in insight generation and UI tooltip


SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
