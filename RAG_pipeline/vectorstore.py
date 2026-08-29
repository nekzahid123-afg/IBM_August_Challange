# src/vectorstore.py
import os
import chromadb
from chromadb.utils import embedding_functions


def get_vectorstore(db_path: str = "chroma_db"):
    """Initializes and returns a persistent ChromaDB client and collection."""
    # Ensure directory exists
    os.makedirs(db_path, exist_ok=True)

    client = chromadb.PersistentClient(path=db_path)

    # Use default sentence-transformer (all-MiniLM-L6-v2)
    emb_fn = (
        embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    )

    collection = client.get_or_create_collection(
        name="orbitlens_nasa_docs",
        embedding_function=emb_fn,
        metadata={"description": "NASA Subsystem & Operational Manuals"},
    )
    return collection


def ingest_chunks_to_chroma(chunks: list[dict], db_path: str = "chroma_db"):
    """Inserts a list of document chunks into ChromaDB."""
    collection = get_vectorstore(db_path)

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    # Batch insertion into ChromaDB
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(
        f"[SUCCESS] Successfully ingested {len(chunks)} chunks into ChromaDB!"
    )


if __name__ == "__main__":
    from loader import load_pdf
    from chunker import chunk_documents

    test_file = "data/nasa_cubesat_handbook.pdf"
    if os.path.exists(test_file):
        pages = load_pdf(test_file)
        chunks = chunk_documents(pages)
        ingest_chunks_to_chroma(chunks)
    else:
        print(
            f"[WARN] Place a PDF in '{test_file}' to test vector ingestion."
        )