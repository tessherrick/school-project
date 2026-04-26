"use client";

import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";

type SyncResult = {
  synced_recovery: number;
  synced_sleep: number;
  dates: string[];
};

type Reading = {
  date: string;
  hrv_rmssd: number | null;
  recovery_score: number | null;
  resting_hr: number | null;
  sleep_performance: number | null;
  source: string;
};

export default function Connect() {
  const [success, setSuccess] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readings, setReadings] = useState<Reading[] | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSuccess(params.get("success") === "true");
    loadReadings();
  }, []);

  async function loadReadings() {
    try {
      const data = await api<Reading[]>("/api/wearables/recent?limit=10");
      setReadings(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleConnect() {
    setError(null);
    setConnecting(true);
    try {
      const { authorize_url } = await api<{ authorize_url: string }>(
        "/api/auth/whoop/login"
      );
      window.location.href = authorize_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setConnecting(false);
    }
  }

  async function handleSync() {
    setError(null);
    setSyncing(true);
    try {
      const result = await api<SyncResult>("/api/whoop/sync", {
        method: "POST",
      });
      setSyncResult(result);
      await loadReadings();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Layout>
      <h1 className="font-serif text-5xl leading-tight">Connect Whoop</h1>
      <p className="mt-3 text-muted">
        Authorize Motif to read your recovery, sleep, and HRV data.
      </p>

      {error && (
        <p className="mt-6 text-sm text-muted">Something went wrong: {error}</p>
      )}

      {!success && (
        <section className="mt-10">
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="rounded-sm bg-ochre px-5 py-3 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {connecting ? "Redirecting…" : "Connect Whoop"}
          </button>
        </section>
      )}

      {success && (
        <section className="mt-10">
          <p className="text-sm text-ink">
            Whoop connected. Pull in your last 30 days of data.
          </p>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="mt-4 rounded-sm bg-ochre px-5 py-3 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {syncing ? "Syncing…" : "Sync last 30 days"}
          </button>
          {syncResult && (
            <p className="mt-4 text-sm text-muted">
              Synced {syncResult.synced_recovery} recovery and{" "}
              {syncResult.synced_sleep} sleep records across{" "}
              {syncResult.dates.length} day{syncResult.dates.length === 1 ? "" : "s"}.
            </p>
          )}
        </section>
      )}

      <section className="mt-14">
        <h2 className="font-serif text-2xl">Recent readings</h2>
        {readings === null && (
          <p className="mt-4 text-muted">Loading…</p>
        )}
        {readings && readings.length === 0 && (
          <p className="mt-4 text-sm text-muted">No readings yet.</p>
        )}
        {readings && readings.length > 0 && (
          <table className="mt-4 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-xs uppercase tracking-widest text-muted">
                <th className="py-3 pr-4 font-normal">Date</th>
                <th className="py-3 pr-4 font-normal">HRV</th>
                <th className="py-3 pr-4 font-normal">Recovery</th>
                <th className="py-3 pr-4 font-normal">RHR</th>
                <th className="py-3 pr-4 font-normal">Sleep</th>
              </tr>
            </thead>
            <tbody>
              {readings.map((r) => (
                <tr key={r.date} className="border-b border-rule last:border-b-0">
                  <td className="py-3 pr-4 text-ink">{r.date}</td>
                  <td className="py-3 pr-4 text-ink">
                    {r.hrv_rmssd != null ? r.hrv_rmssd.toFixed(1) : "—"}
                  </td>
                  <td className="py-3 pr-4 text-ink">
                    {r.recovery_score ?? "—"}
                  </td>
                  <td className="py-3 pr-4 text-ink">{r.resting_hr ?? "—"}</td>
                  <td className="py-3 pr-4 text-ink">
                    {r.sleep_performance ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </Layout>
  );
}
