"use client";

import { useEffect, useState } from "react";

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

const API = process.env.NEXT_PUBLIC_API_URL;

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
      const res = await fetch(`${API}/api/wearables/recent?limit=10`);
      if (!res.ok) throw new Error(await res.text());
      setReadings(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleConnect() {
    setError(null);
    setConnecting(true);
    try {
      const res = await fetch(`${API}/api/auth/whoop/login`);
      if (!res.ok) throw new Error(await res.text());
      const { authorize_url } = await res.json();
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
      const res = await fetch(`${API}/api/whoop/sync`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setSyncResult(await res.json());
      await loadReadings();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncing(false);
    }
  }

  return (
    <main className="min-h-screen p-16 font-mono max-w-3xl">
      <h1 className="text-2xl font-bold mb-8">Connect your Whoop</h1>

      {error && (
        <p className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-6 text-sm whitespace-pre-wrap">
          {error}
        </p>
      )}

      {!success && (
        <section className="mb-10">
          <p className="text-gray-600 mb-4 text-sm">
            Authorize Motif to read your Whoop recovery, sleep, and profile data.
          </p>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="bg-black text-white px-5 py-2 rounded disabled:opacity-50"
          >
            {connecting ? "Redirecting…" : "Connect Whoop"}
          </button>
        </section>
      )}

      {success && (
        <section className="mb-10">
          <p className="bg-green-50 border border-green-200 text-green-800 rounded p-3 mb-4 text-sm">
            Whoop connected. Pull in the last 30 days of data next.
          </p>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="bg-black text-white px-5 py-2 rounded disabled:opacity-50"
          >
            {syncing ? "Syncing…" : "Sync my last 30 days"}
          </button>
          {syncResult && (
            <pre className="bg-gray-100 rounded p-4 text-xs mt-4">
              {JSON.stringify(syncResult, null, 2)}
            </pre>
          )}
        </section>
      )}

      <section>
        <h2 className="text-sm uppercase tracking-widest text-gray-500 mb-3">
          Recent wearable readings
        </h2>
        {readings === null && <p className="text-gray-400 text-sm">Loading…</p>}
        {readings && readings.length === 0 && (
          <p className="text-gray-400 text-sm">No readings yet.</p>
        )}
        {readings && readings.length > 0 && (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4">Date</th>
                <th className="py-2 pr-4">HRV</th>
                <th className="py-2 pr-4">Recovery</th>
                <th className="py-2 pr-4">RHR</th>
                <th className="py-2 pr-4">Sleep %</th>
                <th className="py-2 pr-4">Source</th>
              </tr>
            </thead>
            <tbody>
              {readings.map((r) => (
                <tr key={r.date} className="border-b last:border-b-0">
                  <td className="py-2 pr-4">{r.date}</td>
                  <td className="py-2 pr-4">
                    {r.hrv_rmssd != null ? r.hrv_rmssd.toFixed(1) : "—"}
                  </td>
                  <td className="py-2 pr-4">{r.recovery_score ?? "—"}</td>
                  <td className="py-2 pr-4">{r.resting_hr ?? "—"}</td>
                  <td className="py-2 pr-4">{r.sleep_performance ?? "—"}</td>
                  <td className="py-2 pr-4 text-gray-500">{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
