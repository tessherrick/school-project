import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.db.client import anon_client
from backend.db.queries import (
    TEST_USER_ID,
    create_experiment,
    db_ping,
    get_intervention,
    get_recent_logs,
    list_experiments,
    list_interventions_with_estimates,
    upsert_daily_log,
)
from backend.ml.analysis import analyze_experiment
from backend.ml.backfill import run_observational_backfill
from backend.ml.bandit import (
    select_next_experiment,
    select_next_experiment_diagnostic,
)
from backend.ml.estimator import PersonalEstimator
from backend.ml.protocol import generate_abab_protocol
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


class StartExperimentBody(BaseModel):
    intervention_id: str


class CompleteExperimentBody(BaseModel):
    experiment_id: str


@app.post("/api/experiments/select")
def experiments_select():
    estimator = PersonalEstimator(TEST_USER_ID, anon_client())
    pick = select_next_experiment(estimator)
    pick["candidates"] = select_next_experiment_diagnostic(estimator)
    return pick


@app.post("/api/experiments/start")
def experiments_start(body: StartExperimentBody):
    intervention = get_intervention(body.intervention_id)
    if not intervention:
        raise HTTPException(status_code=404, detail="intervention not found")
    protocol = generate_abab_protocol(
        intervention_id=body.intervention_id,
        intervention_key=intervention["key"],
        start_date=date.today(),
    )
    row = create_experiment(TEST_USER_ID, body.intervention_id, protocol)
    return {"experiment": row, "protocol": protocol}


@app.post("/api/experiments/complete")
def experiments_complete(body: CompleteExperimentBody):
    try:
        return analyze_experiment(body.experiment_id, anon_client())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/experiments")
def experiments_list():
    return list_experiments(TEST_USER_ID)


@app.get("/api/posteriors")
def posteriors():
    """Each row gets a `num_experiments` count layered on top of the
    estimator's view, so the UI can distinguish observational evidence
    (num_observations > num_experiments) from completed experiments.
    """
    client = anon_client()
    estimator = PersonalEstimator(TEST_USER_ID, client)
    rows = estimator.get_all_posteriors()

    completed = (
        client.table("experiments")
        .select("intervention_id, status")
        .eq("user_id", TEST_USER_ID)
        .eq("status", "completed")
        .execute()
        .data
    )
    counts: dict[str, int] = {}
    for r in completed:
        iv_id = r["intervention_id"]
        counts[iv_id] = counts.get(iv_id, 0) + 1

    for row in rows:
        row["num_experiments"] = counts.get(row["intervention_id"], 0)
    return rows


@app.post("/api/backfill/run")
def backfill_run():
    try:
        return run_observational_backfill(TEST_USER_ID, anon_client())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
