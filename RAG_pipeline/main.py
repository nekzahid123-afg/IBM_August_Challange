import os
from loader import PDFParserLoader
from chuker import DocumentChunker
from vectorstore import ChromaStore
from retriever import Retriever

def run_pipeline(pdf_path: str, pages_to_parse: list = None):
    """
    Executes the ingestion and retrieval pipeline.
    
    :param pdf_path: Path to the input PDF file.
    :param pages_to_parse: Optional list of 0-based page numbers to extract.
    """
    # 1. Check if the PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at '{pdf_path}'")
        return

    # 2. Parse selected PDF pages to Markdown using PyMuPDF4LLM
    print("Parsing PDF...")
    if pages_to_parse:
        human_readable_pages = [p + 1 for p in pages_to_parse]
        print(f"Targeting PDF page numbers: {human_readable_pages}")
    else:
        print("Targeting entire PDF document...")

    loader = PDFParserLoader(output_format="markdown")
    markdown_content = loader.load(pdf_path, pages=pages_to_parse)

    # Save intermediate extracted Markdown file for inspection
    output_md_path = os.path.join(os.path.dirname(__file__), "..", "data", "extracted_output.md")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"Extracted Markdown saved to: {output_md_path}")

    # 3. Chunk the extracted Markdown Content
    print("Chunking document content...")
    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=100)
    
    if hasattr(chunker, 'split_text'):
        chunks = chunker.split_text(markdown_content)
    elif hasattr(chunker, 'chunk'):
        chunks = chunker.chunk(markdown_content)
    else:
        chunks = chunker.process(markdown_content)

    print(f"Total created chunks: {len(chunks)}")

    # 4. Store Vectors into ChromaDB
    print("Storing embeddings in ChromaDB...")
    db_path = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    vector_db = ChromaStore(collection_name="orbitlens_rag", persist_directory=db_path)
    
    if hasattr(vector_db, 'add_documents'):
        vector_db.add_documents(chunks)
    elif hasattr(vector_db, 'add_texts'):
        vector_db.add_texts(chunks)

    # 5. Query with Retriever
    print("Initializing Retriever...")
    retriever = Retriever(vector_db=vector_db)
    query = "What is the main objective of this project?"
    
    results = retriever.search(query, top_k=3) if hasattr(retriever, 'search') else retriever.retrieve(query)
    
    print("\n--- Search Results ---")
    print(results)


if __name__ == "__main__":
    # Specify the target PDF path in the data folder
    target_pdf = os.path.join(os.path.dirname(__file__), "..", "data", "sample.pdf")
    
    # --------------------------------------------------------------------------
    # PAGE SELECTION OPTIONS (Remember: PyMuPDF uses 0-based page indexing)
    # --------------------------------------------------------------------------
    
    # Option A: Parse continuous range (e.g., Pages 10 through 25 in the PDF)
    # selected_pages = list(range(9, 25))
    
    # Option B: Parse specific individual pages (e.g., Page 1, Page 5, Page 12)
    selected_pages = [0, 4, 11]
    
    # Option C: Parse ALL pages in document (Set to None)
    # selected_pages = None
    
    run_pipeline(target_pdf, pages_to_parse=selected_pages)