import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from project root (one level up from backend/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

app = FastAPI(title="Motif N1 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "env_check": {
            "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
            "supabase_url_set": bool(os.getenv("SUPABASE_URL")),
            "whoop_client_id_set": bool(os.getenv("WHOOP_CLIENT_ID")),
        },
    }
