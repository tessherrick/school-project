"""Thompson sampling bandit over the user's intervention posteriors.

Picks the next experiment by drawing one sample from each posterior and
ranking by |sample| + 0.5 * posterior_sd. The absolute value handles
"useful negative effects" (alcohol hurts HRV, that's still informative);
the small uncertainty bonus keeps high-variance interventions in the
running so we don't get stuck exploiting an early lucky draw.
"""
from __future__ import annotations

import random
from typing import Any, Optional

from backend.ml.estimator import PersonalEstimator

UNCERTAINTY_BONUS = 0.5


def _rationale(sampled_value: float, posterior_sd: float, all_sds: list[float]) -> str:
    """Cheap label for the UI: largest expected effect, highest uncertainty, or balanced."""
    max_sd = max(all_sds) if all_sds else posterior_sd
    if posterior_sd >= 0.95 * max_sd:
        return "highest uncertainty"
    if abs(sampled_value) >= 1.5 * posterior_sd:
        return "largest expected effect"
    return "balanced"


def _score_candidates(
    estimator: PersonalEstimator,
    exclude_intervention_ids: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    exclude = set(exclude_intervention_ids or [])
    rows = estimator.get_all_posteriors()
    candidates: list[dict[str, Any]] = []
    all_sds = [r["posterior_sd"] for r in rows if r["intervention_id"] not in exclude]
    for r in rows:
        if r["intervention_id"] in exclude:
            continue
        sampled = random.gauss(r["posterior_mean"], r["posterior_sd"])
        score = abs(sampled) + UNCERTAINTY_BONUS * r["posterior_sd"]
        candidates.append(
            {
                "intervention_id": r["intervention_id"],
                "intervention_key": r["key"],
                "intervention_label": r["label"],
                "sampled_value": sampled,
                "current_posterior_mean": r["posterior_mean"],
                "current_posterior_sd": r["posterior_sd"],
                "num_observations": r["num_observations"],
                "score": score,
                "rationale": _rationale(sampled, r["posterior_sd"], all_sds),
            }
        )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def select_next_experiment(
    estimator: PersonalEstimator,
    exclude_intervention_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Return the single highest-scoring intervention. Raises if nothing eligible."""
    candidates = _score_candidates(
        estimator, set(exclude_intervention_ids or [])
    )
    if not candidates:
        raise ValueError("No eligible interventions to select from.")
    return candidates[0]


def select_next_experiment_diagnostic(
    estimator: PersonalEstimator,
    exclude_intervention_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Full ranked list — used by the frontend to preview next-best candidates."""
    return _score_candidates(estimator, set(exclude_intervention_ids or []))
