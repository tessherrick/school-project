"""Whoop OAuth 2.0 authorization-code flow.

- `build_authorize_url()` issues a random state (stored in-process) and returns
  the URL to send the browser to.
- `consume_state(state)` validates and invalidates it on callback (CSRF guard).
- `exchange_code(code)` and `refresh_access_token(refresh_token)` wrap the token
  endpoint.

State is kept in a module-level dict — fine for a single-process dev server. If
we ever run multiple workers, move this to Supabase.
"""
import os
import secrets
import time
from urllib.parse import urlencode

import httpx

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

# `offline` is required to receive a refresh token; the rest are the data scopes.
SCOPES = [
    "offline",
    "read:recovery",
    "read:sleep",
    "read:cycles",
    "read:workout",
    "read:profile",
]

STATE_TTL_SECONDS = 600
_state_store: dict[str, float] = {}


def _purge_expired_states() -> None:
    now = time.time()
    for s in [s for s, exp in _state_store.items() if exp < now]:
        _state_store.pop(s, None)


def issue_state() -> str:
    _purge_expired_states()
    state = secrets.token_urlsafe(32)
    _state_store[state] = time.time() + STATE_TTL_SECONDS
    return state


def consume_state(state: str) -> bool:
    _purge_expired_states()
    return _state_store.pop(state, None) is not None


def build_authorize_url() -> tuple[str, str]:
    client_id = os.environ["WHOOP_CLIENT_ID"]
    redirect_uri = os.environ["WHOOP_REDIRECT_URI"]
    state = issue_state()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    return state, f"{AUTH_URL}?{urlencode(params)}"


def _post_token(data: dict[str, str]) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Whoop token endpoint {resp.status_code}: {resp.text}"
        )
    return resp.json()


def exchange_code(code: str) -> dict:
    return _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": os.environ["WHOOP_CLIENT_ID"],
            "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
            "redirect_uri": os.environ["WHOOP_REDIRECT_URI"],
        }
    )


def refresh_access_token(refresh_token: str) -> dict:
    return _post_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": os.environ["WHOOP_CLIENT_ID"],
            "client_secret": os.environ["WHOOP_CLIENT_SECRET"],
            "scope": "offline",
        }
    )
