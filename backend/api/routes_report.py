"""
GET /report?session_id=<id>&format=<markdown|pdf>

Generates and streams the mission report.

Behaviour:
  - 404 SESSION_NOT_FOUND    if session does not exist or has expired.
  - 404 INSIGHTS_NOT_FOUND   if POST /insights has not been called yet.
  - Always generates Markdown first.
  - If format=pdf, attempts generate_pdf(); falls back to Markdown if it returns None.
  - Fallback filename rule: when falling back from PDF to Markdown, the Content-Disposition
    filename and media_type both reflect .md / text/markdown — never serve Markdown bytes
    under a .pdf filename or application/pdf content-type.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response, StreamingResponse

import sessions
from report.report_generator import generate_markdown, generate_pdf

router = APIRouter()


@router.get("/report")
async def get_report(session_id: str, format: str = "markdown"):
    # ── Session lookup ────────────────────────────────────────────────────────
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

    # ── Insights guard ────────────────────────────────────────────────────────
    insights = session.get("insights")
    if insights is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "INSIGHTS_NOT_FOUND",
                    "message": "Generate insights first by calling POST /insights",
                }
            },
        )

    # ── Generate Markdown (always) ────────────────────────────────────────────
    md_str = generate_markdown(session_id, session, insights)

    # ── PDF path ──────────────────────────────────────────────────────────────
    if format.lower() == "pdf":
        pdf_bytes = generate_pdf(md_str)
        if pdf_bytes is not None:
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="mission_report_{session_id}.pdf"'
                    )
                },
            )
        # Fall back to Markdown — filename and media_type must also fall back
        # Never serve Markdown bytes under a .pdf filename

    # ── Markdown response (default + PDF fallback) ────────────────────────────
    return StreamingResponse(
        iter([md_str.encode("utf-8")]),
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mission_report_{session_id}.md"'
            )
        },
    )
