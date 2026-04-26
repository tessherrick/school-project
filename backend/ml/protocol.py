"""ABAB experiment protocol generator.

A 14-day strictly-alternating schedule of A (intervention absent) and B
(intervention present). The starting condition is randomized per
experiment for counterbalancing — half the time the user starts on A,
half on B — so order effects don't bias the estimate.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

PROTOCOL_DAYS = 14

INSTRUCTIONS: dict[str, dict[str, str]] = {
    "alcohol_any": {
        "A": "Avoid all alcohol today.",
        "B": "Drink as you normally would (1+ drinks).",
    },
    "dairy_any": {
        "A": "Avoid all dairy products today.",
        "B": "Eat dairy as you normally would.",
    },
    "gluten_any": {
        "A": "Avoid all gluten today (no wheat, barley, or rye).",
        "B": "Eat gluten-containing foods as you normally would.",
    },
    "high_histamine_foods": {
        "A": "Avoid high-histamine foods (aged cheese, fermented foods, leftovers, cured meat, wine).",
        "B": "Eat at least one high-histamine food today.",
    },
    "high_fodmap_foods": {
        "A": "Avoid high-FODMAP foods (onion, garlic, beans, wheat, stone fruit).",
        "B": "Eat high-FODMAP foods as you normally would.",
    },
    "large_meal_700cal": {
        "A": "Keep every meal under ~700 calories today.",
        "B": "Eat at least one meal over ~700 calories today.",
    },
    "late_night_eating": {
        "A": "Stop eating at least 2 hours before bed.",
        "B": "Eat or snack within 2 hours of going to sleep.",
    },
    "processed_seed_oils": {
        "A": "Avoid foods cooked in seed oils (soybean, corn, canola, sunflower, safflower).",
        "B": "Eat foods cooked in seed oils as you normally would.",
    },
}


def generate_abab_protocol(
    intervention_id: str,
    intervention_key: str,
    start_date: date,
    num_blocks: int = 7,
) -> dict[str, Any]:
    """Build a 14-day alternating schedule. num_blocks kept for API compat."""
    if intervention_key not in INSTRUCTIONS:
        raise ValueError(f"No instructions defined for intervention key: {intervention_key}")

    starts_on_b = random.choice([0, 1]) == 1
    schedule: list[dict[str, Any]] = []
    for i in range(PROTOCOL_DAYS):
        is_b_day = (i % 2 == 1) if not starts_on_b else (i % 2 == 0)
        condition = "B" if is_b_day else "A"
        day = start_date + timedelta(days=i)
        schedule.append(
            {
                "date": day.isoformat(),
                "condition": condition,
                "instruction": INSTRUCTIONS[intervention_key][condition],
            }
        )

    end_date = start_date + timedelta(days=PROTOCOL_DAYS - 1)
    return {
        "protocol_type": "ABAB",
        "intervention_id": intervention_id,
        "intervention_key": intervention_key,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "schedule": schedule,
    }
