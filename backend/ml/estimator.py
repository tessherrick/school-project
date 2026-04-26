"""Per-user Bayesian estimator over intervention effect sizes.

Closed-form Gaussian conjugate updates (no MCMC). The likelihood for one
experiment is Normal(x̂, σ²/n_A + σ²/n_B), where x̂ is the observed effect
(mean HRV on B days minus mean on A days) and σ² is the assumed
within-subject HRV noise variance — hard-coded at 100 (SD of 10ms RMSSD
day-to-day).

Effect units are milliseconds RMSSD throughout; nothing is normalized.
"""
from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_NOISE_VAR = 100.0  # day-to-day RMSSD variance, SD = 10ms


def bayesian_update(
    prior_mean: float,
    prior_sd: float,
    effect_estimate: float,
    n_control: int,
    n_treatment: int,
    noise_var: float = DEFAULT_NOISE_VAR,
) -> tuple[float, float]:
    """Conjugate Gaussian update with known likelihood variance.

    Returns (posterior_mean, posterior_sd).
    """
    if n_control < 1 or n_treatment < 1:
        raise ValueError("n_control and n_treatment must be >= 1")
    if prior_sd <= 0:
        raise ValueError("prior_sd must be > 0")

    se_sq = noise_var / n_control + noise_var / n_treatment
    prior_precision = 1.0 / (prior_sd ** 2)
    likelihood_precision = 1.0 / se_sq
    posterior_precision = prior_precision + likelihood_precision
    posterior_mean = (
        prior_mean * prior_precision + effect_estimate * likelihood_precision
    ) / posterior_precision
    posterior_sd = float(np.sqrt(1.0 / posterior_precision))
    return float(posterior_mean), posterior_sd


class PersonalEstimator:
    """Holds posteriors over the 8 interventions for a single user.

    On construction, loads intervention metadata + the user's
    personal_estimates rows. Falls back to the prior for any intervention
    that has no estimate row yet. Pass supabase_client=None to skip DB
    I/O (tests inject state directly via the public mutators).
    """

    def __init__(self, user_id: str, supabase_client: Any):
        self.user_id = user_id
        self.client = supabase_client
        self._posteriors: dict[str, dict[str, Any]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        if supabase_client is not None:
            self._load_state()

    def _load_state(self) -> None:
        ivs = (
            self.client.table("interventions")
            .select("id, key, label, prior_mean_effect, prior_sd_effect")
            .execute()
            .data
        )
        for iv in ivs:
            self._meta[iv["id"]] = iv

        ests = (
            self.client.table("personal_estimates")
            .select("intervention_id, posterior_mean, posterior_sd, num_observations")
            .eq("user_id", self.user_id)
            .execute()
            .data
        )
        for e in ests:
            self._posteriors[e["intervention_id"]] = {
                "posterior_mean": e["posterior_mean"],
                "posterior_sd": e["posterior_sd"],
                "num_observations": e["num_observations"],
            }
        for iv_id, iv in self._meta.items():
            if iv_id not in self._posteriors:
                self._posteriors[iv_id] = {
                    "posterior_mean": iv["prior_mean_effect"],
                    "posterior_sd": iv["prior_sd_effect"],
                    "num_observations": 0,
                }

    def set_state(
        self,
        intervention_id: str,
        meta: dict[str, Any],
        posterior: dict[str, Any],
    ) -> None:
        """Test hook: inject metadata + posterior for an intervention without DB."""
        self._meta[intervention_id] = meta
        self._posteriors[intervention_id] = dict(posterior)

    def get_posterior(self, intervention_id: str) -> tuple[float, float, int]:
        p = self._posteriors[intervention_id]
        return (
            float(p["posterior_mean"]),
            float(p["posterior_sd"]),
            int(p["num_observations"]),
        )

    def get_all_posteriors(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for iv_id, meta in self._meta.items():
            p = self._posteriors[iv_id]
            rows.append(
                {
                    "intervention_id": iv_id,
                    "key": meta.get("key"),
                    "label": meta.get("label"),
                    "posterior_mean": float(p["posterior_mean"]),
                    "posterior_sd": float(p["posterior_sd"]),
                    "num_observations": int(p["num_observations"]),
                    "prior_mean_effect": meta.get("prior_mean_effect"),
                    "prior_sd_effect": meta.get("prior_sd_effect"),
                }
            )
        rows.sort(key=lambda r: abs(r["posterior_mean"]), reverse=True)
        return rows

    def update(
        self,
        intervention_id: str,
        effect_estimate: float,
        n_control: int,
        n_treatment: int,
    ) -> tuple[float, float, int]:
        cur = self._posteriors[intervention_id]
        new_mean, new_sd = bayesian_update(
            float(cur["posterior_mean"]),
            float(cur["posterior_sd"]),
            float(effect_estimate),
            int(n_control),
            int(n_treatment),
        )
        new_n = int(cur["num_observations"]) + 1
        self._posteriors[intervention_id] = {
            "posterior_mean": new_mean,
            "posterior_sd": new_sd,
            "num_observations": new_n,
        }
        self._persist(intervention_id, new_mean, new_sd, new_n)
        return new_mean, new_sd, new_n

    def reset_to_prior(self, intervention_id: str) -> tuple[float, float, int]:
        meta = self._meta[intervention_id]
        new_mean = float(meta["prior_mean_effect"])
        new_sd = float(meta["prior_sd_effect"])
        self._posteriors[intervention_id] = {
            "posterior_mean": new_mean,
            "posterior_sd": new_sd,
            "num_observations": 0,
        }
        self._persist(intervention_id, new_mean, new_sd, 0)
        return new_mean, new_sd, 0

    def _persist(
        self,
        intervention_id: str,
        posterior_mean: float,
        posterior_sd: float,
        num_observations: int,
    ) -> None:
        if self.client is None:
            return
        self.client.table("personal_estimates").upsert(
            {
                "user_id": self.user_id,
                "intervention_id": intervention_id,
                "posterior_mean": posterior_mean,
                "posterior_sd": posterior_sd,
                "num_observations": num_observations,
            },
            on_conflict="user_id,intervention_id",
        ).execute()
