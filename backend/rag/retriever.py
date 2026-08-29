"""
ChromaDB vector retriever for OrbitLens RAG pipeline.

Collection: nasa_docs  (populated from RAG_pipeline/chroma_db)
Embedding:  all-MiniLM-L6-v2  (SentenceTransformer — runs locally, no API key required)

The collection client and embedding function are created once (module-level singleton)
so the 200 MB SentenceTransformer model is not reloaded on every retrieval call.
"""

from __future__ import annotations

import os
from pathlib import Path

_THIS_DIR    = Path(__file__).parent   # backend/rag/
_BACKEND_DIR = _THIS_DIR.parent        # backend/
_REPO_ROOT   = _BACKEND_DIR.parent    # workspace root

# Primary: RAG_pipeline/chroma_db — 3,997 NASA embeddings
_CHROMA_DB_PATH = str(_REPO_ROOT / "RAG_pipeline" / "chroma_db")
# Fallback: root chroma_db
_FALLBACK_PATH  = str(_REPO_ROOT / "chroma_db")

CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", _CHROMA_DB_PATH)

# ── Singleton: built once, reused for every query ────────────────────────────
_collection = None


def _get_collection():
    """Return the cached ChromaDB collection, initialising once on first call."""
    global _collection  # noqa: PLW0603
    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.utils import embedding_functions

        db_path = CHROMA_DB_PATH
        if not os.path.exists(db_path) and os.path.exists(_FALLBACK_PATH):
            db_path = _FALLBACK_PATH

        client = chromadb.PersistentClient(path=db_path)
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        for name in ("nasa_docs", "orbitlens_nasa_docs"):
            try:
                _collection = client.get_collection(name=name, embedding_function=emb_fn)
                return _collection
            except Exception:
                continue
        _collection = client.get_or_create_collection(
            name="nasa_docs", embedding_function=emb_fn
        )
        return _collection
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ChromaDB initialisation failed: {exc}") from exc


def retrieve_context(query: str, top_k: int = 3) -> list[dict]:
    """
    Query ChromaDB and return up to `top_k` relevant text chunks.

    Each item in the returned list has the shape expected by prompt_builder.py:
        {
            "text":     str,
            "metadata": {"source": str, "page": str|int, ...},
            "distance": float,   # lower = more similar
        }

    Returns an empty list on any retrieval failure so callers degrade gracefully.
    """
    try:
        collection = _get_collection()
        n = min(top_k, collection.count())
        if n <= 0:
            return []
        results = collection.query(query_texts=[query], n_results=n)
        chunks: list[dict] = []
        if results and results.get("documents") and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunks.append({
                    "text":     doc,
                    "metadata": meta or {},
                    "distance": dist,
                })
        return chunks
    except Exception:  # noqa: BLE001
        return []


def ingest_text_chunks(
    chunks: list[dict],
    *,
    collection_name: str = "nasa_docs",
) -> int:
    """
    Insert pre-built text chunks into the ChromaDB collection.

    Each dict in `chunks` must contain:
        id        str   — unique document chunk identifier
        text      str   — raw chunk text
        metadata  dict  — {"source": str, "page": str, ...}

    Returns the number of chunks successfully inserted.
    Raises RuntimeError if ChromaDB is unavailable.
    """
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        db_path = CHROMA_DB_PATH
        os.makedirs(db_path, exist_ok=True)

        client = chromadb.PersistentClient(path=db_path)
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_or_create_collection(
            name=collection_name, embedding_function=emb_fn
        )

        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ChromaDB ingestion failed: {exc}") from exc
