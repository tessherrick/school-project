"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import Layout from "../../components/Layout";
import { api, formatLongDate, todayISO } from "../../lib/api";

type ScheduleDay = {
  date: string;
  condition: "A" | "B";
  instruction: string;
};

type Experiment = {
  id: string;
  intervention_id: string;
  protocol_type: string;
  start_date: string;
  end_date: string;
  status: string;
  schedule: ScheduleDay[];
  interventions: { key: string; label: string } | null;
};

export default function ExperimentPage({
  params,
}: {
  params: { id: string };
}) {
  const { id } = params;
  const router = useRouter();
  const today = useMemo(() => todayISO(), []);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    let alive = true;
    api<Experiment[]>("/api/experiments")
      .then((rows) => {
        if (!alive) return;
        const found = rows.find((r) => r.id === id);
        if (!found) {
          setError("Experiment not found");
          return;
        }
        setExperiment(found);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [id]);

  async function complete() {
    if (!experiment) return;
    setCompleting(true);
    setError(null);
    try {
      await api("/api/experiments/complete", {
        method: "POST",
        body: { experiment_id: experiment.id },
      });
      setCompleted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCompleting(false);
    }
  }

  return (
    <Layout>
      {error && (
        <p className="text-sm text-muted">Something went wrong: {error}</p>
      )}
      {!experiment && !error && <p className="text-muted">Loading…</p>}

      {experiment && (
        <>
          <h1 className="font-serif text-5xl leading-tight">
            {experiment.interventions?.label ?? "Experiment"}
          </h1>
          <p className="mt-3 text-muted">
            14-day ABAB protocol — started{" "}
            {formatLongDate(experiment.start_date)}
          </p>

          <ul className="mt-10 divide-y divide-rule border-y border-rule">
            {experiment.schedule.map((day) => {
              const isToday = day.date === today;
              return (
                <li
                  key={day.date}
                  className={`grid grid-cols-[80px_60px_1fr_24px] items-center gap-4 py-3 ${
                    isToday ? "bg-paper" : ""
                  }`}
                >
                  <span
                    className={`text-sm ${
                      isToday ? "font-medium text-ochre" : "text-muted"
                    }`}
                  >
                    {shortDate(day.date)}
                  </span>
                  <span className="text-xs uppercase tracking-widest text-muted">
                    {day.condition}
                  </span>
                  <span className="text-sm text-ink">{day.instruction}</span>
                  <span className="text-ochre">{isToday ? "→" : ""}</span>
                </li>
              );
            })}
          </ul>

          <button
            onClick={complete}
            disabled={completing || completed}
            className="mt-8 w-full rounded-sm border border-ochre py-3 font-medium text-ochre transition-colors hover:bg-ochre hover:text-white disabled:opacity-60"
          >
            {completed
              ? "Completed — see body map"
              : completing
              ? "Analyzing…"
              : "Mark this experiment complete"}
          </button>
          {completed && (
            <button
              onClick={() => router.push("/body-map")}
              className="mt-3 w-full rounded-sm bg-ochre py-3 font-medium text-white"
            >
              Open body map
            </button>
          )}
        </>
      )}
    </Layout>
  );
}

function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
