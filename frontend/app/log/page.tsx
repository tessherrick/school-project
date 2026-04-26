"use client";

import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { api, formatLongDate, todayISO } from "../lib/api";

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

export default function LogPage() {
  const today = useMemo(() => todayISO(), []);
  const [interventions, setInterventions] = useState<Intervention[] | null>(
    null
  );
  const [states, setStates] = useState<Record<string, boolean>>({});
  const [recentLogs, setRecentLogs] = useState<DailyLog[]>([]);
  const [alreadyLogged, setAlreadyLogged] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [ivs, logs] = await Promise.all([
          api<Intervention[]>("/api/interventions"),
          api<DailyLog[]>("/api/logs?days=7"),
        ]);
        if (!alive) return;
        setInterventions(ivs);
        setRecentLogs(logs);
        const todays = logs.find((l) => l.date === today);
        const init: Record<string, boolean> = {};
        for (const iv of ivs) {
          init[iv.key] = todays?.intervention_states?.[iv.key] ?? false;
        }
        setStates(init);
        setAlreadyLogged(!!todays);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, [today]);

  function toggle(key: string) {
    setStates((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api("/api/logs", {
        method: "POST",
        body: { date: today, intervention_states: states },
      });
      const logs = await api<DailyLog[]>("/api/logs?days=7");
      setRecentLogs(logs);
      setAlreadyLogged(true);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Layout>
      <h1 className="font-serif text-5xl leading-tight">Log today</h1>
      <p className="mt-3 text-muted">{formatLongDate(today)}</p>

      {error && (
        <p className="mt-6 text-sm text-muted">Something went wrong: {error}</p>
      )}

      {!interventions && !error && (
        <p className="mt-10 text-muted">Loading…</p>
      )}

      {interventions && (
        <>
          {alreadyLogged && (
            <p className="mt-10 text-sm text-muted">
              Already logged today. Update if anything changed.
            </p>
          )}

          <ul className="mt-6 divide-y divide-rule border-y border-rule">
            {interventions.map((iv) => {
              const on = !!states[iv.key];
              return (
                <li
                  key={iv.id}
                  className="flex items-start justify-between gap-6 py-5"
                >
                  <div className="flex-1">
                    <div className="font-medium text-ink">{iv.label}</div>
                    <div className="mt-1 text-sm text-muted">
                      {iv.description}
                    </div>
                  </div>
                  <Toggle on={on} onClick={() => toggle(iv.key)} />
                </li>
              );
            })}
          </ul>

          <button
            onClick={save}
            disabled={saving}
            className="mt-8 w-full rounded-sm bg-ochre py-3 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {savedFlash ? "Saved" : saving ? "Saving…" : "Save today"}
          </button>

          <ThisWeek
            interventions={interventions}
            logs={recentLogs}
            today={today}
          />
        </>
      )}
    </Layout>
  );
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className={`relative h-7 w-12 flex-shrink-0 rounded-full border transition-colors ${
        on ? "border-ochre bg-ochre" : "border-rule bg-surface"
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full transition-all ${
          on ? "left-6 bg-white" : "left-0.5 bg-muted"
        }`}
      />
      <span className="sr-only">{on ? "yes" : "no"}</span>
    </button>
  );
}

function ThisWeek({
  interventions,
  logs,
  today,
}: {
  interventions: Intervention[];
  logs: DailyLog[];
  today: string;
}) {
  const days: { iso: string; label: string }[] = [];
  for (let i = 6; i >= 0; i--) {
    const [y, m, d] = today.split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    dt.setDate(dt.getDate() - i);
    const iso = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(
      2,
      "0"
    )}-${String(dt.getDate()).padStart(2, "0")}`;
    const label = dt.toLocaleDateString("en-US", { weekday: "narrow" });
    days.push({ iso, label });
  }

  const byDate = new Map(logs.map((l) => [l.date, l.intervention_states]));

  return (
    <section className="mt-12">
      <h2 className="font-serif text-2xl">This week</h2>
      <div className="mt-4 grid grid-cols-7 gap-2">
        {days.map(({ iso, label }) => {
          const states = byDate.get(iso);
          const dayNum = Number(iso.slice(-2));
          return (
            <div
              key={iso}
              title={iso}
              className="flex flex-col items-center gap-2"
            >
              <div className="text-xs text-muted">
                {label}
                <span className="ml-1 text-ink">{dayNum}</span>
              </div>
              <div className="flex flex-col gap-1.5">
                {interventions.map((iv) => {
                  if (!states) {
                    return <span key={iv.id} className="h-1.5 w-1.5" />;
                  }
                  const on = !!states[iv.key];
                  return (
                    <span
                      key={iv.id}
                      className={`h-1.5 w-1.5 rounded-full ${
                        on
                          ? "bg-ochre"
                          : "border border-rule bg-transparent"
                      }`}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
