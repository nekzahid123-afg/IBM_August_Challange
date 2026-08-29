"""Reference-document ingestion — extracts text AND indexes embeddings into ChromaDB.

session_id is optional. When omitted a document-only session is created so
PDF/TXT/MD/DOCX uploads work without uploading a CSV first.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import JSONResponse

import sessions
from knowledge_base.document_extractor import DocumentExtractionError, extract_document_text

router = APIRouter()

_CHUNK_SIZE    = 800
_CHUNK_OVERLAP = 150


def _chunk_text(text: str, filename: str) -> list[dict]:
    file_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    chunks: list[dict] = []
    step  = max(1, _CHUNK_SIZE - _CHUNK_OVERLAP)
    words = text.split()
    if not words:
        return chunks
    i, idx = 0, 0
    while i < len(words):
        chunk_words = words[i : i + _CHUNK_SIZE]
        chunk_text  = " ".join(chunk_words).strip()
        if chunk_text:
            chunks.append({
                "id":       f"{file_hash}_{filename}_{idx}",
                "text":     chunk_text,
                "metadata": {"source": filename, "page": str(idx + 1)},
            })
        i   += step
        idx += 1
    return chunks


def _do_ingest(text: str, filename: str) -> tuple[int, str | None]:
    """Blocking: chunk text and add to ChromaDB. Returns (chunks_indexed, error_msg|None)."""
    try:
        from rag.retriever import ingest_text_chunks
        chunks = _chunk_text(text, filename)
        if chunks:
            return ingest_text_chunks(chunks), None
        return 0, None
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


@router.post("/documents")
async def upload_reference_document(
    file: UploadFile = File(...),
    session_id: str | None = Query(default=None),
):
    """Attach a reference document (PDF, DOCX, TXT, MD) to a session and index it.

    If session_id is omitted a lightweight document-only session is created
    so this endpoint works without uploading a CSV first.
    """
    # ── Resolve / create session ──────────────────────────────────────────────
    if session_id:
        session = sessions.get_session(session_id)
        if session is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found or expired."}},
            )
    else:
        # Auto-create a document-only session
        session_id = uuid.uuid4().hex
        session    = {
            "dataframe":  None,
            "anomalies":  None,
            "insights":   None,
            "created_at": time.time(),
            "doc_only":   True,
        }
        sessions.set_session(session_id, session)

    raw_bytes = await file.read()
    filename  = file.filename or "reference"

    # ── Extract text (sync but fast for most docs, offload for safety) ───────
    try:
        text = await asyncio.to_thread(extract_document_text, filename, raw_bytes)
    except DocumentExtractionError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "DOCUMENT_PARSE_ERROR", "message": str(exc)}},
        )

    # ── Store in session ──────────────────────────────────────────────────────
    session.setdefault("reference_documents", []).append({"filename": filename, "text": text})
    sessions.set_session(session_id, session)

    # ── Index into ChromaDB (offloaded — never blocks event loop) ─────────────
    chunks_indexed, index_error = await asyncio.to_thread(_do_ingest, text, filename)

    response: dict = {
        "session_id":           session_id,
        "filename":             filename,
        "extracted_characters": len(text),
        "chunks_indexed":       chunks_indexed,
        "message": (
            f"Document indexed: {chunks_indexed} chunk(s) added to ChromaDB."
            if chunks_indexed
            else "Document attached (ChromaDB indexing unavailable; fallback mode active)."
        ),
    }
    if index_error:
        response["index_warning"] = index_error
    return response
