"""
Grounded mission-support chat backed by ChromaDB vector search + watsonx.ai.

POST /chat
  Body: { "session_id": str (optional), "message": str }   ← backend canonical
        { "session_id": str (optional), "question": str }   ← frontend alias

Returns: { "session_id": str|null, "answer": str, "source_chunks": list }
"""

from __future__ import annotations

import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

import sessions

router = APIRouter()

# ── Domain allow / reject lists ───────────────────────────────────────────────
# If a message matches NONE of these space-related keywords AND matches an
# off-topic keyword, we reject it immediately without spending an LLM call.

_SPACE_KEYWORDS = re.compile(
    r"\b(space|satellite|spacecraft|orbit|telemetry|anomal|rocket|launch|mission|"
    r"nasa|esa|isro|iss|astronaut|payload|thruster|propuls|attitude|altitude|"
    r"solar\s*panel|battery|voltage|temperature|signal|sensor|fuel|propellant|"
    r"radiation|thermal|power|subsystem|gyroscope|magnetometer|accelerometer|"
    r"velocity|trajectory|apogee|perigee|eclipse|comms|communication|link|rf|"
    r"chroma|rag|ibm|granite|ai|analysis|insight|report|health|status|"
    r"detection|isolation\s*forest|anomaly|data|upload|csv|document|"
    r"debris|cubesat|leo|geo|meo|deep\s*space|mars|moon|lunar|jupiter|saturn)\b",
    re.IGNORECASE,
)

_OFFTOPIC_KEYWORDS = re.compile(
    r"\b(recipe|cooking|movie|film|sport|football|cricket|basketball|music|song|"
    r"celebrity|actor|actress|stock|crypto|bitcoin|weather|joke|poem|story|"
    r"restaurant|fashion|makeup|hair|travel|tourism|hotel|flight\s*booking|"
    r"shopping|game|video\s*game|anime|manga|dating|relationship|love|"
    r"politics|election|president|prime\s*minister|war|military\s*tactics)\b",
    re.IGNORECASE,
)


def _is_off_topic(text: str) -> bool:
    """Return True only when query has strong off-topic signals AND zero space signals."""
    has_space   = bool(_SPACE_KEYWORDS.search(text))
    has_offtopic = bool(_OFFTOPIC_KEYWORDS.search(text))
    return has_offtopic and not has_space


# ── Request model ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None)
    # Accept "message" (backend canonical) OR "question" (frontend alias)
    message:    str | None = Field(default=None, min_length=None, max_length=2_000)
    question:   str | None = Field(default=None, min_length=None, max_length=2_000)

    @model_validator(mode="after")
    def _normalise_message(self) -> "ChatRequest":
        """Ensure self.message is always populated from whichever field arrived."""
        if not self.message and self.question:
            self.message = self.question
        if not self.message:
            raise ValueError("Either 'message' or 'question' must be provided.")
        return self


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_chat_prompt(
    message: str,
    retrieved_chunks: list[dict],
    anomalies: list,
    insights: dict,
) -> str:
    """Build a conversational, RAG-grounded prompt."""

    # Retrieved document context
    context_text = ""
    for idx, chunk in enumerate(retrieved_chunks):
        metadata = chunk.get("metadata", {})
        source   = metadata.get("source", "Reference Document")
        text     = chunk.get("text", "")
        context_text += f"\n[Source {idx + 1}: {source}]\n{text}\n"

    # Mission telemetry summary
    mission_ctx = ""
    if anomalies:
        high   = sum(1 for a in anomalies if _sev(a) == "high")
        medium = sum(1 for a in anomalies if _sev(a) == "medium")
        low    = sum(1 for a in anomalies if _sev(a) == "low")
        mission_ctx = (
            f"\nMission telemetry: {len(anomalies)} anomalies detected "
            f"({high} high, {medium} medium, {low} low severity)."
        )
    if insights.get("mission_summary"):
        mission_ctx += f"\nMission summary: {insights['mission_summary']}"

    return f"""You are OrbitLens AI, an expert spacecraft mission-operations assistant. \
Answer the operator's question clearly and concisely, grounded in the mission context \
and reference documentation provided below. Do NOT hallucinate facts.

--- MISSION CONTEXT ---
{mission_ctx.strip() if mission_ctx else "No telemetry session active."}

--- REFERENCE DOCUMENTATION (from ChromaDB knowledge base) ---
{context_text.strip() if context_text.strip() else "No reference documents indexed yet."}

--- OPERATOR QUESTION ---
{message}

--- INSTRUCTIONS ---
- Answer in plain, professional language (2–5 sentences for simple questions; up to a short paragraph for complex ones).
- Ground your answer in the mission context or documentation above when relevant.
- Do NOT use a numbered 1)/2)/3) report format — answer conversationally.
- If the information is genuinely unavailable, say so and suggest what the operator should do next.
- Stay strictly within the domain of space, satellite systems, and mission operations.

Answer:"""


def _sev(a) -> str:
    return getattr(a, "severity", None) or (a.get("severity", "") if isinstance(a, dict) else "")


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/chat")
async def post_chat(body: ChatRequest):
    message = (body.message or "").strip()

    # ── Domain guard ──────────────────────────────────────────────────────────
    if _is_off_topic(message):
        return {
            "session_id":    body.session_id,
            "answer": (
                "I'm specialised in space mission operations and telemetry analysis. "
                "Your question appears to be outside that domain — I can't help with it. "
                "Try asking about mission health, anomalies, subsystem status, or your uploaded telemetry data."
            ),
            "source_chunks": [],
        }

    # ── Session lookup (optional — chatbox works without a session) ───────────
    session   = sessions.get_session(body.session_id) if body.session_id else None
    anomalies = (session.get("anomalies") or []) if session else []
    insights  = (session.get("insights")  or {}) if session else {}

    answer: str = ""
    source_chunks: list[dict] = []

    # ── RAG + LLM ─────────────────────────────────────────────────────────────
    try:
        from rag.retriever      import retrieve_context
        from rag.granite_client import query_granite

        retrieved = retrieve_context(query=message, top_k=4)

        prompt   = _build_chat_prompt(message, retrieved, anomalies, insights)
        llm_text = query_granite(prompt)

        if llm_text:
            # Strip any accidental leading "Answer:" echo from the model
            answer = re.sub(r"^Answer:\s*", "", llm_text.strip(), flags=re.IGNORECASE)
        else:
            # LLM unavailable — use session-aware dynamic fallback
            answer = _session_aware_fallback(message, anomalies, insights)

        # Map chunks to API contract shape
        for chunk in retrieved:
            meta       = chunk.get("metadata", {})
            dist       = chunk.get("distance", 1.0)
            similarity = round(max(0.0, min(1.0, 1.0 - dist / 2.0)), 3)
            source_chunks.append({
                "source_doc":       meta.get("source", "Reference Document"),
                "chunk_text":       chunk.get("text", "")[:400],
                "similarity_score": similarity,
            })

    except Exception as exc:  # noqa: BLE001
        print(f"[OrbitLens Chat] RAG pipeline error: {exc}")
        answer = _session_aware_fallback(message, anomalies, insights)

    return {
        "session_id":    body.session_id,
        "answer":        answer,
        "source_chunks": source_chunks,
    }


# ── Session-aware fallback (no LLM / no docs) ─────────────────────────────────

def _session_aware_fallback(message: str, anomalies: list, insights: dict) -> str:
    """Produce a helpful dynamic answer from cached session state when LLM is unavailable."""
    lower = message.lower()

    if any(w in lower for w in ("health", "status", "nominal", "how is", "overall")):
        if anomalies:
            high   = sum(1 for a in anomalies if _sev(a) == "high")
            medium = sum(1 for a in anomalies if _sev(a) == "medium")
            low    = sum(1 for a in anomalies if _sev(a) == "low")
            if high > 0:
                return (
                    f"Mission health requires attention: {len(anomalies)} anomalies detected "
                    f"({high} high-severity, {medium} medium, {low} low). "
                    "High-severity events need immediate review. Use 'Generate AI Insights' for detailed analysis."
                )
            return (
                f"Mission health is stable with {len(anomalies)} minor anomalies "
                f"({medium} medium, {low} low severity). No high-severity events."
            )
        return "All monitored subsystems are currently within nominal operating ranges."

    if any(w in lower for w in ("anomal", "fault", "issue", "problem", "error", "warning", "critical")):
        if anomalies:
            high        = sum(1 for a in anomalies if _sev(a) == "high")
            medium      = sum(1 for a in anomalies if _sev(a) == "medium")
            high_fields = list({
                (getattr(a, "field", None) or (a.get("field", "unknown") if isinstance(a, dict) else "unknown")).replace("_", " ")
                for a in anomalies if _sev(a) == "high"
            })[:3]
            if high_fields:
                return (
                    f"{len(anomalies)} anomalies detected: {high} high-severity in {', '.join(high_fields)}; "
                    f"{medium} medium-severity. Run 'Generate AI Insights' for root-cause analysis."
                )
            return f"{len(anomalies)} anomalies detected ({high} high, {medium} medium severity). Review recommended."
        return "No anomalies detected. All parameters are within normal bounds."

    if any(w in lower for w in ("battery", "voltage", "power")):
        batt = [a for a in anomalies if "battery" in (getattr(a, "field", "") or (a.get("field", "") if isinstance(a, dict) else ""))]
        if batt:
            return f"Battery voltage shows {len(batt)} anomaly/anomalies. Check power subsystem and charging cycle status."
        return "Battery voltage telemetry appears within nominal range."

    if any(w in lower for w in ("temperature", "thermal", "heat")):
        temp = [a for a in anomalies if "temperature" in (getattr(a, "field", "") or (a.get("field", "") if isinstance(a, dict) else ""))]
        if temp:
            return f"Temperature anomalies detected: {len(temp)} readings outside nominal range. Check thermal subsystem."
        return "Temperature readings are within expected operational bounds."

    if any(w in lower for w in ("signal", "communication", "comms", "link", "rf")):
        sig = [a for a in anomalies if "signal" in (getattr(a, "field", "") or (a.get("field", "") if isinstance(a, dict) else ""))]
        if sig:
            return f"Signal strength shows {len(sig)} anomaly/anomalies. Check antenna alignment and atmospheric conditions."
        return "Signal strength is currently within nominal range."

    if any(w in lower for w in ("fuel", "propellant", "propulsion")):
        fuel = [a for a in anomalies if "fuel" in (getattr(a, "field", "") or (a.get("field", "") if isinstance(a, dict) else ""))]
        if fuel:
            return f"Fuel level shows {len(fuel)} anomaly/anomalies. Verify propulsion system integrity."
        return "Fuel level is within nominal range."

    if any(w in lower for w in ("altitude", "orbit", "position", "trajectory")):
        alt = [a for a in anomalies if "altitude" in (getattr(a, "field", "") or (a.get("field", "") if isinstance(a, dict) else ""))]
        if alt:
            return f"Altitude shows {len(alt)} anomaly/anomalies. Verify orbital parameters and attitude control."
        return "Altitude is within expected orbital parameters."

    if "summary" in lower and insights.get("mission_summary"):
        return insights["mission_summary"]

    if any(w in lower for w in ("help", "what can", "what do", "capability")):
        return (
            "I can answer questions about: mission health, detected anomalies, battery/power, "
            "temperature, signal strength, fuel levels, altitude, and velocity. "
            "Upload reference documents (PDF, DOCX, TXT) to enable document-grounded answers via RAG."
        )

    return (
        "I'm OrbitLens AI, your mission intelligence assistant. "
        "Ask me about mission health, telemetry anomalies, subsystem status, or upload a file to start analysis. "
        "I'm grounded in your uploaded documents and IBM Granite via watsonx.ai."
    )
