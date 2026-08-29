"""
Mission report generator.

generate_markdown() — builds a structured Markdown string from session data and
                      cached insights.
generate_pdf()      — optionally renders Markdown → PDF via WeasyPrint.
                      Returns None on any import or rendering failure so the
                      caller can silently fall back to Markdown.
"""

from __future__ import annotations


def generate_markdown(session_id: str, session: dict, insights: dict) -> str:
    """
    Build the full mission report as a Markdown string.

    Parameters
    ----------
    session_id : str
        The session identifier (used in the heading).
    session : dict
        The session dict from the store; must contain 'dataframe' and 'anomalies'.
    insights : dict
        The cached insights dict (from POST /insights); must contain
        'mission_summary' and 'insights'.
    """
    df = session.get("dataframe")
    anomalies = session.get("anomalies") or []
    insight_list = insights.get("insights") or []
    mission_summary = insights.get("mission_summary", "")

    # ── Mission Overview ──────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"# OrbitLens Mission Report — Session `{session_id}`\n")
    lines.append("## Mission Overview\n")

    if df is not None and not df.empty:
        row_count = len(df)
        # Derive time range from the 'timestamp' column if present
        if "timestamp" in df.columns:
            try:
                ts_sorted = df["timestamp"].dropna().sort_values()
                time_range = f"{ts_sorted.iloc[0]} — {ts_sorted.iloc[-1]}"
            except Exception:  # noqa: BLE001
                time_range = "N/A"
        else:
            time_range = "N/A"
    else:
        row_count = 0
        time_range = "N/A"

    # Compute health score: 100 minus a penalty per severity
    severity_penalty = {"high": 15, "medium": 5, "low": 2}
    penalty = sum(severity_penalty.get(getattr(a, "severity", "low"), 2) for a in anomalies)
    health_score = max(0, 100 - penalty)

    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Health Score | {health_score} / 100 |")
    lines.append(f"| Total Rows | {row_count} |")
    lines.append(f"| Time Range | {time_range} |")
    lines.append(f"| Anomalies Detected | {len(anomalies)} |")
    lines.append("")

    # ── Detected Anomalies ────────────────────────────────────────────────────
    lines.append("## Detected Anomalies\n")
    if anomalies:
        lines.append("| Field | Timestamp | Value | Severity | Method |")
        lines.append("|---|---|---|---|---|")
        for a in anomalies:
            lines.append(
                f"| {a.field} | {a.timestamp} | {a.value} "
                f"| {a.severity} | {a.method} |"
            )
    else:
        lines.append("No anomalies detected.")
    lines.append("")

    # ── AI Explanations ───────────────────────────────────────────────────────
    lines.append("## AI Explanations\n")

    # Build anomaly lookup by id for field/timestamp context in headings
    anomaly_map: dict = {}
    for a in anomalies:
        anomaly_map[a.id] = a

    for insight in insight_list:
        anomaly = anomaly_map.get(insight.get("anomaly_id"))
        if anomaly:
            heading = f"{anomaly.field.replace('_', ' ').title()} — {anomaly.timestamp}"
        else:
            heading = f"Anomaly {insight.get('anomaly_id', '')}"

        lines.append(f"### {heading}\n")
        lines.append(insight.get("explanation", ""))
        lines.append("")
        lines.append(f"**Hypothesis:** {insight.get('root_cause_hypothesis', '')}")
        lines.append("")
        lines.append(f"**Recommended Action:** {insight.get('recommendation', '')}")
        lines.append("")

        # Only add Sources section if source_chunks is non-empty
        source_chunks = insight.get("source_chunks") or []
        if source_chunks:
            lines.append("**Sources:**")
            for chunk in source_chunks:
                lines.append(f"- {chunk}")
            lines.append("")

    # ── Mission Summary ───────────────────────────────────────────────────────
    lines.append("## Mission Summary\n")
    lines.append(mission_summary)
    lines.append("")

    # ── Appendix — Anomaly Detection Details ──────────────────────────────────
    lines.append("## Appendix — Anomaly Detection Details\n")
    if anomalies:
        for a in anomalies:
            lines.append(f"**{a.field} @ {a.timestamp}:** {a.detection_detail}")
            lines.append("")
    else:
        lines.append("No anomaly detection details available.")
        lines.append("")

    return "\n".join(lines)


def generate_pdf(markdown_str: str) -> bytes | None:
    """
    Render a Markdown string to PDF bytes via WeasyPrint.

    Returns None on any failure (missing system libraries, import error, etc.)
    so the caller can fall back to Markdown silently.
    """
    try:
        import markdown as md_lib
        html = md_lib.markdown(markdown_str)
    except Exception:  # noqa: BLE001
        return None

    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except Exception:  # noqa: BLE001
        return None
