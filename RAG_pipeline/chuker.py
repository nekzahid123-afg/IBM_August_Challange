# src/chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(
    pages: list[dict], chunk_size: int = 800, chunk_overlap: int = 150
) -> list[dict]:
    """Splits loaded pages into smaller semantic chunks with inherited metadata."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    chunk_counter = 0

    for page in pages:
        page_text = page["text"]
        page_meta = page["metadata"]

        raw_chunks = text_splitter.split_text(page_text)

        for chunk_text in raw_chunks:
            chunk_counter += 1
            chunks.append(
                {
                    "id": f"{page_meta['source']}_p{page_meta['page']}_c{chunk_counter}",
                    "text": chunk_text,
                    "metadata": {
                        "source": page_meta["source"],
                        "page": page_meta["page"],
                        "chunk_id": chunk_counter,
                    },
                }
            )

    return chunks


if __name__ == "__main__":
    from loader import load_pdf

    test_file = "data/nasa_cubesat_handbook.pdf"
    try:
        pages = load_pdf(test_file)
        chunks = chunk_documents(pages)
        print(
            f"[SUCCESS] Generated {len(chunks)} chunks from {len(pages)} pages."
        )
        if chunks:
            print(f"Sample Chunk 1 ID: {chunks[0]['id']}")
            print(f"Sample Chunk 1 Text:\n{chunks[0]['text'][:150]}...")
    except Exception as e:
        print(f"[ERROR] {e}")