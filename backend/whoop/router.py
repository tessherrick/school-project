"""FastAPI router for Whoop OAuth + sync endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from backend.db.queries import (
    TEST_USER_ID,
    get_all_wearable_readings,
    get_recent_wearable_readings,
)
from backend.whoop.oauth import (
    build_authorize_url,
    consume_state,
    exchange_code,
    refresh_access_token,
)
from backend.whoop.sync import sync_last_30_days
from backend.whoop.tokens import get_tokens, save_tokens

router = APIRouter()


@router.get("/api/auth/whoop/login")
def whoop_login():
    try:
        _, url = build_authorize_url()
    except KeyError as e:
        raise HTTPException(500, f"Missing env var: {e}")
    return {"authorize_url": url}


@router.get("/api/auth/whoop/callback")
def whoop_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        raise HTTPException(400, f"Whoop returned error: {error}")
    if not code or not state:
        raise HTTPException(400, "Missing code or state")
    if not consume_state(state):
        raise HTTPException(400, "Invalid or expired state (CSRF check failed)")
    try:
        token_response = exchange_code(code)
        save_tokens(TEST_USER_ID, token_response)
    except Exception as e:
        raise HTTPException(500, f"Token exchange failed: {e}")
    return RedirectResponse(url="http://localhost:3000/connect?success=true")


@router.post("/api/whoop/refresh")
def whoop_refresh():
    tok = get_tokens(TEST_USER_ID)
    if not tok:
        raise HTTPException(400, "No Whoop tokens stored — connect first")
    try:
        new = refresh_access_token(tok["refresh_token"])
        save_tokens(TEST_USER_ID, new)
    except Exception as e:
        raise HTTPException(500, f"Refresh failed: {e}")
    return {"refreshed": True, "expires_in": new.get("expires_in")}


@router.post("/api/whoop/sync")
def whoop_sync():
    try:
        return sync_last_30_days(TEST_USER_ID)
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {e}")


@router.get("/api/wearables/recent")
def wearables_recent(limit: int = 10):
    return get_recent_wearable_readings(TEST_USER_ID, limit=limit)


@router.get("/api/wearables/all")
def wearables_all():
    return get_all_wearable_readings(TEST_USER_ID)
