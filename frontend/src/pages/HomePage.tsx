import { useEffect, useState } from "react";

import { fetchHealth, type HealthResponse } from "../api/health.ts";

type HealthState =
  { kind: "loading" } | { kind: "loaded"; health: HealthResponse } | { kind: "failed" };

function statusText(state: HealthState): string {
  switch (state.kind) {
    case "loading":
      return "Проверяем…";
    case "failed":
      return "Сервер недоступен";
    case "loaded":
      return state.health.status === "ok" ? "Сервер работает" : "База данных недоступна";
  }
}

export function HomePage() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((health) => {
        setState({ kind: "loaded", health });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error);
          setState({ kind: "failed" });
        }
      });
    return () => {
      controller.abort();
    };
  }, []);

  const ok = state.kind === "loaded" && state.health.status === "ok";

  return (
    <main className="page">
      <h1>Fintech MVP</h1>
      <p className="muted">Кошелёк, подписки и цифровые товары в одном месте.</p>
      <section className="card" aria-live="polite">
        <span className={`dot ${ok ? "dot-ok" : state.kind === "loading" ? "" : "dot-error"}`} />
        <span data-testid="health-status">{statusText(state)}</span>
      </section>
    </main>
  );
}
