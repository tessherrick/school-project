"""Observational backfill: sweep historical daily_logs against next-morning
HRV readings and apply *weak* Bayesian updates to each intervention's posterior.

This is how a user with weeks of pre-existing Whoop data plus retroactively-
filled food logs gets a meaningful body map without waiting for randomized
14-day experiments to finish. The math is the same conjugate Gaussian update
as analyze_experiment, but we deliberately downweight the likelihood by
halving each side's sample count before passing it to PersonalEstimator.update —
observational data is more confounded (correlation between alcohol and late
nights, between dairy and large meals, etc.), so we should let it move the
posterior less per observed day.

Each updated intervention writes a row into experiment_results with
experiment_id = NULL. The /body-map page joins on this to badge results that
came from history vs. from a real experiment.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from backend.ml.estimator import PersonalEstimator

MIN_OBSERVATIONS_PER_GROUP = 4
# Multiplier applied to n_a / n_b before the Bayesian update.
# Halving the effective sample count halves the likelihood precision, so an
# observational pair contributes ~1/2 the certainty of a randomized pair.
OBSERVATIONAL_PRECISION_FACTOR = 0.5


def _summary_text(
    label: str, n_a: int, n_b: int, mean_a: float, mean_b: float
) -> str:
    direction = "lower" if mean_b < mean_a else "higher"
    delta = abs(mean_b - mean_a)
    return (
        f"Observational backfill: {label.lower()} present on {n_b} day"
        f"{'s' if n_b != 1 else ''} vs absent on {n_a} day"
        f"{'s' if n_a != 1 else ''}. "
        f"HRV averaged {delta:.1f}ms {direction} on {label.lower()} days."
    )


def _pair_logs_to_hrv(
    logs: list[dict[str, Any]],
    hrv_by_date: dict[str, float],
) -> list[tuple[dict[str, Any], float]]:
    """Each log entry is paired with the HRV measured the FOLLOWING morning,
    since Whoop reports overnight recovery the morning after the day in question.
    Logs without a matching next-day HRV are dropped.
    """
    from datetime import date as date_t, datetime, timedelta

    paired: list[tuple[dict[str, Any], float]] = []
    for log in logs:
        d_raw = log.get("date")
        if isinstance(d_raw, date_t):
            d = d_raw
        else:
            d = datetime.strptime(str(d_raw)[:10], "%Y-%m-%d").date()
        next_key = (d + timedelta(days=1)).isoformat()
        hrv = hrv_by_date.get(next_key)
        if hrv is None:
            continue
        paired.append((log, float(hrv)))
    return paired


def run_observational_backfill(
    user_id: str, supabase_client: Any
) -> dict[str, Any]:
    interventions = (
        supabase_client.table("interventions")
        .select("id, key, label")
        .execute()
        .data
    )

    log_rows = (
        supabase_client.table("daily_logs")
        .select("date, intervention_states")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    logs = [
        r for r in log_rows
        if r.get("intervention_states")
        and any(v is not None for v in r["intervention_states"].values())
    ]

    hrv_rows = (
        supabase_client.table("wearable_readings")
        .select("date, hrv_rmssd")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    hrv_by_date: dict[str, float] = {
        str(r["date"])[:10]: r["hrv_rmssd"]
        for r in hrv_rows
        if r.get("hrv_rmssd") is not None
    }

    paired = _pair_logs_to_hrv(logs, hrv_by_date)

    estimator = PersonalEstimator(user_id, supabase_client)

    details: list[dict[str, Any]] = []
    updated = 0
    insufficient = 0

    for iv in interventions:
        key = iv["key"]
        intervention_id = iv["id"]
        label = iv["label"]

        a_values: list[float] = []
        b_values: list[float] = []
        for log, hrv in paired:
            states = log.get("intervention_states") or {}
            if key not in states or states[key] is None:
                continue
            if bool(states[key]):
                b_values.append(hrv)
            else:
                a_values.append(hrv)

        n_a = len(a_values)
        n_b = len(b_values)

        if n_a < MIN_OBSERVATIONS_PER_GROUP or n_b < MIN_OBSERVATIONS_PER_GROUP:
            insufficient += 1
            details.append(
                {
                    "key": key,
                    "status": "insufficient_data",
                    "n_a": n_a,
                    "n_b": n_b,
                }
            )
            continue

        mean_a = float(np.mean(a_values))
        mean_b = float(np.mean(b_values))
        effect_estimate = mean_b - mean_a

        # Halve effective sample counts so observational data updates the
        # posterior with ~half the confidence of a randomized experiment.
        # PersonalEstimator.update requires int >= 1 on each side.
        weak_n_a = max(1, int(round(n_a * OBSERVATIONAL_PRECISION_FACTOR)))
        weak_n_b = max(1, int(round(n_b * OBSERVATIONAL_PRECISION_FACTOR)))

        new_mean, new_sd, new_n = estimator.update(
            intervention_id, effect_estimate, weak_n_a, weak_n_b
        )

        confidence_z = new_mean / new_sd if new_sd > 0 else 0.0
        summary = _summary_text(label, n_a, n_b, mean_a, mean_b)

        supabase_client.table("experiment_results").insert(
            {
                "experiment_id": None,
                "summary_text": summary,
                "effect_estimate": effect_estimate,
                "confidence": confidence_z,
            }
        ).execute()

        updated += 1
        details.append(
            {
                "key": key,
                "status": "updated",
                "effect": round(effect_estimate, 2),
                "n_a": n_a,
                "n_b": n_b,
                "mean_a": round(mean_a, 2),
                "mean_b": round(mean_b, 2),
                "posterior_mean": round(new_mean, 2),
                "posterior_sd": round(new_sd, 2),
                "num_observations": new_n,
                "summary_text": summary,
            }
        )

    return {
        "interventions_updated": updated,
        "interventions_insufficient": insufficient,
        "paired_days": len(paired),
        "details": details,
    }
