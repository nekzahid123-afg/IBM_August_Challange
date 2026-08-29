import os
import chromadb
from chromadb.utils import embedding_functions

# 1. Resolve relative database path directly inside RAG_pipeline
src_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(src_dir, "chroma_db")

# 2. Embedding Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"

def get_vectorstore():
    """Returns the persistent ChromaDB collection for NASA documents."""
    client = chromadb.PersistentClient(path=db_path)
    
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME
    )
    
    collection = client.get_or_create_collection(
        name="nasa_docs",
        embedding_function=embedding_fn  # pyright: ignore[reportArgumentType]
    )
    return collection

def retrieve_context(query, top_k=3):
    """
    Queries ChromaDB and returns top_k matching document snippets 
    along with their source metadata.
    """
    collection = get_vectorstore()
    
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
    retrieved_chunks = []
    
    documents_result = results.get("documents")
    if documents_result and documents_result[0]:
        documents = documents_result[0]
        metadatas_result = results.get("metadatas")
        distances_result = results.get("distances")
        metadatas = metadatas_result[0] if metadatas_result else [{}] * len(documents)
        distances = distances_result[0] if distances_result else [0.0] * len(documents)
        
        for doc, meta, dist in zip(documents, metadatas, distances):
            retrieved_chunks.append({
                "content": doc,
                "metadata": meta,
                "distance": dist
            })
            
    return retrieved_chunks

if __name__ == "__main__":
    # Test execution when running retriever.py directly
    test_query = "What are the peak power options for 6U market solutions?"
    print(f"--- Running Test Query: '{test_query}' ---")
    chunks = retrieve_context(test_query, top_k=3)
    
    print(f"\nRetrieved {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("source", "Unknown")
        print(f"\n[{i}] Source: {source} (Distance: {chunk['distance']:.4f})")
        print(f"Content: {chunk['content'][:600]}...")