# Motif N1

Autonomous AI experiment engine for personal food sensitivity discovery.

## Project structure

```
motif-n1/
├── .env              ← single env file for both services (never committed)
├── backend/          ← FastAPI Python API
│   ├── .venv/        ← Python virtual environment (not committed)
│   ├── main.py
│   └── requirements.txt
└── frontend/         ← Next.js 14 app
    ├── app/
    └── ...
```

## Prerequisites

- Node.js 18+
- Python 3.11+

## Running locally

You need two terminal windows — one for the backend, one for the frontend.

### Terminal 1 — Backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

The app will be available at `http://localhost:3000`.

## Verifying it works

1. **Backend health check** — open a third terminal and run:
   ```bash
   curl http://localhost:8000/api/health
   ```
   Expected response:
   ```json
   {"status":"ok","env_check":{"anthropic_key_set":true,"supabase_url_set":true,"whoop_client_id_set":true}}
   ```
   (`anthropic_key_set` will be `false` until you add the real key.)

2. **Frontend → backend connection** — open `http://localhost:3000` in a browser.  
   You should see the health response rendered on the page.

## Environment variables

All variables live in `.env` at the project root. Both services read from it automatically.

| Variable               | Used by  | Notes                          |
|------------------------|----------|--------------------------------|
| `ANTHROPIC_API_KEY`    | backend  | Add real key when ready        |
| `SUPABASE_URL`         | backend  | Set                            |
| `SUPABASE_ANON_KEY`    | backend  | Set                            |
| `WHOOP_CLIENT_ID`      | backend  | Set                            |
| `WHOOP_CLIENT_SECRET`  | backend  | Set                            |
| `NEXT_PUBLIC_API_URL`  | frontend | Default: `http://localhost:8000` |
