"""Persist Whoop tokens per user and hand out a valid access token on demand.

`get_valid_access_token(user_id)` is the only function callers should need.
It refreshes transparently when the stored access token is close to expiry.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.db.client import service_client
from backend.whoop.oauth import refresh_access_token

# Refresh when fewer than this many seconds remain on the access token.
REFRESH_BUFFER_SECONDS = 60


def save_tokens(user_id: str, token_response: dict[str, Any]) -> dict[str, Any]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(token_response["expires_in"])
    )
    row = {
        "user_id": user_id,
        "access_token": token_response["access_token"],
        "refresh_token": token_response["refresh_token"],
        "expires_at": expires_at.isoformat(),
    }
    c = service_client()
    existing = (
        c.table("whoop_tokens").select("id").eq("user_id", user_id).execute()
    )
    if existing.data:
        result = (
            c.table("whoop_tokens").update(row).eq("user_id", user_id).execute()
        )
    else:
        result = c.table("whoop_tokens").insert(row).execute()
    return result.data[0] if result.data else row


def get_tokens(user_id: str) -> dict[str, Any] | None:
    result = (
        service_client()
        .table("whoop_tokens")
        .select("access_token, refresh_token, expires_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_valid_access_token(user_id: str) -> str:
    tok = get_tokens(user_id)
    if not tok:
        raise RuntimeError("Whoop not connected — no tokens stored for user")
    expires_at = datetime.fromisoformat(
        tok["expires_at"].replace("Z", "+00:00")
    )
    now = datetime.now(timezone.utc)
    if expires_at - now > timedelta(seconds=REFRESH_BUFFER_SECONDS):
        return tok["access_token"]
    new = refresh_access_token(tok["refresh_token"])
    save_tokens(user_id, new)
    return new["access_token"]
