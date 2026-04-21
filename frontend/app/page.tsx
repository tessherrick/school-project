"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  env_check: {
    anthropic_key_set: boolean;
    supabase_url_set: boolean;
    whoop_client_id_set: boolean;
  };
};

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/health`)
      .then((res) => res.json())
      .then(setHealth)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main className="min-h-screen p-16 font-mono">
      <h1 className="text-2xl font-bold mb-8">Motif N1 — Scaffold Check</h1>

      <section className="mb-6">
        <h2 className="text-sm uppercase tracking-widest text-gray-500 mb-2">
          Backend Health
        </h2>
        {error && (
          <p className="text-red-500">
            Could not reach backend: {error}
            <br />
            <span className="text-gray-400 text-xs">
              Make sure the FastAPI server is running on port 8000.
            </span>
          </p>
        )}
        {health && (
          <pre className="bg-gray-100 rounded p-4 text-sm">
            {JSON.stringify(health, null, 2)}
          </pre>
        )}
        {!health && !error && (
          <p className="text-gray-400">Calling backend…</p>
        )}
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-widest text-gray-500 mb-2">
          Frontend Config
        </h2>
        <pre className="bg-gray-100 rounded p-4 text-sm">
          {JSON.stringify(
            { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL },
            null,
            2
          )}
        </pre>
      </section>
    </main>
  );
}
