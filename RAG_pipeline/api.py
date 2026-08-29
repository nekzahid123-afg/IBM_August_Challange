from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pipeline import generate_anomaly_insight

app = FastAPI(
    title="OrbitLens-AI Telemetry RAG API",
    description="Automated spacecraft telemetry anomaly reasoning via watsonx.ai and ChromaDB",
    version="1.0.0"
)

class AnomalyPayload(BaseModel):
    field: str
    value: float
    timestamp: str
    detection_method_explanation: str

@app.get("/")
def health_check():
    return {"status": "online", "system": "OrbitLens-AI RAG Pipeline"}

@app.post("/analyze")
def analyze_telemetry(payload: AnomalyPayload):
    try:
        # Pass JSON payload to your completed RAG pipeline
        result = generate_anomaly_insight(payload.model_dump())
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))