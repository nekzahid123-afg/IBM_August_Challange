"""
OrbitLens AI — FastAPI backend entry point.

Endpoints registered here:
  GET /health  — liveness check

Additional routes are registered in sub-tasks 3–8 via api/routes_*.py modules.
"""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import routes_upload, routes_anomalies, routes_telemetry, routes_insights, routes_report, routes_chat, routes_documents

app = FastAPI(title="OrbitLens AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    print("[OrbitLens] Backend started. Session store ready.")


app.include_router(routes_upload.router)
app.include_router(routes_anomalies.router)
app.include_router(routes_telemetry.router)
app.include_router(routes_insights.router)
app.include_router(routes_report.router)
app.include_router(routes_chat.router)
app.include_router(routes_documents.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
