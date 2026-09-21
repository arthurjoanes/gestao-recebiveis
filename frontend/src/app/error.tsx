"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="initial-loading">
      <h1>Falha ao carregar a página.</h1>

      <button className="button" onClick={reset}>
        Tentar novamente
      </button>
    </main>
  );
}
