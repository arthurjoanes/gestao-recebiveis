"use client";
import { useState } from "react";
import { api, errorMessage, query } from "@/lib/api";
import { instant } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { Demo, Page, Receivable, Session } from "@/lib/types";
import { Alert, Badge, Loading } from "@/components/ui";

export function DemoView({
  session,
  onChange,
}: {
  session: Session;
  onChange: () => void;
}) {
  const [revision, setRevision] = useState(0);
  const demo = useResource<Demo>("/demo", revision);
  const [search, setSearch] = useState("");
  const titles = useResource<Page<Receivable>>(
    `/receivables?${query({ status: "open", q: search, page_size: 100 })}`,
    revision,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [clockError, setClockError] = useState("");
  const [success, setSuccess] = useState("");
  const operator = session.user.role === "operator";
  async function change(path: string, body: unknown, message: string) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api(
        path,
        { method: "POST", body: JSON.stringify(body) },
        session.csrf_token,
      );
      setSuccess(message);
      setRevision((value) => value + 1);
      onChange();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Demonstração</h1>
        </div>
      </div>
      <div className="info-banner">
        <strong>Ambiente de demonstração — mensagens simuladas</strong>
      </div>
      {error && <Alert>{error}</Alert>}
      {success && <Alert success>{success}</Alert>}
      {demo.error && <Alert>{demo.error}</Alert>}
      {demo.loading ? (
        <Loading />
      ) : (
        demo.data &&
        (!demo.data.enabled ? (
          <Alert>Controles desativados neste ambiente.</Alert>
        ) : (
          <>
            {!operator && (
              <div className="info-banner">
                Seu perfil permite apenas consulta.
              </div>
            )}
            <div className="demo-grid">
              <section className="panel padded">
                <p className="eyebrow">Relógio comercial</p>
                <h2>{instant(demo.data.business_now)}</h2>
                <p>São Paulo · America/Sao_Paulo</p>
                <p className="muted">
                  Vencimentos e pagamentos usam este relógio. Sessões e retries
                  usam o tempo real.
                </p>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    const value = new FormData(event.currentTarget).get(
                      "business_now",
                    );
                    const next = `${value}:00-03:00`;
                    if (
                      Date.parse(next) <= Date.parse(demo.data!.business_now)
                    ) {
                      setClockError(
                        "Informe data e hora posteriores ao relógio comercial atual.",
                      );
                      (
                        event.currentTarget.elements.namedItem(
                          "business_now",
                        ) as HTMLInputElement
                      )?.focus();
                      return;
                    }
                    setClockError("");
                    void change(
                      "/demo/clock",
                      { business_now: `${value}:00-03:00` },
                      "Data comercial avançada.",
                    );
                  }}
                >
                  <label>
                    Nova data e hora comercial
                    <input
                      name="business_now"
                      type="datetime-local"
                      min="1900-01-01T00:00"
                      max="2199-12-31T23:59"
                      aria-invalid={!!clockError}
                      aria-describedby={clockError ? "clock-error" : undefined}
                      required
                      disabled={!operator || busy}
                    />
                  </label>
                  <button
                    className="button"
                    disabled={!operator || busy}
                    type="submit"
                  >
                    Avançar relógio
                  </button>
                  {clockError && (
                    <p className="field-error" role="alert" id="clock-error">
                      {clockError}
                    </p>
                  )}
                </form>
              </section>
              <section className="panel padded">
                <h2>
                  {demo.data.worker_enabled ? "Worker ativo" : "Worker pausado"}
                </h2>
                <div
                  className={`worker-indicator ${demo.data.worker_enabled ? "is-active" : ""}`}
                >
                  <span />
                  {demo.data.worker_enabled
                    ? "Processando lembretes"
                    : "Escolha um cenário antes de iniciar"}
                </div>
                <p className="muted">
                  A pausa bloqueia novas tentativas. O agendamento continua;
                  tentativas autorizadas podem terminar.
                </p>
                <button
                  className="button"
                  disabled={!operator || busy}
                  onClick={() =>
                    void change(
                      "/demo/worker",
                      { enabled: !demo.data!.worker_enabled },
                      demo.data!.worker_enabled
                        ? "Novas tentativas pausadas. O agendamento continua."
                        : "Processamento retomado.",
                    )
                  }
                >
                  {busy
                    ? "Salvando…"
                    : demo.data.worker_enabled
                      ? "Pausar processamento"
                      : "Retomar processamento"}
                </button>
              </section>
            </div>
            <section className="panel padded">
              <h2>Escolher cenário de entrega</h2>
              <p className="muted">
                Configure antes da primeira tentativa do título.
              </p>
              <form
                className="scenario-search"
                onSubmit={(event) => {
                  event.preventDefault();
                  setSearch(
                    String(
                      new FormData(event.currentTarget).get("q") ?? "",
                    ).trim(),
                  );
                }}
              >
                <label>
                  Buscar título em aberto
                  <input
                    name="q"
                    type="search"
                    maxLength={200}
                    placeholder="Código ou nome do cliente"
                  />
                </label>
                <button className="button secondary" type="submit">
                  Buscar título
                </button>
              </form>
              {titles.error && <Alert>{titles.error}</Alert>}
              <form
                className="scenario-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  void change(
                    "/demo/scenario",
                    {
                      receivable_id: Number(form.get("receivable_id")),
                      scenario: form.get("scenario"),
                    },
                    "Cenário configurado. Retome o processamento.",
                  );
                }}
              >
                <label>
                  Título
                  <select
                    name="receivable_id"
                    required
                    disabled={!operator || busy || titles.loading}
                  >
                    <option value="">Selecione um título</option>
                    {titles.data?.items.map((item) => (
                      <option value={item.id} key={item.id}>
                        {item.external_receivable_id} · {item.customer_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Cenário
                  <select name="scenario" disabled={!operator || busy}>
                    <option value="success">Sucesso</option>
                    <option value="transient">
                      Falha transitória seguida de sucesso
                    </option>
                    <option value="permanent">Falha permanente</option>
                    <option value="response_lost">
                      Entrega aceita, resposta perdida
                    </option>
                    <option value="always_transient">
                      Falha transitória até o limite
                    </option>
                  </select>
                </label>
                <button
                  className="button"
                  type="submit"
                  disabled={!operator || busy || titles.loading}
                >
                  Aplicar cenário
                </button>
              </form>
              <div className="scenario-notes">
                <p>
                  <Badge status="retry_scheduled" /> Falha transitória agenda
                  retry, até cinco tentativas.
                </p>
                <p>
                  <Badge status="uncertain" /> Resposta perdida consulta a mesma
                  tentativa e chave de entrega.
                </p>
              </div>
            </section>
            <p className="footnote">
              Para restaurar a carteira, use o reset descrito no README, com API
              e worker parados.
            </p>
          </>
        ))
      )}
    </>
  );
}
