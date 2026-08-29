def build_granite_prompt(anomaly: dict, retrieved_chunks: list) -> str:
    """
    Formats the anomaly payload and retrieved knowledge chunks into a 
    structured, grounded prompt for the LLM.
    """
    context_text = ""
    for idx, chunk in enumerate(retrieved_chunks):
        # Extract metadata dictionary safely
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", chunk.get("source", "Telemetry Doc"))
        page = metadata.get("page", chunk.get("page", "N/A"))
        text = chunk.get("text", "")
        
        context_text += f"\n[Source {idx+1}: {source} (Page {page})]\n{text}\n"

    prompt = f"""You are an expert spacecraft system analyst. Analyze the following telemetry anomaly using ONLY the provided reference documentation context.

--- TELEMETRY ANOMALY DETAILS ---
Field: {anomaly.get('field')}
Observed Value: {anomaly.get('value')}
Timestamp: {anomaly.get('timestamp')}
Detection Context: {anomaly.get('detection_method_explanation')}

--- REFERENCE DOCUMENTATION CONTEXT ---
{context_text if context_text.strip() else "No specific document context found."}

--- INSTRUCTIONS ---
Based strictly on the telemetry details and reference documentation context provided above, provide:
1) A clear, plain-language explanation of what this telemetry value means.
2) The likely root cause based on the documentation.
3) Specific recommended corrective actions for flight controllers.

Keep your response factual, concise, and grounded in the provided documentation context."""

    return prompt