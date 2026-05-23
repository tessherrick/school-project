"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Layout from "./components/Layout";
import { api, todayISO } from "./lib/api";

type DailyLog = {
  id: string;
  date: string;
  intervention_states: Record<string, boolean>;
};

type Reading = {
  date: string;
  hrv_rmssd: number | null;
  recovery_score: number | null;
};

type Posterior = {
  intervention_id: string;
  label: string;
  posterior_mean: number;
  num_observations: number;
};

export default function Home() {
  const [loggedToday, setLoggedToday] = useState<boolean | null>(null);
  const [reading, setReading] = useState<Reading | null | undefined>(undefined);
  const [posteriors, setPosteriors] = useState<Posterior[] | null>(null);

  useEffect(() => {
    const today = todayISO();
    api<DailyLog[]>("/api/logs?days=1")
      .then((logs) => setLoggedToday(logs.some((l) => l.date === today)))
      .catch(() => setLoggedToday(false));

    api<Reading[]>("/api/wearables/recent?limit=1")
      .then((rs) => setReading(rs[0] ?? null))
      .catch(() => setReading(null));

    api<Posterior[]>("/api/posteriors")
      .then(setPosteriors)
      .catch(() => setPosteriors([]));
  }, []);

  const completedCount =
    posteriors?.filter((p) => p.num_observations > 0).length ?? 0;

  const strongest =
    posteriors && posteriors.length > 0
      ? [...posteriors].sort(
          (a, b) => Math.abs(b.posterior_mean) - Math.abs(a.posterior_mean)
        )[0]
      : null;

  return (
    <Layout>
      <h1 className="font-serif text-[60px] leading-none tracking-tight">
        motif
      </h1>

      <div className="mt-12 flex flex-col gap-5">
        <Card>
          <CardLabel>Today</CardLabel>
          <CardBody>
            {loggedToday === null ? (
              <span className="text-muted">…</span>
            ) : loggedToday ? (
              <span>
                <span className="text-ochre">✓</span> Logged today
              </span>
            ) : (
              "Not logged yet"
            )}
          </CardBody>
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            <Link
              href="/log"
              className="font-medium text-ochre hover:underline"
            >
              {loggedToday ? "Update log" : "Log today"} →
            </Link>
            <Link
              href="/history"
              className="text-muted hover:text-ink hover:underline"
            >
              Fill in your history →
            </Link>
          </div>
        </Card>

        <Card>
          <CardLabel>Recovery</CardLabel>
          {reading === undefined && (
            <CardBody>
              <span className="text-muted">…</span>
            </CardBody>
          )}
          {reading === null && (
            <>
              <CardBody>No recent readings</CardBody>
              <CardAction href="/connect">Connect Whoop</CardAction>
            </>
          )}
          {reading && (
            <>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="font-serif text-5xl text-ochre">
                  {reading.hrv_rmssd != null
                    ? Math.round(reading.hrv_rmssd)
                    : "—"}
                </span>
                <span className="text-sm text-muted">ms HRV last night</span>
              </div>
              {reading.recovery_score != null && (
                <div className="mt-2 text-sm text-muted">
                  {reading.recovery_score}% recovery
                </div>
              )}
            </>
          )}
        </Card>

        <Card>
          <CardLabel>Body map</CardLabel>
          <CardBody>
            {posteriors === null
              ? "…"
              : completedCount === 0
              ? "What you've learned — nothing yet"
              : `What you've learned — ${completedCount} finding${
                  completedCount === 1 ? "" : "s"
                } so far`}
          </CardBody>
          {strongest && completedCount > 0 && (
            <div className="mt-3 text-sm">
              <span className="text-ink">{strongest.label}</span>
              <span className="text-muted"> — </span>
              <span
                className={
                  Math.abs(strongest.posterior_mean) > 3
                    ? "text-ochre"
                    : "text-muted"
                }
              >
                {formatEffect(strongest.posterior_mean)}
              </span>
            </div>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            <Link
              href="/body-map"
              className="font-medium text-ochre hover:underline"
            >
              {completedCount === 0 ? "Run your first experiment" : "Open body map"} →
            </Link>
            <Link
              href="/hypotheses"
              className="text-muted hover:text-ink hover:underline"
            >
              See what to test →
            </Link>
          </div>
        </Card>
      </div>
    </Layout>
  );
}

function formatEffect(v: number): string {
  const r = Math.round(v);
  const sign = r > 0 ? "+" : r < 0 ? "−" : "";
  const verb = r >= 0 ? "increase" : "reduction";
  return `${sign}${Math.abs(r)} ms HRV ${verb}`;
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <section className="border border-rule bg-surface p-6">
      {children}
    </section>
  );
}

function CardLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-xs uppercase tracking-widest text-muted">
      {children}
    </div>
  );
}

function CardBody({ children }: { children: React.ReactNode }) {
  return <div className="mt-2 text-lg text-ink">{children}</div>;
}

function CardAction({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="mt-5 inline-block text-sm font-medium text-ochre hover:underline"
    >
      {children} →
    </Link>
  );
}
