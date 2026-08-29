"""
Prompt builder for OrbitLens RAG pipeline.

Formats an anomaly payload and retrieved knowledge chunks into a structured,
grounded prompt for the LLM (ibm/granite-4-h-small via watsonx.ai).
"""

from __future__ import annotations


def build_granite_prompt(anomaly: dict, retrieved_chunks: list[dict]) -> str:
    """
    Build a grounded LLM prompt from anomaly data and ChromaDB context chunks.

    Parameters
    ----------
    anomaly : dict
        Keys: field, value, timestamp, detection_detail (or detection_method_explanation)
    retrieved_chunks : list[dict]
        Each item: {"text": str, "metadata": {"source": str, "page": str|int, ...}}

    Returns
    -------
    str
        Fully formatted prompt ready to send to the LLM.
    """
    context_text = ""
    for idx, chunk in enumerate(retrieved_chunks):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", chunk.get("source", "Telemetry Doc"))
        page   = metadata.get("page", chunk.get("page", "N/A"))
        text   = chunk.get("text", "")
        context_text += f"\n[Source {idx + 1}: {source} (Page {page})]\n{text}\n"

    detection_note = anomaly.get("detection_detail") or anomaly.get(
        "detection_method_explanation", ""
    )

    prompt = f"""You are an expert spacecraft systems analyst. \
Analyze the following telemetry anomaly using ONLY the provided reference documentation context.

--- TELEMETRY ANOMALY DETAILS ---
Field:              {anomaly.get('field', 'unknown')}
Observed Value:     {anomaly.get('value', 'unknown')}
Timestamp:          {anomaly.get('timestamp', 'unknown')}
Detection Context:  {detection_note}

--- REFERENCE DOCUMENTATION CONTEXT ---
{context_text.strip() if context_text.strip() else "No specific document context found."}

--- INSTRUCTIONS ---
Based strictly on the telemetry details and reference documentation context provided above, \
provide your analysis in EXACTLY the following format (do not deviate):

1) Plain-language explanation:
<one short paragraph explaining what this telemetry value means and why it is anomalous>

2) Likely root cause:
<one short paragraph identifying the most probable root cause based on the documentation>

3) Recommended action:
<one short paragraph of specific corrective actions for flight controllers>

Keep your response factual, concise, and grounded in the provided documentation context."""

    return prompt


def parse_llm_response(llm_text: str) -> dict[str, str]:
    """
    Parse the structured LLM response into explanation, root_cause, recommendation.

    Expected format:
        1) Plain-language explanation:\n<text>\n\n
        2) Likely root cause:\n<text>\n\n
        3) Recommended action:\n<text>

    Falls back to splitting on double-newlines if the numbered format is absent.
    """
    import re

    explanation   = ""
    root_cause    = ""
    recommendation = ""

    # Try numbered-section parsing first
    p1 = re.search(
        r"1\)\s*[^\n]*explanation[^:]*:\s*(.*?)(?=2\)|\Z)",
        llm_text, re.IGNORECASE | re.DOTALL
    )
    p2 = re.search(
        r"2\)\s*[^\n]*root cause[^:]*:\s*(.*?)(?=3\)|\Z)",
        llm_text, re.IGNORECASE | re.DOTALL
    )
    p3 = re.search(
        r"3\)\s*[^\n]*(?:recommended|action)[^:]*:\s*(.*?)$",
        llm_text, re.IGNORECASE | re.DOTALL
    )

    if p1:
        explanation = p1.group(1).strip()
    if p2:
        root_cause = p2.group(1).strip()
    if p3:
        recommendation = p3.group(1).strip()

    # Fallback: split on double-newlines and assign in order
    if not (explanation and root_cause and recommendation):
        parts = [s.strip() for s in llm_text.split("\n\n") if s.strip()]
        if len(parts) >= 3:
            explanation    = explanation    or parts[0]
            root_cause     = root_cause     or parts[1]
            recommendation = recommendation or parts[2]
        elif len(parts) == 2:
            explanation    = explanation    or parts[0]
            root_cause     = root_cause     or parts[1]
            recommendation = recommendation or parts[1]
        elif parts:
            explanation    = explanation    or parts[0]
            root_cause     = root_cause     or parts[0]
            recommendation = recommendation or parts[0]

    # Final safety — never return empty strings
    _fallback = llm_text.strip() or "See telemetry data for details."
    return {
        "explanation":           explanation    or _fallback,
        "root_cause_hypothesis": root_cause     or _fallback,
        "recommendation":        recommendation or _fallback,
    }
