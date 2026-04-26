"""All DB access lives here. Route handlers call these, never Supabase directly.

Hardcoded to a single test user for now; when we add real auth, swap the
TEST_USER_ID constant for a request-scoped user id.
"""
from datetime import date, timedelta
from typing import Any

from backend.db.client import anon_client, service_client

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
TEST_USER_EMAIL = "tess@test.local"


def list_interventions_with_estimates(user_id: str) -> list[dict[str, Any]]:
    """All interventions with the user's personal_estimates joined in.

    Uses PostgREST's embedded-resource syntax to pull estimates alongside
    interventions in a single request. If the user has no estimate yet for
    an intervention, we fall back to the prior.
    """
    result = (
        anon_client()
        .table("interventions")
        .select(
            "id, key, label, description, prior_mean_effect, prior_sd_effect, "
            "personal_estimates(user_id, posterior_mean, posterior_sd, "
            "num_observations, last_updated)"
        )
        .order("key")
        .execute()
    )

    rows: list[dict[str, Any]] = []
    for row in result.data:
        matching = [
            e
            for e in (row.get("personal_estimates") or [])
            if e.get("user_id") == user_id
        ]
        est = matching[0] if matching else None
        rows.append(
            {
                "id": row["id"],
                "key": row["key"],
                "label": row["label"],
                "description": row["description"],
                "prior_mean_effect": row["prior_mean_effect"],
                "prior_sd_effect": row["prior_sd_effect"],
                "posterior_mean": est["posterior_mean"] if est else row["prior_mean_effect"],
                "posterior_sd": est["posterior_sd"] if est else row["prior_sd_effect"],
                "num_observations": est["num_observations"] if est else 0,
                "last_updated": est["last_updated"] if est else None,
            }
        )
    return rows


def upsert_daily_log(
    user_id: str, day: str, intervention_states: dict[str, bool]
) -> dict[str, Any]:
    """Insert or update today's log. Conflicts on (user_id, date)."""
    result = (
        anon_client()
        .table("daily_logs")
        .upsert(
            {
                "user_id": user_id,
                "date": day,
                "intervention_states": intervention_states,
            },
            on_conflict="user_id,date",
        )
        .execute()
    )
    return result.data[0] if result.data else {}


def get_recent_logs(user_id: str, days: int = 7) -> list[dict[str, Any]]:
    today = date.today()
    start = today - timedelta(days=days - 1)
    result = (
        anon_client()
        .table("daily_logs")
        .select("id, date, intervention_states, created_at")
        .eq("user_id", user_id)
        .gte("date", start.isoformat())
        .lte("date", today.isoformat())
        .order("date", desc=True)
        .execute()
    )
    return result.data


def get_recent_wearable_readings(
    user_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    result = (
        anon_client()
        .table("wearable_readings")
        .select(
            "date, hrv_rmssd, recovery_score, resting_hr, "
            "sleep_performance, strain, source, created_at"
        )
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def get_all_wearable_readings(user_id: str) -> list[dict[str, Any]]:
    """Every reading we have for the user, oldest first.

    Used by the /history page so the user can retrospectively log past days
    against the nights for which we already have HRV.
    """
    result = (
        anon_client()
        .table("wearable_readings")
        .select(
            "date, hrv_rmssd, recovery_score, resting_hr, sleep_performance"
        )
        .eq("user_id", user_id)
        .order("date", desc=False)
        .execute()
    )
    return result.data


def db_ping() -> bool:
    """Cheap round-trip to Supabase: SELECT one row from interventions."""
    try:
        anon_client().table("interventions").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def list_experiments(user_id: str) -> list[dict[str, Any]]:
    result = (
        anon_client()
        .table("experiments")
        .select(
            "id, intervention_id, protocol_type, start_date, end_date, "
            "status, schedule, created_at, "
            "interventions(key, label)"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def get_intervention(intervention_id: str) -> dict[str, Any] | None:
    result = (
        anon_client()
        .table("interventions")
        .select("id, key, label")
        .eq("id", intervention_id)
        .execute()
    )
    return result.data[0] if result.data else None


def create_experiment(
    user_id: str,
    intervention_id: str,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    result = (
        anon_client()
        .table("experiments")
        .insert(
            {
                "user_id": user_id,
                "intervention_id": intervention_id,
                "protocol_type": protocol["protocol_type"],
                "start_date": protocol["start_date"],
                "end_date": protocol["end_date"],
                "status": "active",
                "schedule": protocol["schedule"],
            }
        )
        .execute()
    )
    return result.data[0] if result.data else {}
