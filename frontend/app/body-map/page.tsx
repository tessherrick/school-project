"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";

type Posterior = {
  intervention_id: string;
  key: string;
  label: string;
  posterior_mean: number;
  posterior_sd: number;
  num_observations: number;
  num_experiments: number;
  prior_mean_effect: number | null;
  prior_sd_effect: number | null;
};

type Intervention = {
  id: string;
  key: string;
  description: string;
};

type SelectResponse = {
  intervention_id: string;
  intervention_key: string;
  intervention_label: string;
};

type StartResponse = {
  experiment: { id: string };
};

const RANGE = 15;

export default function BodyMapPage() {
  const router = useRouter();
  const [posteriors, setPosteriors] = useState<Posterior[] | null>(null);
  const [descriptions, setDescriptions] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [post, ivs] = await Promise.all([
          api<Posterior[]>("/api/posteriors"),
          api<Intervention[]>("/api/interventions"),
        ]);
        if (!alive) return;
        const sorted = [...post].sort(
          (a, b) => Math.abs(b.posterior_mean) - Math.abs(a.posterior_mean)
        );
        setPosteriors(sorted);
        const desc: Record<string, string> = {};
        for (const iv of ivs) desc[iv.id] = iv.description;
        setDescriptions(desc);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const completed = posteriors
    ? posteriors.filter((p) => p.num_observations > 0).length
    : 0;

  const subhead =
    completed === 0
      ? "Your starting point — based on what we expect from the literature."
      : completed <= 2
      ? "Early findings from your data."
      : "Your personal causal map.";

  async function runExperiment() {
    setStarting(true);
    setError(null);
    try {
      const pick = await api<SelectResponse>("/api/experiments/select", {
        method: "POST",
      });
      const started = await api<StartResponse>("/api/experiments/start", {
        method: "POST",
        body: { intervention_id: pick.intervention_id },
      });
      router.push(`/experiments/${started.experiment.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStarting(false);
    }
  }

  return (
    <Layout>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex-1">
          <h1 className="font-serif text-5xl leading-tight">
            What affects your recovery
          </h1>
          <p className="mt-3 text-muted">{subhead}</p>
          <Link
            href="/history"
            className="mt-2 inline-block text-sm text-ochre hover:underline"
          >
            Fill in your history →
          </Link>
        </div>
        <button
          onClick={runExperiment}
          disabled={starting}
          className="self-start rounded-sm border border-ochre px-4 py-2 text-sm font-medium text-ochre transition-colors hover:bg-ochre hover:text-white disabled:opacity-60"
        >
          {starting ? "Starting…" : "Run an experiment"}
        </button>
      </div>

      {error && (
        <p className="mt-6 text-sm text-muted">Something went wrong: {error}</p>
      )}

      {!posteriors && !error && (
        <p className="mt-10 text-muted">Loading…</p>
      )}

      {posteriors && (
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2">
          {posteriors.map((p) => (
            <PosteriorCard
              key={p.intervention_id}
              p={p}
              description={descriptions[p.intervention_id] ?? ""}
            />
          ))}
        </div>
      )}
    </Layout>
  );
}

function evidenceLabel(p: Posterior): string {
  const exp = p.num_experiments ?? 0;
  const hasObservational = p.num_observations > exp;
  if (exp === 0 && !hasObservational) return "no experiments yet";
  if (exp === 0 && hasObservational) return "From your history";
  if (exp > 0 && hasObservational) {
    return `${exp} experiment${exp === 1 ? "" : "s"} + history`;
  }
  return `${exp} experiment${exp === 1 ? "" : "s"} completed`;
}

function PosteriorCard({
  p,
  description,
}: {
  p: Posterior;
  description: string;
}) {
  const mean = p.posterior_mean;
  const rounded = Math.round(mean);
  const display = `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${Math.abs(
    rounded
  )} ms HRV`;
  const isStrong = Math.abs(mean) > 3;

  return (
    <article className="border border-rule bg-surface p-6">
      <div className="font-medium text-[18px] text-ink">{p.label}</div>
      <div
        className={`mt-3 font-serif text-[28px] leading-none ${
          isStrong ? "text-ochre" : "text-muted"
        }`}
      >
        {display}
      </div>
      <ConfidenceBar mean={mean} sd={p.posterior_sd} />
      <div className="mt-3 text-xs text-muted">{evidenceLabel(p)}</div>
      {description && (
        <div className="mt-4 text-[13px] text-muted">{description}</div>
      )}
    </article>
  );
}

function ConfidenceBar({ mean, sd }: { mean: number; sd: number }) {
  const clamp = (v: number) => Math.max(-RANGE, Math.min(RANGE, v));
  const pct = (v: number) => ((clamp(v) + RANGE) / (2 * RANGE)) * 100;
  const left = pct(mean - sd);
  const right = pct(mean + sd);
  const tick = pct(mean);
  const zero = pct(0);

  return (
    <div className="mt-4">
      <div className="relative h-2 w-full bg-paper">
        <span
          className="absolute top-0 h-full w-px bg-rule"
          style={{ left: `${zero}%` }}
        />
        <span
          className="absolute top-0 h-full"
          style={{
            left: `${left}%`,
            width: `${Math.max(right - left, 0.5)}%`,
            backgroundColor: "rgba(184, 118, 58, 0.18)",
          }}
        />
        <span
          className="absolute top-[-2px] h-3 w-[2px] bg-ochre"
          style={{ left: `calc(${tick}% - 1px)` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-muted">
        <span>−15</span>
        <span>0</span>
        <span>+15</span>
      </div>
    </div>
  );
}
