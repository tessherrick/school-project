"""Bayesian update math is fully closed-form, so every test asserts a
hand-computed expected value. If a number drifts, something is wrong
with the conjugate update — not the noise model."""
import math

import pytest

from backend.ml.estimator import PersonalEstimator, bayesian_update
from backend.ml.tests._fakes import FakeSupabase


def test_bayesian_update_neutral_prior():
    """Prior N(0, 5²), one observation x̂=-10 from n_A=n_B=7, σ²=100."""
    post_mean, post_sd = bayesian_update(
        prior_mean=0.0, prior_sd=5.0,
        effect_estimate=-10.0, n_control=7, n_treatment=7,
    )
    assert post_mean == pytest.approx(-4.6667, abs=0.01)
    assert post_sd == pytest.approx(3.6515, abs=0.01)


def test_bayesian_update_alcohol_prior():
    """Prior N(-8, 3²) (the seeded alcohol prior), x̂=-12 from n_A=n_B=7."""
    post_mean, post_sd = bayesian_update(
        prior_mean=-8.0, prior_sd=3.0,
        effect_estimate=-12.0, n_control=7, n_treatment=7,
    )
    # Hand computation:
    #   prior_precision = 1/9
    #   likelihood_precision = 7/200
    #   posterior_precision = 263/1800
    #   posterior_mean = (-8/9 + -12*7/200) / (263/1800) = -2356/263 ≈ -8.9582
    #   posterior_sd = sqrt(1800/263) ≈ 2.6161
    assert post_mean == pytest.approx(-8.9582, abs=0.01)
    assert post_sd == pytest.approx(2.6161, abs=0.01)


def test_sequential_updates_shrink_posterior():
    """Each new observation should reduce posterior_sd (more data, more confidence)."""
    mean1, sd1 = bayesian_update(0.0, 5.0, -10.0, 7, 7)
    mean2, sd2 = bayesian_update(mean1, sd1, -8.0, 7, 7)
    mean3, sd3 = bayesian_update(mean2, sd2, -9.0, 7, 7)
    assert sd2 < sd1
    assert sd3 < sd2
    # mean should also be drifting toward the observations
    assert mean1 < 0
    assert mean3 < mean1 or abs(mean3) > abs(mean1)


def test_update_increments_observations_and_persists():
    sb = FakeSupabase()
    iv_id = "iv-1"
    sb.tables["interventions"] = [{
        "id": iv_id, "key": "alcohol_any", "label": "Alcohol",
        "prior_mean_effect": -8.0, "prior_sd_effect": 3.0,
    }]
    sb.tables["personal_estimates"] = [{
        "user_id": "u1", "intervention_id": iv_id,
        "posterior_mean": -8.0, "posterior_sd": 3.0, "num_observations": 0,
    }]
    est = PersonalEstimator("u1", sb)

    new_mean, new_sd, new_n = est.update(iv_id, -12.0, 7, 7)
    assert new_mean == pytest.approx(-8.9582, abs=0.01)
    assert new_sd == pytest.approx(2.6161, abs=0.01)
    assert new_n == 1

    # And it should be persisted
    persisted = sb.tables["personal_estimates"][0]
    assert persisted["num_observations"] == 1
    assert persisted["posterior_mean"] == pytest.approx(-8.9582, abs=0.01)


def test_reset_to_prior_restores_seeded_values():
    sb = FakeSupabase()
    iv_id = "iv-1"
    sb.tables["interventions"] = [{
        "id": iv_id, "key": "alcohol_any", "label": "Alcohol",
        "prior_mean_effect": -8.0, "prior_sd_effect": 3.0,
    }]
    sb.tables["personal_estimates"] = [{
        "user_id": "u1", "intervention_id": iv_id,
        "posterior_mean": -2.0, "posterior_sd": 1.5, "num_observations": 5,
    }]
    est = PersonalEstimator("u1", sb)
    mean, sd, n = est.reset_to_prior(iv_id)
    assert mean == -8.0
    assert sd == 3.0
    assert n == 0
    persisted = sb.tables["personal_estimates"][0]
    assert persisted["posterior_mean"] == -8.0
    assert persisted["num_observations"] == 0


def test_get_all_posteriors_orders_by_absolute_mean():
    sb = FakeSupabase()
    sb.tables["interventions"] = [
        {"id": "iv-1", "key": "alcohol_any", "label": "Alcohol",
         "prior_mean_effect": -8.0, "prior_sd_effect": 3.0},
        {"id": "iv-2", "key": "dairy_any", "label": "Dairy",
         "prior_mean_effect": -2.0, "prior_sd_effect": 6.0},
        {"id": "iv-3", "key": "gluten_any", "label": "Gluten",
         "prior_mean_effect": 0.0, "prior_sd_effect": 5.0},
    ]
    sb.tables["personal_estimates"] = [
        {"user_id": "u1", "intervention_id": "iv-1",
         "posterior_mean": -8.0, "posterior_sd": 3.0, "num_observations": 0},
        {"user_id": "u1", "intervention_id": "iv-2",
         "posterior_mean": -2.0, "posterior_sd": 6.0, "num_observations": 0},
        {"user_id": "u1", "intervention_id": "iv-3",
         "posterior_mean": 5.0, "posterior_sd": 5.0, "num_observations": 0},
    ]
    est = PersonalEstimator("u1", sb)
    rows = est.get_all_posteriors()
    means = [r["posterior_mean"] for r in rows]
    assert [abs(m) for m in means] == sorted([abs(m) for m in means], reverse=True)
    assert rows[0]["key"] == "alcohol_any"


def test_falls_back_to_prior_if_no_estimate_row():
    sb = FakeSupabase()
    sb.tables["interventions"] = [{
        "id": "iv-x", "key": "gluten_any", "label": "Gluten",
        "prior_mean_effect": -2.0, "prior_sd_effect": 6.0,
    }]
    # no personal_estimates row at all
    est = PersonalEstimator("u1", sb)
    mean, sd, n = est.get_posterior("iv-x")
    assert mean == -2.0
    assert sd == 6.0
    assert n == 0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        bayesian_update(0.0, 5.0, -10.0, 0, 7)
    with pytest.raises(ValueError):
        bayesian_update(0.0, 0.0, -10.0, 7, 7)
