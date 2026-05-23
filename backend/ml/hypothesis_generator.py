"""Claude-powered next-experiment recommender.

Pulls the user's current personal posteriors, last 30 days of log/HRV pairs,
and recent experiment_results summaries, formats them as Markdown, and asks
Claude (via tool-use schema enforcement) to return 3-5 ranked hypotheses for
what to test next. Tool-use guarantees the response shape matches the schema
defined in HYPOTHESIS_TOOL below.

Voice rules in the system prompt mirror Motif's brand: observational, never
prescriptive, no praise, no hedging modal verbs. The model is instructed to
reference the user's actual posteriors, not population literature.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048
RECENT_LOG_WINDOW_DAYS = 30
RECENT_RESULTS_LIMIT = 5

SYSTEM_PROMPT = """You are the experiment designer for Motif, an autonomous n-of-1 nutrition research system. Your job is to recommend which experiment to run next, based on the user's actual data — not population studies.

Voice rules:
- Observational, never prescriptive. Say "your data shows X" — never "you should avoid X" or "you need to."
- Past tense for findings, present tense for what to test next.
- Never use "may", "might", "could potentially" — state what was found.
- Max 80 words per rationale.
- Never use phrases like "great choice", "well done", or any praise.
- Reference the user's actual posteriors and recent data, not literature.

Optimize for:
- High expected information gain. Interventions with wide posteriors (SD ≥ 4) are more informative to test than those already known (SD ≤ 2).
- Practical compliance. An experiment is worthless if the user can't reasonably comply.
- Surprise. If the data hints at something unexpected (e.g., processed_seed_oils showing a real effect despite mixed literature), prioritize that.

Constraints:
- Generate 3-5 hypotheses, ranked. Quality over quantity — 3 strong hypotheses beats 5 mediocre ones.
- Don't suggest interventions already at very low uncertainty (SD < 1.5) unless there's a specific reason.
- Use the submit_hypotheses tool. Do not respond in plain text."""


HYPOTHESIS_TOOL: dict[str, Any] = {
    "name": "submit_hypotheses",
    "description": "Submit ranked hypotheses for the next experiment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hypotheses": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "rank": {"type": "integer"},
                        "intervention_key": {
                            "type": "string",
                            "description": "Must exactly match one of the intervention keys from the data section.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Max 80 words. Observational voice. References user's actual data — posteriors, uncertainty, or paired observations.",
                        },
                        "what_to_test": {
                            "type": "string",
                            "description": "Specific protocol description. E.g., 'A 14-day ABAB protocol alternating dairy-present and dairy-absent days, with HRV measured the morning after each.'",
                        },
                        "expected_information_gain": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": [
                        "rank",
                        "intervention_key",
                        "rationale",
                        "what_to_test",
                        "expected_information_gain",
                    ],
                },
            },
            "summary": {
                "type": "string",
                "description": "One sentence summarizing what the user should focus on. Max 30 words. Observational voice.",
            },
        },
        "required": ["hypotheses", "summary"],
    },
}


def _fmt_signed(value: float) -> str:
    rounded = round(value, 1)
    if rounded == 0:
        return "0 ms"
    sign = "+" if rounded > 0 else "−"
    return f"{sign}{abs(rounded):.1f} ms"


def _load_estimates(
    user_id: str, supabase_client: Any
) -> list[dict[str, Any]]:
    """All 8 interventions with this user's personal_estimates joined in.

    Mirrors list_interventions_with_estimates but reuses the passed client so
    tests can pass a fake.
    """
    result = (
        supabase_client.table("interventions")
        .select(
            "id, key, label, description, prior_mean_effect, prior_sd_effect, "
            "personal_estimates(user_id, posterior_mean, posterior_sd, num_observations)"
        )
        .order("key")
        .execute()
    )
    rows: list[dict[str, Any]] = []
    for row in result.data:
        matching = [
            e
            for e in (row.get("personal_estimates") or [])
            if e.get("user_id") == user_id
        ]
        est = matching[0] if matching else None
        rows.append(
            {
                "id": row["id"],
                "key": row["key"],
                "label": row["label"],
                "description": row.get("description") or "",
                "posterior_mean": (
                    est["posterior_mean"]
                    if est
                    else row["prior_mean_effect"]
                ),
                "posterior_sd": (
                    est["posterior_sd"]
                    if est
                    else row["prior_sd_effect"]
                ),
                "num_observations": (
                    est["num_observations"] if est else 0
                ),
            }
        )
    return rows


def _load_recent_pairs(
    user_id: str, supabase_client: Any, window_days: int
) -> list[dict[str, Any]]:
    """Daily logs paired with the next-morning HRV reading, last `window_days`."""
    today = date.today()
    start = today - timedelta(days=window_days)
    log_rows = (
        supabase_client.table("daily_logs")
        .select("date, intervention_states")
        .eq("user_id", user_id)
        .gte("date", start.isoformat())
        .order("date", desc=True)
        .execute()
        .data
    )
    hrv_rows = (
        supabase_client.table("wearable_readings")
        .select("date, hrv_rmssd")
        .eq("user_id", user_id)
        .gte("date", start.isoformat())
        .execute()
        .data
    )
    hrv_by_date: dict[str, float] = {
        str(r["date"])[:10]: r["hrv_rmssd"]
        for r in hrv_rows
        if r.get("hrv_rmssd") is not None
    }
    pairs: list[dict[str, Any]] = []
    for log in log_rows:
        d_str = str(log["date"])[:10]
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        next_key = (d + timedelta(days=1)).isoformat()
        hrv = hrv_by_date.get(next_key)
        if hrv is None:
            continue
        states = log.get("intervention_states") or {}
        present = sorted(k for k, v in states.items() if v)
        absent = sorted(k for k, v in states.items() if v is False)
        pairs.append(
            {
                "date": d_str,
                "next_morning_hrv": round(float(hrv), 1),
                "present": present,
                "absent": absent,
            }
        )
    return pairs


def _load_recent_results(
    supabase_client: Any, limit: int
) -> list[dict[str, Any]]:
    """Most-recent experiment_results, both observational and structured.

    No user filter — single-tenant for now. Backfill rows have
    experiment_id = NULL; experiment rows carry it.
    """
    result = (
        supabase_client.table("experiment_results")
        .select("summary_text, effect_estimate, confidence, completed_at, experiment_id")
        .order("completed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def _format_user_prompt(
    estimates: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    lines: list[str] = []

    lines.append(
        "# Current personal effect estimates (ms RMSSD on next-morning HRV)"
    )
    lines.append("")
    lines.append("| Key | Label | Posterior | Uncertainty (SD) | Observations |")
    lines.append("|---|---|---|---|---|")
    for e in estimates:
        post = _fmt_signed(float(e["posterior_mean"] or 0.0))
        sd = float(e["posterior_sd"] or 0.0)
        lines.append(
            f"| `{e['key']}` | {e['label']} | {post} | ±{sd:.1f} | {e['num_observations']} |"
        )
    lines.append("")

    lines.append("## Intervention descriptions (literature priors, for context only)")
    lines.append("")
    for e in estimates:
        desc = (e.get("description") or "").strip()
        if desc:
            lines.append(f"- `{e['key']}`: {desc}")
    lines.append("")

    lines.append(f"# Recent paired data (last {RECENT_LOG_WINDOW_DAYS} days)")
    lines.append("")
    if not pairs:
        lines.append("_No log-to-HRV pairs in the recent window._")
    else:
        lines.append("Each row is a logged day plus the HRV measured the morning after.")
        lines.append("")
        lines.append("| Date | Next-morning HRV | Present | Absent |")
        lines.append("|---|---|---|---|")
        for p in pairs:
            present = ", ".join(p["present"]) if p["present"] else "—"
            absent = ", ".join(p["absent"]) if p["absent"] else "—"
            lines.append(
                f"| {p['date']} | {p['next_morning_hrv']} ms | {present} | {absent} |"
            )
    lines.append("")

    lines.append("# Recent experiment results")
    lines.append("")
    if not results:
        lines.append("_No completed experiments or backfill results yet._")
    else:
        for r in results:
            origin = "experiment" if r.get("experiment_id") else "observational backfill"
            effect = r.get("effect_estimate")
            effect_str = (
                _fmt_signed(float(effect)) if effect is not None else "—"
            )
            lines.append(
                f"- ({origin}) {r.get('summary_text', '').strip()} "
                f"[effect={effect_str}, confidence_z={round(float(r.get('confidence') or 0.0), 2)}]"
            )
    lines.append("")

    lines.append("# Your task")
    lines.append("")
    lines.append(
        "Generate 3-5 ranked hypotheses for what experiment to run next. "
        "Use only intervention keys from the table above. Call submit_hypotheses."
    )
    return "\n".join(lines)


def _extract_tool_input(message: Any) -> dict[str, Any]:
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_hypotheses":
            return dict(block.input)
    raise RuntimeError(
        f"Claude did not call submit_hypotheses. stop_reason={message.stop_reason}"
    )


def _validate(payload: dict[str, Any], valid_keys: set[str]) -> dict[str, Any]:
    hyps = payload.get("hypotheses") or []
    if not (3 <= len(hyps) <= 5):
        raise ValueError(f"Expected 3-5 hypotheses, got {len(hyps)}")
    cleaned: list[dict[str, Any]] = []
    for h in hyps:
        key = h.get("intervention_key")
        if key not in valid_keys:
            raise ValueError(f"Unknown intervention_key: {key}")
        gain = h.get("expected_information_gain")
        if gain not in ("high", "medium", "low"):
            raise ValueError(f"Bad expected_information_gain: {gain}")
        cleaned.append(
            {
                "rank": int(h["rank"]),
                "intervention_key": key,
                "rationale": str(h["rationale"]).strip(),
                "what_to_test": str(h["what_to_test"]).strip(),
                "expected_information_gain": gain,
            }
        )
    cleaned.sort(key=lambda h: h["rank"])
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise ValueError("Missing summary")
    return {"hypotheses": cleaned, "summary": summary}


def generate_hypotheses(
    user_id: str,
    supabase_client: Any,
    *,
    anthropic_client: Any | None = None,
) -> dict[str, Any]:
    """Build context from the user's data, ask Claude for ranked next-experiment
    hypotheses, return the validated structured payload.

    `anthropic_client` is injectable so tests can pass a fake. In production
    it's constructed lazily from ANTHROPIC_API_KEY in the environment.
    """
    estimates = _load_estimates(user_id, supabase_client)
    pairs = _load_recent_pairs(user_id, supabase_client, RECENT_LOG_WINDOW_DAYS)
    results = _load_recent_results(supabase_client, RECENT_RESULTS_LIMIT)

    user_prompt = _format_user_prompt(estimates, pairs, results)

    client = anthropic_client or anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"]
    )
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[HYPOTHESIS_TOOL],
        tool_choice={"type": "tool", "name": "submit_hypotheses"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = _extract_tool_input(message)
    validated = _validate(raw, {e["key"] for e in estimates})

    # Attach intervention id + label per hypothesis so the frontend can render
    # labels and POST to /experiments/start without a second lookup roundtrip.
    by_key = {e["key"]: e for e in estimates}
    for h in validated["hypotheses"]:
        meta = by_key[h["intervention_key"]]
        h["intervention_id"] = meta["id"]
        h["intervention_label"] = meta["label"]
        h["posterior_mean"] = round(float(meta["posterior_mean"] or 0.0), 2)
        h["posterior_sd"] = round(float(meta["posterior_sd"] or 0.0), 2)
        h["num_observations"] = meta["num_observations"]

    validated["generated_at"] = datetime.utcnow().isoformat() + "Z"
    return validated
