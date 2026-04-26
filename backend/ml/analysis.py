"""Post-experiment analysis: turn 14 days of logs + HRV readings into a
posterior update.

The flow:
  1. Pull the experiment's schedule.
  2. For each scheduled day, look up the user's daily_log and the next-
     morning wearable reading. Drop days with missing HRV or
     non-compliance (logged state doesn't match the assigned condition).
  3. Compute mean HRV per condition. Require >= 3 valid days per side.
  4. effect_estimate = mean_B - mean_A.
  5. Welch's t-test for a frequentist confidence number.
  6. Hand the estimate to PersonalEstimator.update(); record the row.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from scipy import stats

from backend.ml.estimator import PersonalEstimator

MIN_DAYS_PER_CONDITION = 3


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _summary_text(intervention_label: str, effect: float, n_a: int, n_b: int) -> str:
    direction = "reduced" if effect < 0 else "increased"
    pairs = min(n_a, n_b)
    return (
        f"{intervention_label} {direction} HRV by an average of "
        f"{abs(effect):.1f}ms across {pairs} paired days."
    )


def analyze_experiment(experiment_id: str, supabase_client: Any) -> dict[str, Any]:
    exp_rows = (
        supabase_client.table("experiments")
        .select("id, user_id, intervention_id, schedule, start_date, end_date, status")
        .eq("id", experiment_id)
        .execute()
        .data
    )
    if not exp_rows:
        raise ValueError(f"No experiment with id {experiment_id}")
    exp = exp_rows[0]
    user_id = exp["user_id"]
    intervention_id = exp["intervention_id"]
    schedule: list[dict[str, Any]] = exp["schedule"] or []

    iv_rows = (
        supabase_client.table("interventions")
        .select("id, key, label")
        .eq("id", intervention_id)
        .execute()
        .data
    )
    if not iv_rows:
        raise ValueError(f"No intervention with id {intervention_id}")
    intervention = iv_rows[0]
    intervention_key = intervention["key"]
    intervention_label = intervention["label"]

    schedule_dates = [_to_date(d["date"]) for d in schedule]
    if not schedule_dates:
        raise ValueError("Experiment has no schedule")
    log_start = min(schedule_dates).isoformat()
    log_end = max(schedule_dates).isoformat()
    hrv_start = (min(schedule_dates) + timedelta(days=1)).isoformat()
    hrv_end = (max(schedule_dates) + timedelta(days=1)).isoformat()

    log_rows = (
        supabase_client.table("daily_logs")
        .select("date, intervention_states")
        .eq("user_id", user_id)
        .gte("date", log_start)
        .lte("date", log_end)
        .execute()
        .data
    )
    logs_by_date: dict[str, dict[str, Any]] = {
        str(r["date"])[:10]: (r.get("intervention_states") or {}) for r in log_rows
    }

    hrv_rows = (
        supabase_client.table("wearable_readings")
        .select("date, hrv_rmssd")
        .eq("user_id", user_id)
        .gte("date", hrv_start)
        .lte("date", hrv_end)
        .execute()
        .data
    )
    hrv_by_date: dict[str, float] = {
        str(r["date"])[:10]: r["hrv_rmssd"]
        for r in hrv_rows
        if r.get("hrv_rmssd") is not None
    }

    a_values: list[float] = []
    b_values: list[float] = []
    dropped: list[dict[str, str]] = []
    for entry in schedule:
        day = _to_date(entry["date"])
        condition = entry["condition"]
        next_day_key = (day + timedelta(days=1)).isoformat()
        day_key = day.isoformat()

        hrv = hrv_by_date.get(next_day_key)
        if hrv is None:
            dropped.append({"date": day_key, "reason": "no_hrv"})
            continue

        logged = logs_by_date.get(day_key)
        if logged is None:
            dropped.append({"date": day_key, "reason": "no_log"})
            continue
        actually_present = bool(logged.get(intervention_key, False))
        expected_present = condition == "B"
        if actually_present != expected_present:
            dropped.append({"date": day_key, "reason": "non_compliance"})
            continue

        if condition == "A":
            a_values.append(float(hrv))
        else:
            b_values.append(float(hrv))

    n_a = len(a_values)
    n_b = len(b_values)

    if n_a < MIN_DAYS_PER_CONDITION or n_b < MIN_DAYS_PER_CONDITION:
        return {
            "status": "insufficient_data",
            "n_a": n_a,
            "n_b": n_b,
            "needed": MIN_DAYS_PER_CONDITION,
            "dropped": dropped,
        }

    mean_a = float(np.mean(a_values))
    mean_b = float(np.mean(b_values))
    effect_estimate = mean_b - mean_a

    t_stat, p_value = stats.ttest_ind(b_values, a_values, equal_var=False)
    t_stat = float(t_stat)
    p_value = float(p_value)

    estimator = PersonalEstimator(user_id, supabase_client)
    new_mean, new_sd, new_n = estimator.update(
        intervention_id, effect_estimate, n_a, n_b
    )

    confidence_z = new_mean / new_sd if new_sd > 0 else 0.0
    summary = _summary_text(intervention_label, effect_estimate, n_a, n_b)

    supabase_client.table("experiment_results").insert(
        {
            "experiment_id": experiment_id,
            "summary_text": summary,
            "effect_estimate": effect_estimate,
            "confidence": confidence_z,
        }
    ).execute()

    supabase_client.table("experiments").update(
        {"status": "completed"}
    ).eq("id", experiment_id).execute()

    return {
        "status": "completed",
        "experiment_id": experiment_id,
        "intervention_id": intervention_id,
        "intervention_key": intervention_key,
        "intervention_label": intervention_label,
        "n_a": n_a,
        "n_b": n_b,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "effect_estimate": effect_estimate,
        "t_stat": t_stat,
        "p_value": p_value,
        "posterior_mean": new_mean,
        "posterior_sd": new_sd,
        "num_observations": new_n,
        "confidence_z": confidence_z,
        "summary_text": summary,
        "dropped": dropped,
    }
