"""
Insight generator — live RAG execution with ChromaDB + watsonx.ai.

Performance fixes applied:
- All heavy work (ChromaDB + LLM) runs in a ThreadPoolExecutor so the async
  event loop is never blocked.
- A single batched LLM call replaces N+1 per-anomaly calls.
- Anomaly count is capped before LLM work to keep response time bounded.
- Template fallback is always instant (no network call).
"""

from __future__ import annotations

import concurrent.futures
from typing import Any

from anomaly.models import Anomaly, SEVERITY_ORDER

# Maximum anomalies sent to the LLM in one batch. Keeps prompt size and
# latency bounded even for large uploads.
_MAX_ANOMALIES_FOR_LLM = 5

# ---------------------------------------------------------------------------
# Template fallbacks (instant — no network)
# ---------------------------------------------------------------------------

_URGENCY = {"low": "minor deviation", "medium": "significant deviation", "high": "critical deviation"}


def _fallback_explanation(a: Anomaly) -> str:
    return (
        f"{a.field.replace('_', ' ').title()} recorded a {_URGENCY.get(a.severity, 'deviation')} "
        f"of {a.value} at {a.timestamp}. {a.detection_detail}."
    )


def _fallback_root_cause(a: Anomaly) -> str:
    return (
        f"The root cause of this {a.severity}-severity "
        f"{a.field.replace('_', ' ')} anomaly requires further investigation "
        "via subsystem telemetry review."
    )


def _fallback_recommendation(a: Anomaly) -> str:
    return (
        f"Review {a.field.replace('_', ' ')} subsystem logs and consult with the "
        "mission operations team to determine whether corrective action is required."
    )


def _template_insight(anomaly: Anomaly) -> dict:
    return {
        "anomaly_id":            anomaly.id,
        "explanation":           _fallback_explanation(anomaly),
        "root_cause_hypothesis": _fallback_root_cause(anomaly),
        "recommendation":        _fallback_recommendation(anomaly),
        "source_chunks":         [],
        "no_strong_match":       True,
    }


# ---------------------------------------------------------------------------
# RAG probe (cheap — just checks collection is reachable)
# ---------------------------------------------------------------------------

def _probe_rag() -> bool:
    try:
        from rag.retriever import retrieve_context
        retrieve_context("probe", top_k=1)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Batched RAG insight generation (one LLM call for all anomalies)
# ---------------------------------------------------------------------------

def _batch_rag_insights(anomalies: list[Anomaly]) -> list[dict] | None:
    """
    Retrieve context and query the LLM ONCE for all anomalies together.
    Returns a list of insight dicts, or None on any failure.

    Running in a plain function (not async) so it can be submitted to
    ThreadPoolExecutor from the async route without nesting event loops.
    """
    try:
        from rag.retriever      import retrieve_context
        from rag.granite_client import query_granite
        from rag.prompt_builder import build_granite_prompt, parse_llm_response

        # Search across the full anomaly set so document context is not limited
        # to whichever anomaly happens to have the highest severity.
        anchor = max(anomalies, key=lambda a: SEVERITY_ORDER[a.severity])
        anomaly_terms = " ".join(
            f"{a.field} {a.value} {a.severity}" for a in anomalies
        )
        search_query = (
            f"spacecraft telemetry anomaly reference documentation {anomaly_terms}"
        )
        retrieved_chunks = retrieve_context(query=search_query, top_k=3)

        # A broad retry handles documents whose terminology does not match the
        # detector field names while keeping the retrieval bounded to one retry.
        if not retrieved_chunks:
            retrieved_chunks = retrieve_context(
                query="spacecraft mission telemetry battery temperature signal fuel operations",
                top_k=3,
            )

        # Build source_chunks list (shared across all insights in this batch)
        source_chunks: list[dict] = []
        no_strong_match = True
        for chunk in retrieved_chunks:
            meta = chunk.get("metadata", {})
            dist = chunk.get("distance", 1.0)
            sim  = round(max(0.0, min(1.0, 1.0 - dist / 2.0)), 3)
            source_chunks.append({
                "source_doc":       meta.get("source", "Reference Document"),
                "chunk_text":       chunk.get("text", "")[:600],
                "similarity_score": sim,
                "source":           meta.get("source", "Reference Document"),
                "page":             str(meta.get("page", "N/A")),
                "text":             chunk.get("text", ""),
            })
            if dist < 1.0:
                no_strong_match = False
        if not retrieved_chunks:
            no_strong_match = True

        # Build a single prompt covering all anomalies
        anomaly_lines = "\n".join(
            f"- [{a.field}] value={a.value}, severity={a.severity}, time={a.timestamp}"
            for a in anomalies
        )
        context_text = ""
        for idx, chunk in enumerate(retrieved_chunks):
            meta = chunk.get("metadata", {})
            context_text += f"\n[Source {idx+1}: {meta.get('source','Doc')}]\n{chunk.get('text','')}\n"

        prompt = f"""You are an expert spacecraft systems analyst.
Analyze the following telemetry anomalies using ONLY the provided reference documentation.

--- ANOMALIES ---
{anomaly_lines}

--- REFERENCE DOCUMENTATION CONTEXT ---
{context_text.strip() if context_text.strip() else "No specific document context found."}

--- INSTRUCTIONS ---
For EACH anomaly listed above, provide a brief analysis in this EXACT format (repeat for each):

ANOMALY: <field_name>
1) Plain-language explanation: <one sentence>
2) Likely root cause: <one sentence>
3) Recommended action: <one sentence>

Be concise. Ground your answers in the documentation context."""

        llm_text = query_granite(prompt)
        if not llm_text:
            return None

        # Parse the batched response — split on ANOMALY: markers
        results: list[dict] = []
        import re
        sections = re.split(r"ANOMALY:\s*", llm_text, flags=re.IGNORECASE)
        # Build a field→section map
        field_sections: dict[str, str] = {}
        for section in sections:
            if not section.strip():
                continue
            lines = section.strip().splitlines()
            field_name = lines[0].strip().lower().replace(" ", "_")
            body = "\n".join(lines[1:])
            field_sections[field_name] = body

        for anomaly in anomalies:
            body = field_sections.get(anomaly.field.lower(), "")
            if body:
                parsed = parse_llm_response(body)
            else:
                # LLM didn't cover this anomaly — use template
                parsed = {
                    "explanation":           _fallback_explanation(anomaly),
                    "root_cause_hypothesis": _fallback_root_cause(anomaly),
                    "recommendation":        _fallback_recommendation(anomaly),
                }
            results.append({
                "anomaly_id":            anomaly.id,
                "explanation":           parsed["explanation"],
                "root_cause_hypothesis": parsed["root_cause_hypothesis"],
                "recommendation":        parsed["recommendation"],
                "source_chunks":         source_chunks,
                "no_strong_match":       no_strong_match,
            })

        return results

    except Exception as exc:  # noqa: BLE001
        print(f"[OrbitLens Insights] Batch RAG error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Mission summary (one additional LLM call, also in the thread pool)
# ---------------------------------------------------------------------------

def _try_rag_mission_summary(insights: list[dict], anomalies: list[Anomaly]) -> str | None:
    try:
        from rag.granite_client import query_granite

        anomaly_lines = "\n".join(
            f"- {a.field} at {a.timestamp}: value={a.value}, severity={a.severity}"
            for a in anomalies
        )
        summary_prompt = (
            "You are a spacecraft mission controller. "
            "Write a concise 2-3 sentence mission health summary for these anomalies:\n\n"
            f"{anomaly_lines}\n\n"
            "Provide the summary only — no headings or bullet points."
        )
        result = query_granite(summary_prompt)
        if result and isinstance(result, str) and len(result.strip()) >= 50:
            return result.strip()
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# Public API — generate_insights()
# ---------------------------------------------------------------------------

def generate_insights(anomalies: list[Anomaly]) -> dict:
    """
    Generate insights for all anomalies.

    Heavy work (ChromaDB + LLM) is offloaded to a ThreadPoolExecutor so this
    function is safe to call from async FastAPI routes via asyncio.to_thread()
    or directly in tests. Always returns promptly — never hangs.
    """
    try:
        rag_available = _probe_rag()

        # Cap anomalies sent to LLM to keep prompt+latency bounded
        llm_anomalies = sorted(anomalies, key=lambda a: -SEVERITY_ORDER[a.severity])[:_MAX_ANOMALIES_FOR_LLM]
        remaining     = [a for a in anomalies if a not in llm_anomalies]

        insights: list[dict] = []

        if rag_available:
            # Run batched RAG+LLM in a thread so sync blocking code
            # doesn't stall the caller's context.
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                # Submit batch insight generation
                future_insights = pool.submit(_batch_rag_insights, llm_anomalies)

                try:
                    rag_insights = future_insights.result(timeout=45)
                except concurrent.futures.TimeoutError:
                    print("[OrbitLens Insights] Batch RAG timed out — using template fallback.")
                    rag_insights = None
                except Exception as exc:  # noqa: BLE001
                    print(f"[OrbitLens Insights] Batch RAG error: {exc}")
                    rag_insights = None

            if rag_insights:
                insights.extend(rag_insights)
            else:
                insights.extend(_template_insight(a) for a in llm_anomalies)
        else:
            insights.extend(_template_insight(a) for a in llm_anomalies)

        # Remaining anomalies (beyond cap) always get template fallback
        insights.extend(_template_insight(a) for a in remaining)

        # Restore original anomaly order
        id_order = {a.id: i for i, a in enumerate(anomalies)}
        insights.sort(key=lambda ins: id_order.get(ins["anomaly_id"], 999))

        # ── Mission summary ──────────────────────────────────────────────────
        total  = len(anomalies)
        high   = sum(1 for a in anomalies if a.severity == "high")
        medium = sum(1 for a in anomalies if a.severity == "medium")
        low    = sum(1 for a in anomalies if a.severity == "low")

        if total == 0:
            mission_summary = "Mission analysis found no anomalies. All systems nominal."
        else:
            top = max(anomalies, key=lambda a: SEVERITY_ORDER[a.severity])
            try:
                ts_display = top.timestamp.split("T")[1].rstrip("Z")[:5] + " UTC"
            except Exception:  # noqa: BLE001
                ts_display = top.timestamp
            field_display = top.field.replace("_", " ")

            llm_summary = None
            if rag_available and insights:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    f = pool.submit(_try_rag_mission_summary, insights, anomalies)
                    try:
                        llm_summary = f.result(timeout=35)
                    except Exception:  # noqa: BLE001
                        pass

            mission_summary = llm_summary or (
                f"Mission analysis identified {total} anomalies: {high} high, "
                f"{medium} medium, {low} low severity. "
                f"The most critical event was a {field_display} anomaly at {ts_display}."
            )

        return {"mission_summary": mission_summary, "insights": insights}

    except Exception as exc:  # noqa: BLE001
        return {
            "mission_summary": "Insight generation encountered an error. Please retry.",
            "insights":        [_template_insight(a) for a in anomalies],
            "_error":          str(exc),
        }
