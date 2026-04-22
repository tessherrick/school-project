"""Fetch the last 30 days of recovery + sleep and upsert into wearable_readings.

One row per (user_id, date, source='whoop'). Recovery fills HRV / recovery /
resting_hr; sleep fills sleep_performance. Both merge into raw_payload as
`{"recovery": ..., "sleep": ...}`.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.db.client import service_client
from backend.whoop.tokens import get_valid_access_token

RECOVERY_URL = "https://api.prod.whoop.com/developer/v2/recovery"
SLEEP_URL = "https://api.prod.whoop.com/developer/v2/activity/sleep"
PAGE_LIMIT = 25


def _fetch_paginated(
    url: str, access_token: str, start: str, end: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_token: str | None = None
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        params: dict[str, Any] = {
            "start": start,
            "end": end,
            "limit": PAGE_LIMIT,
        }
        if next_token:
            params["nextToken"] = next_token
        resp = httpx.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 429:
            raise RuntimeError("Whoop rate limit hit — try again in a minute")
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Whoop API {resp.status_code} at {url}: {resp.text}"
            )
        body = resp.json()
        records.extend(body.get("records", []))
        next_token = body.get("next_token")
        if not next_token:
            return records


def _record_date(rec: dict[str, Any]) -> str | None:
    iso = rec.get("created_at") or rec.get("start")
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.date().isoformat()


def _upsert_reading(
    user_id: str, day: str, updates: dict[str, Any]
) -> None:
    c = service_client()
    existing = (
        c.table("wearable_readings")
        .select("id, raw_payload")
        .eq("user_id", user_id)
        .eq("date", day)
        .eq("source", "whoop")
        .limit(1)
        .execute()
    )
    if existing.data:
        row_id = existing.data[0]["id"]
        merged_raw = (existing.data[0].get("raw_payload") or {}) | (
            updates.get("raw_payload") or {}
        )
        payload = {**updates, "raw_payload": merged_raw}
        c.table("wearable_readings").update(payload).eq("id", row_id).execute()
    else:
        c.table("wearable_readings").insert(
            {"user_id": user_id, "date": day, "source": "whoop", **updates}
        ).execute()


def sync_last_30_days(user_id: str) -> dict[str, Any]:
    access = get_valid_access_token(user_id)
    now = datetime.now(timezone.utc)
    # Whoop expects RFC 3339; replace the +00:00 offset with a literal Z.
    end = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    start = (
        (now - timedelta(days=30))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    recovery_records = _fetch_paginated(RECOVERY_URL, access, start, end)
    sleep_records = _fetch_paginated(SLEEP_URL, access, start, end)

    dates: set[str] = set()

    for rec in recovery_records:
        day = _record_date(rec)
        if not day:
            continue
        score = rec.get("score") or {}
        _upsert_reading(
            user_id,
            day,
            {
                "hrv_rmssd": score.get("hrv_rmssd_milli"),
                "recovery_score": score.get("recovery_score"),
                "resting_hr": score.get("resting_heart_rate"),
                "raw_payload": {"recovery": rec},
            },
        )
        dates.add(day)

    for rec in sleep_records:
        day = _record_date(rec)
        if not day:
            continue
        score = rec.get("score") or {}
        _upsert_reading(
            user_id,
            day,
            {
                "sleep_performance": score.get("sleep_performance_percentage"),
                "raw_payload": {"sleep": rec},
            },
        )
        dates.add(day)

    return {
        "synced_recovery": len(recovery_records),
        "synced_sleep": len(sleep_records),
        "dates": sorted(dates),
    }
