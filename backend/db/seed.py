"""Seed interventions + test user + starting personal_estimates.

Idempotent: upserts on natural keys so re-running is safe. Uses the
service-role client (bypasses RLS) since this is an admin operation.

Run from the project root:
    python -m backend.db.seed
"""
from backend.db.client import service_client
from backend.db.queries import TEST_USER_EMAIL, TEST_USER_ID

INTERVENTIONS = [
    {
        "key": "alcohol_any",
        "label": "Alcohol",
        "description": (
            "Any alcoholic drink — beer, wine, spirits, cocktails. Strong "
            "population prior: the Whoop 2023 alcohol study found that 1–2 "
            "drinks reduced overnight HRV by up to 20%."
        ),
        "prior_mean_effect": -8,
        "prior_sd_effect": 3,
    },
    {
        "key": "dairy_any",
        "label": "Dairy",
        "description": (
            "Milk, cheese, yogurt, butter, cream — anything made from cow, "
            "goat, or sheep milk. Weak population prior; individual response "
            "varies widely, which is exactly what this app is built to tease apart."
        ),
        "prior_mean_effect": -2,
        "prior_sd_effect": 6,
    },
    {
        "key": "gluten_any",
        "label": "Gluten",
        "description": (
            "Wheat, barley, rye, and products made from them — bread, pasta, "
            "beer, most baked goods. Weak population prior; individual response "
            "varies widely."
        ),
        "prior_mean_effect": -2,
        "prior_sd_effect": 6,
    },
    {
        "key": "high_histamine_foods",
        "label": "High-histamine foods",
        "description": (
            "Aged cheeses, fermented foods (sauerkraut, kombucha, kimchi), "
            "leftovers, cured meats, and wine. Histamine content rises with "
            "age and fermentation and can drive inflammatory-feeling "
            "responses in sensitive individuals."
        ),
        "prior_mean_effect": -3,
        "prior_sd_effect": 5,
    },
    {
        "key": "high_fodmap_foods",
        "label": "High-FODMAP foods",
        "description": (
            "Fermentable carbs that can drive gut symptoms in sensitive "
            "people — onions, garlic, beans, wheat, and many stone fruits. "
            "Pooled clinical evidence supports a real effect in IBS-prone "
            "populations but not the general public."
        ),
        "prior_mean_effect": -2,
        "prior_sd_effect": 5,
    },
    {
        "key": "large_meal_700cal",
        "label": "Large meal (>700 cal in one sitting)",
        "description": (
            "A single sitting over ~700 calories. Heavy meals, especially "
            "later in the day, elevate resting heart rate and can suppress "
            "overnight recovery."
        ),
        "prior_mean_effect": -3,
        "prior_sd_effect": 4,
    },
    {
        "key": "late_night_eating",
        "label": "Eating within 2hr of bed",
        "description": (
            "Any meal or significant snack within two hours of going to "
            "sleep. Active digestion during sleep is consistently correlated "
            "with reduced HRV and sleep performance in wearable data."
        ),
        "prior_mean_effect": -4,
        "prior_sd_effect": 4,
    },
    {
        "key": "processed_seed_oils",
        "label": "Processed seed oils (cooking fat)",
        "description": (
            "Foods cooked in soybean, corn, canola, sunflower, or safflower "
            "oil. Short-term effects on HRV and recovery are inconclusive in "
            "the literature — genuinely neutral prior."
        ),
        "prior_mean_effect": 0,
        "prior_sd_effect": 5,
    },
]


def seed() -> None:
    sb = service_client()

    print("Upserting interventions...")
    sb.table("interventions").upsert(INTERVENTIONS, on_conflict="key").execute()

    print(f"Ensuring test user exists: {TEST_USER_EMAIL} (id {TEST_USER_ID})...")
    sb.table("users").upsert(
        [{"id": TEST_USER_ID, "email": TEST_USER_EMAIL}],
        on_conflict="id",
    ).execute()

    print("Fetching intervention ids to seed personal_estimates...")
    interventions = (
        sb.table("interventions")
        .select("id, key, prior_mean_effect, prior_sd_effect")
        .execute()
    ).data

    estimates = [
        {
            "user_id": TEST_USER_ID,
            "intervention_id": iv["id"],
            "posterior_mean": iv["prior_mean_effect"],
            "posterior_sd": iv["prior_sd_effect"],
            "num_observations": 0,
        }
        for iv in interventions
    ]
    sb.table("personal_estimates").upsert(
        estimates, on_conflict="user_id,intervention_id"
    ).execute()
    print(f"  wrote {len(estimates)} personal_estimates rows.")
    print("Done.")


if __name__ == "__main__":
    seed()
