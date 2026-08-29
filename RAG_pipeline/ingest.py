import os
import hashlib
import chromadb
from chromadb.utils import embedding_functions
import docx
from pypdf import PdfReader

# Import LangChain's Semantic Chunker and HuggingFace Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.embeddings import HuggingFaceEmbeddings

# 1. Resolve relative paths directly inside RAG_pipeline
src_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(src_dir, "data")
db_path = os.path.join(src_dir, "chroma_db")

# 2. Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"

hf_embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
semantic_splitter = SemanticChunker(
    hf_embeddings,
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=90.0
)

# 3. Persistent ChromaDB Client
client = chromadb.PersistentClient(path=db_path)
chroma_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_NAME
)

# Get or create collection without wiping previous entries
collection = client.get_or_create_collection(
    name="nasa_docs",
    embedding_function=chroma_embedding_fn  # pyright: ignore[reportArgumentType]
)

def get_file_hash(file_path):
    """Generates an MD5 hash of a file to detect content changes."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def extract_pdf_text(file_path):
    reader = PdfReader(file_path)
    text = [page.extract_text() for page in reader.pages if page.extract_text()]
    return "\n\n".join(text)

def extract_docx_text(file_path):
    doc = docx.Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

# 4. Read documents exclusively from 'data/' and incrementally process
if os.path.exists(data_dir):
    valid_extensions = ('.pdf', '.docx', '.txt')
    files = [
        f for f in os.listdir(data_dir) 
        if f.lower().endswith(valid_extensions) and not f.startswith('~$')
    ]

    for file_name in files:
        file_path = os.path.join(data_dir, file_name)
        file_hash = get_file_hash(file_path)

        # Check if this file is already in ChromaDB
        existing_records = collection.get(
            where={"source": file_name},
            include=["metadatas"]
        )

        # If file exists and hash matches, skip processing entirely
        if existing_records and existing_records["metadatas"]:
            stored_hash = existing_records["metadatas"][0].get("file_hash")
            if stored_hash == file_hash:
                print(f"Skipping '{file_name}' (Already ingested and unchanged).")
                continue
            else:
                print(f"File '{file_name}' modified. Updating existing entries...")
                collection.delete(where={"source": file_name})

        # Extract text for new/modified files
        print(f"Extracting & chunking new file: {file_name}...")
        if file_name.lower().endswith('.pdf'):
            full_text = extract_pdf_text(file_path)
        elif file_name.lower().endswith('.docx'):
            full_text = extract_docx_text(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_text = f.read()

        if full_text.strip():
            raw_chunks = semantic_splitter.split_text(full_text)
            
            documents, metadatas, ids = [], [], []
            for idx, chunk_text in enumerate(raw_chunks):
                if chunk_text.strip():
                    documents.append(chunk_text)
                    metadatas.append({
                        "source": file_name, 
                        "chunk_index": idx,
                        "file_hash": file_hash
                    })
                    ids.append(f"{file_name}_sem_chunk_{idx}")

            if documents:
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                print(f"Ingested {len(documents)} chunks for '{file_name}'.")

else:
    print(f"Directory not found: {data_dir}")

print(f"\nTotal documents currently in ChromaDB: {collection.count()}")