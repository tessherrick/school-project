"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";

type Hypothesis = {
  rank: number;
  intervention_key: string;
  intervention_id: string;
  intervention_label: string;
  rationale: string;
  what_to_test: string;
  expected_information_gain: "high" | "medium" | "low";
  posterior_mean: number;
  posterior_sd: number;
  num_observations: number;
};

type HypothesesPayload = {
  summary: string;
  hypotheses: Hypothesis[];
  generated_at: string;
  cached: boolean;
};

type StartResponse = { experiment: { id: string } };

export default function HypothesesPage() {
  const router = useRouter();
  const [data, setData] = useState<HypothesesPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startingKey, setStartingKey] = useState<string | null>(null);

  const fetchHypotheses = useCallback(async () => {
    setError(null);
    setData(null);
    try {
      const result = await api<HypothesesPayload>(
        "/api/hypotheses/generate",
        { method: "POST", body: {} }
      );
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    fetchHypotheses();
  }, [fetchHypotheses]);

  async function startExperiment(h: Hypothesis) {
    setStartingKey(h.intervention_key);
    setError(null);
    try {
      const started = await api<StartResponse>("/api/experiments/start", {
        method: "POST",
        body: { intervention_id: h.intervention_id },
      });
      router.push(`/experiments/${started.experiment.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStartingKey(null);
    }
  }

  return (
    <Layout>
      <h1 className="font-serif text-5xl leading-tight">What to test next</h1>

      {!data && !error && (
        <p className="mt-6 text-muted">
          Generating<span className="inline-block animate-pulse">…</span>
        </p>
      )}

      {error && (
        <div className="mt-8 border border-rule bg-surface p-6">
          <p className="text-sm text-ink">
            Something went wrong generating hypotheses.
          </p>
          <p className="mt-2 text-xs text-muted">{error}</p>
          <button
            onClick={fetchHypotheses}
            className="mt-4 text-sm font-medium text-ochre hover:underline"
          >
            Try again →
          </button>
        </div>
      )}

      {data && (
        <>
          <p className="mt-4 text-lg text-muted">{data.summary}</p>

          <div className="mt-10 flex flex-col gap-6">
            {data.hypotheses.map((h) => (
              <HypothesisCard
                key={h.intervention_key}
                h={h}
                starting={startingKey === h.intervention_key}
                disabled={startingKey !== null}
                onStart={() => startExperiment(h)}
              />
            ))}
          </div>
        </>
      )}
    </Layout>
  );
}

function HypothesisCard({
  h,
  starting,
  disabled,
  onStart,
}: {
  h: Hypothesis;
  starting: boolean;
  disabled: boolean;
  onStart: () => void;
}) {
  return (
    <article className="border border-rule bg-surface p-6">
      <div className="flex items-baseline gap-3">
        <span className="text-xs font-medium uppercase tracking-widest text-ochre">
          #{h.rank}
        </span>
        <h2 className="text-[18px] font-medium text-ink">
          {h.intervention_label}
        </h2>
      </div>

      <p className="mt-3 text-base leading-relaxed text-ink">{h.rationale}</p>

      <p className="mt-4 text-[14px] italic leading-relaxed text-muted">
        {h.what_to_test}
      </p>

      <div className="mt-4">
        <InfoGainBadge gain={h.expected_information_gain} />
      </div>

      <button
        onClick={onStart}
        disabled={disabled}
        className="mt-6 w-full rounded-sm bg-ochre px-4 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {starting ? "Starting…" : "Start this experiment"}
      </button>
    </article>
  );
}

function InfoGainBadge({ gain }: { gain: "high" | "medium" | "low" }) {
  const cls =
    gain === "high"
      ? "border-ochre bg-ochre/10 text-ochre"
      : gain === "medium"
      ? "border-rule text-muted"
      : "border-rule text-muted opacity-60";
  return (
    <span
      className={`inline-block rounded-sm border px-2 py-0.5 text-[11px] lowercase tracking-wide ${cls}`}
    >
      {gain} information gain
    </span>
  );
}
