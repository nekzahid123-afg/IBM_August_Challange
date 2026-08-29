from retriever import retrieve_context
from prompt_builder import build_granite_prompt
from granite_client import query_granite

def generate_anomaly_insight(anomaly: dict) -> dict:
    # 1. Search vector database for relevant documentation
    search_query = f"{anomaly['field']} anomaly value {anomaly['value']}"
    retrieved_chunks = retrieve_context(query=search_query, top_k=3)

    # 2. Build structured prompt
    prompt = build_granite_prompt(anomaly, retrieved_chunks)

    # 3. Pass prompt to LLM
    llm_response = query_granite(prompt)

    # 4. Extract sources safely
    sources = []
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        sources.append({
            "source": metadata.get("source", chunk.get("source", "Unknown")),
            "page": metadata.get("page", chunk.get("page", "N/A")),
            "text": chunk.get("text", "")
        })

    return {
        "anomaly": anomaly,
        "llm_response": llm_response,
        "sources": sources
    }


if __name__ == "__main__":
    # TEST CASE: Anomaly NOT present in ChromaDB documentation
    unseen_anomaly = {
        "field": "plasma_containment_coil_impedance",
        "value": 487.9,
        "timestamp": "2026-08-22T16:00:00Z",
        "detection_method_explanation": "Spike detected beyond Isolation Forest threshold (Nominal: 120-150 Ohms)."
    }

    print("--- Running RAG Test for UNSEEN / NOT-IN-DATABASE Anomaly ---")
    result = generate_anomaly_insight(unseen_anomaly)

    print("\n[AI INSIGHT RESPONSE]:")
    print(result["llm_response"])
    print("\n[GROUNDED SOURCES RETRIEVED]:")
    for src in result["sources"]:
        print(f" - {src['source']} (Page {src['page']})")