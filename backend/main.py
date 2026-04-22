import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.db.queries import (
    TEST_USER_ID,
    db_ping,
    get_recent_logs,
    list_interventions_with_estimates,
    upsert_daily_log,
)
from backend.whoop.router import router as whoop_router

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Motif N1 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whoop_router)


class LogBody(BaseModel):
    date: date
    intervention_states: dict[str, bool]


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "db_connected": db_ping(),
        "env_check": {
            "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
            "supabase_url_set": bool(os.getenv("SUPABASE_URL")),
            "whoop_client_id_set": bool(os.getenv("WHOOP_CLIENT_ID")),
        },
    }


@app.get("/api/interventions")
def interventions():
    return list_interventions_with_estimates(TEST_USER_ID)


@app.post("/api/logs")
def create_log(body: LogBody):
    try:
        return upsert_daily_log(
            TEST_USER_ID, body.date.isoformat(), body.intervention_states
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
def list_logs(days: int = 7):
    return get_recent_logs(TEST_USER_ID, days=days)
