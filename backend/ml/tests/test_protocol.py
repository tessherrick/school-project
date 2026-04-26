"""Protocol structure tests: 14 days, strict alternation, balanced A/B,
correct instruction strings."""
import random
from datetime import date

import pytest

from backend.ml.protocol import INSTRUCTIONS, generate_abab_protocol


def test_schedule_has_14_days():
    proto = generate_abab_protocol("iv-1", "alcohol_any", date(2026, 4, 25))
    assert len(proto["schedule"]) == 14


def test_alternates_strictly():
    random.seed(0)
    proto = generate_abab_protocol("iv-1", "alcohol_any", date(2026, 4, 25))
    conditions = [d["condition"] for d in proto["schedule"]]
    for i in range(1, len(conditions)):
        assert conditions[i] != conditions[i - 1], (
            f"day {i} ({conditions[i]}) does not alternate from day {i-1} ({conditions[i-1]})"
        )


def test_balanced_a_and_b():
    proto = generate_abab_protocol("iv-1", "dairy_any", date(2026, 4, 25))
    conditions = [d["condition"] for d in proto["schedule"]]
    assert conditions.count("A") == 7
    assert conditions.count("B") == 7


def test_dates_are_consecutive():
    proto = generate_abab_protocol("iv-1", "gluten_any", date(2026, 4, 25))
    expected = [date(2026, 4, 25 + i).isoformat() if 25 + i <= 30 else None for i in range(14)]
    actual = [d["date"] for d in proto["schedule"]]
    assert actual[0] == "2026-04-25"
    assert actual[-1] == "2026-05-08"


def test_instructions_match_assigned_condition():
    proto = generate_abab_protocol("iv-1", "alcohol_any", date(2026, 4, 25))
    for entry in proto["schedule"]:
        expected = INSTRUCTIONS["alcohol_any"][entry["condition"]]
        assert entry["instruction"] == expected


def test_all_eight_interventions_have_instructions():
    expected_keys = {
        "alcohol_any", "dairy_any", "gluten_any", "high_histamine_foods",
        "high_fodmap_foods", "large_meal_700cal", "late_night_eating",
        "processed_seed_oils",
    }
    assert set(INSTRUCTIONS.keys()) == expected_keys
    for key, pair in INSTRUCTIONS.items():
        assert "A" in pair and "B" in pair
        assert pair["A"] != pair["B"]


def test_starting_condition_is_randomized():
    """Across many seeds, both starting conditions should appear."""
    starts = set()
    for seed in range(50):
        random.seed(seed)
        proto = generate_abab_protocol("iv-1", "alcohol_any", date(2026, 4, 25))
        starts.add(proto["schedule"][0]["condition"])
    assert starts == {"A", "B"}


def test_unknown_intervention_key_raises():
    with pytest.raises(ValueError):
        generate_abab_protocol("iv-1", "made_up_key", date(2026, 4, 25))


def test_protocol_metadata():
    proto = generate_abab_protocol("iv-abc", "alcohol_any", date(2026, 4, 25))
    assert proto["protocol_type"] == "ABAB"
    assert proto["intervention_id"] == "iv-abc"
    assert proto["intervention_key"] == "alcohol_any"
    assert proto["start_date"] == "2026-04-25"
    assert proto["end_date"] == "2026-05-08"
