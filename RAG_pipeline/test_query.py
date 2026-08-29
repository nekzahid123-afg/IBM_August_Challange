import os
import chromadb
from chromadb.utils import embedding_functions

# Point to chroma_db in the root directory (one level up from src/)
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))

client = chromadb.PersistentClient(path=db_path)

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

collection = client.get_collection(
    name="nasa_docs",
    embedding_function=embedding_fn
)

def test_query(user_query, n_results=5):
    print(f"\n--- Searching for: '{user_query}' ---")
    results = collection.query(
        query_texts=[user_query],
        n_results=n_results
    )
    
    for idx, (doc, meta, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0])):
        print(f"\nMatch {idx + 1} (Source: {meta.get('source', 'N/A')}, Distance: {dist:.4f}):")
        print("-" * 50)
        print(doc[:300] + "...\n")

# Run test query
test_query("What are the peak power options for 6U market solutions?")