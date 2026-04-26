"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";

type Reading = {
  date: string;
  hrv_rmssd: number | null;
  recovery_score: number | null;
};

type Intervention = {
  id: string;
  key: string;
  label: string;
  description: string;
};

type DailyLog = {
  id: string;
  date: string;
  intervention_states: Record<string, boolean>;
};

type BackfillDetail = {
  key: string;
  status: "updated" | "insufficient_data";
  effect?: number;
  n_a: number;
  n_b: number;
};

type BackfillResult = {
  interventions_updated: number;
  interventions_insufficient: number;
  paired_days: number;
  details: BackfillDetail[];
};

type PillState = "unset" | "yes" | "no";
type PageStates = Record<string, Record<string, PillState>>; // date -> key -> state

function nextPillState(s: PillState): PillState {
  if (s === "unset") return "yes";
  if (s === "yes") return "no";
  return "unset";
}

function shortLabel(label: string): string {
  // Compact label for the pill row — take first word for most, but
  // a couple of interventions need a different shorthand.
  return label.split(" ")[0];
}

function longDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export default function HistoryPage() {
  const [readings, setReadings] = useState<Reading[] | null>(null);
  const [interventions, setInterventions] = useState<Intervention[] | null>(
    null
  );
  const [states, setStates] = useState<PageStates>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backfill, setBackfill] = useState<BackfillResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [rs, ivs, logs] = await Promise.all([
          api<Reading[]>("/api/wearables/all"),
          api<Intervention[]>("/api/interventions"),
          api<DailyLog[]>("/api/logs?days=365"),
        ]);
        if (!alive) return;
        setReadings(rs);
        setInterventions(ivs);
        const init: PageStates = {};
        for (const r of rs) {
          init[r.date] = {};
          for (const iv of ivs) init[r.date][iv.key] = "unset";
        }
        for (const log of logs) {
          if (!init[log.date]) continue;
          const logged = log.intervention_states || {};
          for (const iv of ivs) {
            if (iv.key in logged) {
              init[log.date][iv.key] = logged[iv.key] ? "yes" : "no";
            }
          }
        }
        setStates(init);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const completedRowCount = useMemo(() => {
    let n = 0;
    for (const date of Object.keys(states)) {
      const row = states[date];
      if (Object.values(row).some((v) => v !== "unset")) n++;
    }
    return n;
  }, [states]);

  function cyclePill(date: string, key: string) {
    setStates((prev) => ({
      ...prev,
      [date]: { ...prev[date], [key]: nextPillState(prev[date][key]) },
    }));
  }

  async function saveAll() {
    if (!interventions || !readings) return;
    setSaving(true);
    setError(null);
    setBackfill(null);
    try {
      for (const r of readings) {
        const row = states[r.date] || {};
        const filled: Record<string, boolean> = {};
        for (const iv of interventions) {
          const s = row[iv.key];
          if (s === "yes") filled[iv.key] = true;
          else if (s === "no") filled[iv.key] = false;
        }
        if (Object.keys(filled).length === 0) continue;
        await api("/api/logs", {
          method: "POST",
          body: { date: r.date, intervention_states: filled },
        });
      }
      const result = await api<BackfillResult>("/api/backfill/run", {
        method: "POST",
      });
      setBackfill(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function rerunAnalysis() {
    setAnalyzing(true);
    setError(null);
    try {
      const result = await api<BackfillResult>("/api/backfill/run", {
        method: "POST",
      });
      setBackfill(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <Layout>
      <h1 className="font-serif text-5xl leading-tight">Fill in your history</h1>
      <p className="mt-3 text-muted">
        Approximate is fine. The system marks observational data as weaker
        evidence than experiments.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          onClick={saveAll}
          disabled={saving || !readings || completedRowCount === 0}
          className="rounded-sm bg-ochre px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving
            ? "Saving…"
            : `Save all${
                completedRowCount > 0 ? ` (${completedRowCount} day${
                  completedRowCount === 1 ? "" : "s"
                })` : ""
              }`}
        </button>
        <button
          onClick={rerunAnalysis}
          disabled={analyzing}
          className="rounded-sm border border-rule px-4 py-2 text-sm text-ink transition-colors hover:border-ochre hover:text-ochre disabled:opacity-50"
        >
          {analyzing ? "Analyzing…" : "Re-run analysis"}
        </button>
      </div>

      {backfill && (
        <div className="mt-6 border border-rule bg-surface px-4 py-3 text-sm">
          <div className="text-ink">
            Updated {backfill.interventions_updated} of{" "}
            {backfill.interventions_updated + backfill.interventions_insufficient}{" "}
            interventions from your historical data.{" "}
            <Link href="/body-map" className="text-ochre hover:underline">
              Open body map →
            </Link>
          </div>
          {backfill.paired_days > 0 && (
            <div className="mt-1 text-xs text-muted">
              Paired {backfill.paired_days} log/HRV days.
            </div>
          )}
        </div>
      )}

      {error && (
        <p className="mt-6 text-sm text-muted">Something went wrong: {error}</p>
      )}

      {!readings || !interventions ? (
        <p className="mt-10 text-muted">Loading…</p>
      ) : readings.length === 0 ? (
        <p className="mt-10 text-sm text-muted">
          No wearable readings yet — connect Whoop and sync first.
        </p>
      ) : (
        <ul className="mt-8 divide-y divide-rule border-y border-rule">
          {readings.map((r) => (
            <li key={r.date} className="py-5">
              <div className="flex items-baseline justify-between gap-4">
                <div className="font-medium text-ink">{longDate(r.date)}</div>
                <div className="text-xs text-muted">
                  {r.hrv_rmssd != null
                    ? `${r.hrv_rmssd.toFixed(0)} ms HRV`
                    : "—"}
                  {r.recovery_score != null
                    ? ` · ${r.recovery_score}% recovery`
                    : ""}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {interventions.map((iv) => {
                  const s = states[r.date]?.[iv.key] ?? "unset";
                  return (
                    <Pill
                      key={iv.id}
                      label={shortLabel(iv.label)}
                      state={s}
                      onClick={() => cyclePill(r.date, iv.key)}
                    />
                  );
                })}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}

function Pill({
  label,
  state,
  onClick,
}: {
  label: string;
  state: PillState;
  onClick: () => void;
}) {
  const base =
    "rounded-sm px-2.5 py-1 text-xs transition-colors select-none";
  const cls =
    state === "yes"
      ? `${base} border border-ochre bg-ochre text-white`
      : state === "no"
      ? `${base} border border-ink text-ink line-through`
      : `${base} border border-rule text-muted hover:border-ink hover:text-ink`;
  return (
    <button onClick={onClick} className={cls} aria-pressed={state === "yes"}>
      {label}
    </button>
  );
}
