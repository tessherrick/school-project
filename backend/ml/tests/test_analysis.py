"""Integration test for analyze_experiment using FakeSupabase. Builds a
full 14-day experiment, fakes compliant/non-compliant days, and asserts
the posterior moves the right way and the result row is written."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.ml.analysis import analyze_experiment
from backend.ml.tests._fakes import FakeSupabase

USER_ID = "u1"
INTERVENTION_ID = "iv-1"
EXPERIMENT_ID = "exp-1"


def _seed_alcohol_experiment(
    sb: FakeSupabase,
    start: date,
    *,
    a_hrv: float = 60.0,
    b_hrv: float = 50.0,
    drop_dates: set[str] | None = None,
    non_compliant_dates: set[str] | None = None,
) -> None:
    """Wire up an A/B/A/B/... 14-day alcohol experiment."""
    drop_dates = drop_dates or set()
    non_compliant_dates = non_compliant_dates or set()

    sb.tables["interventions"] = [{
        "id": INTERVENTION_ID, "key": "alcohol_any", "label": "Alcohol",
        "prior_mean_effect": -8.0, "prior_sd_effect": 3.0,
    }]
    sb.tables["personal_estimates"] = [{
        "user_id": USER_ID, "intervention_id": INTERVENTION_ID,
        "posterior_mean": -8.0, "posterior_sd": 3.0, "num_observations": 0,
    }]

    schedule = []
    daily_logs = []
    wearable_readings = []
    for i in range(14):
        day = start + timedelta(days=i)
        condition = "A" if i % 2 == 0 else "B"
        day_key = day.isoformat()
        schedule.append({
            "date": day_key, "condition": condition,
            "instruction": f"day {i} instruction",
        })

        # daily log: compliant by default, flipped if in non_compliant_dates
        actual_present = (condition == "B")
        if day_key in non_compliant_dates:
            actual_present = not actual_present
        daily_logs.append({
            "user_id": USER_ID, "date": day_key,
            "intervention_states": {"alcohol_any": actual_present},
        })

        # wearable reading on day+1, unless dropped
        next_day_key = (day + timedelta(days=1)).isoformat()
        if next_day_key not in drop_dates:
            wearable_readings.append({
                "user_id": USER_ID, "date": next_day_key,
                "hrv_rmssd": a_hrv if condition == "A" else b_hrv,
            })

    sb.tables["experiments"] = [{
        "id": EXPERIMENT_ID, "user_id": USER_ID,
        "intervention_id": INTERVENTION_ID,
        "schedule": schedule,
        "start_date": schedule[0]["date"],
        "end_date": schedule[-1]["date"],
        "status": "active",
    }]
    sb.tables["daily_logs"] = daily_logs
    sb.tables["wearable_readings"] = wearable_readings


def test_full_experiment_updates_posterior_and_writes_result():
    sb = FakeSupabase()
    _seed_alcohol_experiment(sb, date(2026, 4, 1), a_hrv=60.0, b_hrv=50.0)

    result = analyze_experiment(EXPERIMENT_ID, sb)

    assert result["status"] == "completed"
    assert result["n_a"] == 7
    assert result["n_b"] == 7
    assert result["mean_a"] == 60.0
    assert result["mean_b"] == 50.0
    assert result["effect_estimate"] == pytest.approx(-10.0)

    # posterior should move toward the data: started at -8, observed -10,
    # closed-form result is -8.479 (see hand computation in test_estimator).
    assert result["posterior_mean"] == pytest.approx(-8.479, abs=0.01)
    assert result["posterior_sd"] == pytest.approx(2.6161, abs=0.01)
    assert result["num_observations"] == 1

    # experiment_results row written
    assert len(sb.tables["experiment_results"]) == 1
    er = sb.tables["experiment_results"][0]
    assert er["experiment_id"] == EXPERIMENT_ID
    assert "Alcohol" in er["summary_text"]
    assert "reduced" in er["summary_text"]

    # experiment marked completed
    assert sb.tables["experiments"][0]["status"] == "completed"

    # personal_estimate persisted
    pe = sb.tables["personal_estimates"][0]
    assert pe["num_observations"] == 1
    assert pe["posterior_mean"] == pytest.approx(-8.479, abs=0.01)


def test_non_compliance_days_are_dropped():
    sb = FakeSupabase()
    # Mark several non-compliant. The function should still proceed if
    # >=3 valid days remain per side.
    bad = {"2026-04-01", "2026-04-03", "2026-04-05"}  # three A days flipped
    _seed_alcohol_experiment(
        sb, date(2026, 4, 1), non_compliant_dates=bad,
    )
    result = analyze_experiment(EXPERIMENT_ID, sb)
    assert result["status"] == "completed"
    assert result["n_a"] == 4  # 7 A days - 3 non-compliant
    assert result["n_b"] == 7
    assert any(d["reason"] == "non_compliance" for d in result["dropped"])


def test_insufficient_data_returns_status_without_persisting():
    sb = FakeSupabase()
    # Drop most B-day HRV readings → not enough valid B days.
    drop = {f"2026-04-{i:02d}" for i in (3, 5, 7, 9, 11, 13)}  # 6 of 7 B-day HRVs
    _seed_alcohol_experiment(sb, date(2026, 4, 1), drop_dates=drop)

    result = analyze_experiment(EXPERIMENT_ID, sb)
    assert result["status"] == "insufficient_data"
    assert result["n_b"] < 3
    assert result["needed"] == 3

    # nothing should have been written
    assert sb.tables.get("experiment_results", []) == []
    assert sb.tables["experiments"][0]["status"] == "active"
    pe = sb.tables["personal_estimates"][0]
    assert pe["num_observations"] == 0


def test_summary_text_uses_increased_when_effect_positive():
    sb = FakeSupabase()
    # A days lower than B days → "increased"
    _seed_alcohol_experiment(sb, date(2026, 4, 1), a_hrv=50.0, b_hrv=60.0)
    result = analyze_experiment(EXPERIMENT_ID, sb)
    assert result["effect_estimate"] == pytest.approx(10.0)
    assert "increased" in result["summary_text"]
