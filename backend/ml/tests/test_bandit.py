"""Thompson sampling tests. Frequency-based: run many trials, then check
that exploration actually favors high-uncertainty interventions."""
import random
from collections import Counter

from backend.ml.bandit import (
    select_next_experiment,
    select_next_experiment_diagnostic,
)
from backend.ml.estimator import PersonalEstimator
from backend.ml.tests._fakes import FakeSupabase


def _build_estimator(state: list[dict]) -> PersonalEstimator:
    """Build a no-DB estimator with explicit posteriors for each intervention."""
    est = PersonalEstimator(user_id="u1", supabase_client=None)
    for s in state:
        est.set_state(
            intervention_id=s["id"],
            meta={
                "id": s["id"], "key": s["key"], "label": s["label"],
                "prior_mean_effect": s["mean"], "prior_sd_effect": s["sd"],
            },
            posterior={
                "posterior_mean": s["mean"], "posterior_sd": s["sd"],
                "num_observations": s.get("n", 0),
            },
        )
    return est


def test_high_uncertainty_intervention_is_picked_more_often():
    random.seed(42)
    state = [
        {"id": "iv-low",  "key": "low_unc",  "label": "Low Unc",
         "mean": 0.0, "sd": 0.5},
        {"id": "iv-mid",  "key": "mid_unc",  "label": "Mid Unc",
         "mean": 0.0, "sd": 3.0},
        {"id": "iv-high", "key": "high_unc", "label": "High Unc",
         "mean": 0.0, "sd": 7.0},
    ]
    est = _build_estimator(state)

    counts = Counter()
    for _ in range(1000):
        choice = select_next_experiment(est)
        counts[choice["intervention_key"]] += 1

    assert counts["high_unc"] > counts["mid_unc"] > counts["low_unc"]
    # high-uncertainty should dominate by a wide margin
    assert counts["high_unc"] > 500


def test_returns_required_fields():
    random.seed(0)
    est = _build_estimator([
        {"id": "iv-1", "key": "alcohol_any", "label": "Alcohol",
         "mean": -8.0, "sd": 3.0},
    ])
    pick = select_next_experiment(est)
    for field in (
        "intervention_id", "intervention_key", "intervention_label",
        "sampled_value", "current_posterior_mean", "current_posterior_sd",
        "num_observations", "rationale",
    ):
        assert field in pick, f"missing field {field!r}"
    assert pick["intervention_key"] == "alcohol_any"


def test_exclude_skips_intervention():
    random.seed(0)
    est = _build_estimator([
        {"id": "iv-1", "key": "alcohol_any", "label": "Alcohol",
         "mean": -8.0, "sd": 3.0},
        {"id": "iv-2", "key": "dairy_any", "label": "Dairy",
         "mean": -2.0, "sd": 6.0},
    ])
    for _ in range(20):
        pick = select_next_experiment(est, exclude_intervention_ids=["iv-1"])
        assert pick["intervention_id"] == "iv-2"


def test_diagnostic_returns_full_ranked_list():
    random.seed(0)
    est = _build_estimator([
        {"id": "iv-1", "key": "alcohol_any", "label": "Alcohol",
         "mean": -8.0, "sd": 3.0},
        {"id": "iv-2", "key": "dairy_any", "label": "Dairy",
         "mean": -2.0, "sd": 6.0},
        {"id": "iv-3", "key": "gluten_any", "label": "Gluten",
         "mean": 0.0, "sd": 5.0},
    ])
    ranked = select_next_experiment_diagnostic(est)
    assert len(ranked) == 3
    scores = [c["score"] for c in ranked]
    assert scores == sorted(scores, reverse=True)


def test_largest_expected_effect_rationale_for_strong_prior():
    """An intervention with a big mean and small sd should usually be tagged
    'largest expected effect', not 'highest uncertainty'."""
    random.seed(123)
    est = _build_estimator([
        {"id": "iv-1", "key": "alcohol_any", "label": "Alcohol",
         "mean": -15.0, "sd": 1.0},
        {"id": "iv-2", "key": "dairy_any", "label": "Dairy",
         "mean": 0.0, "sd": 2.0},
    ])
    rationales = Counter()
    for _ in range(50):
        pick = select_next_experiment(est)
        if pick["intervention_key"] == "alcohol_any":
            rationales[pick["rationale"]] += 1
    assert rationales["largest expected effect"] > 0
