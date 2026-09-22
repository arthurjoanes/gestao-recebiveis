"use client";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { date, instant, money, reminderStage, nextAttempt } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { ReceivableDetail, Session } from "@/lib/types";
import { Alert, Badge, Empty, Icon, Loading, Modal } from "@/components/ui";

export function ReceivableDetailView({
  id,
  session,
  onBack,
  onReminder,
}: {
  id: number;
  session: Session;
  onBack: () => void;
  onReminder: (id: number) => void;
}) {
  const [revision, setRevision] = useState(0);
  const result = useResource<ReceivableDetail>(`/receivables/${id}`, revision);
  const [action, setAction] = useState<"pay" | "cancel" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [paymentKey, setPaymentKey] = useState("");
  const data = result.data;
  async function submit(form: HTMLFormElement) {
    const values = new FormData(form);
    if (
      action === "cancel" &&
      String(values.get("reason") ?? "").trim().length < 3
    ) {
      setError(
        "Informe um motivo com pelo menos 3 caracteres, sem contar espaços nas pontas.",
      );
      (form.elements.namedItem("reason") as HTMLTextAreaElement)?.focus();
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (action === "pay")
        await api(
          `/receivables/${id}/payments`,
          {
            method: "POST",
            body: JSON.stringify({
              idempotency_key: paymentKey,
              note: String(values.get("note") ?? ""),
            }),
          },
          session.csrf_token,
        );
      else
        await api(
          `/receivables/${id}/cancel`,
          {
            method: "POST",
            body: JSON.stringify({
              reason: String(values.get("reason") ?? ""),
            }),
          },
          session.csrf_token,
        );
      setSuccess(
        action === "pay" ? "Pagamento registrado." : "Título cancelado.",
      );
      setAction(null);
      setRevision((value) => value + 1);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="text-button back-button" onClick={onBack}>
        Voltar para títulos
      </button>
      {result.error && <Alert>{result.error}</Alert>}
      {result.loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="page-heading">
              <div>
                <h1>{data.external_receivable_id}</h1>
                <p className="title-customer">{data.customer_name}</p>
              </div>
              <div className="button-group">
                <button
                  className="button secondary"
                  onClick={() => setRevision((value) => value + 1)}
                >
                  <Icon name="refresh" /> Atualizar
                </button>
              </div>
            </div>
            {success && <Alert success>{success}</Alert>}
            <div className="detail-grid">
              <section
                className="panel detail-summary"
                aria-label="Dados do título"
              >
                <div className="invoice-decision">
                  <div className="invoice-balance">
                    <h2>Valor do título</h2>
                    <strong className="detail-amount">
                      {money(data.amount_cents)}
                    </strong>
                    <div className="invoice-state">
                      <Badge status={data.overdue ? "overdue" : data.status} />
                      <span>Vencimento: {date(data.due_date)}</span>
                    </div>
                  </div>
                  {data.status === "open" &&
                    session.user.role === "operator" && (
                      <div className="invoice-actions">
                        <button
                          className="button"
                          onClick={() => {
                            setAction("pay");
                            setPaymentKey(crypto.randomUUID());
                            setError("");
                          }}
                        >
                          Registrar pagamento
                        </button>
                        <button
                          className="button danger-outline"
                          onClick={() => {
                            setAction("cancel");
                            setError("");
                          }}
                        >
                          Cancelar título
                        </button>
                      </div>
                    )}
                </div>
                <p className="footnote">
                  A baixa quita o valor integral e cancela os lembretes
                  pendentes. Uma tentativa de envio já autorizada pode terminar.
                </p>
                <dl>
                  <div>
                    <dt>E-mail do cliente</dt>
                    <dd>{data.customer_email}</dd>
                  </div>
                  <div>
                    <dt>Sistema de origem</dt>
                    <dd>{data.source_system}</dd>
                  </div>
                  <div>
                    <dt>Descrição</dt>
                    <dd>{data.description}</dd>
                  </div>
                  {data.payment && (
                    <>
                      <div>
                        <dt>Pagamento integral</dt>
                        <dd>{money(data.payment.amount_cents)}</dd>
                      </div>
                      <div>
                        <dt>Data comercial da baixa</dt>
                        <dd>{instant(data.payment.paid_at)}</dd>
                      </div>
                      <div>
                        <dt>Registro da baixa</dt>
                        <dd>{instant(data.payment.recorded_at)}</dd>
                      </div>
                    </>
                  )}
                </dl>
              </section>
              <section className="panel">
                <div className="section-heading">
                  <div>
                    <h2>Linha do tempo</h2>
                    <p>Importação, alterações e registro da baixa.</p>
                  </div>
                </div>
                {data.events.length ? (
                  <ol className="timeline">
                    {data.events.map((event) => (
                      <li key={event.id}>
                        <div className="timeline-dot" />
                        <p className="timeline-message">{event.message}</p>
                        <p className="timeline-date">
                          Registrado em {instant(event.occurred_at)}
                        </p>
                        <small>
                          Data comercial: {instant(event.business_at)}
                        </small>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <Empty title="Sem eventos" />
                )}
              </section>
            </div>
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Lembretes deste título</h2>
                </div>
              </div>
              {data.reminders.length ? (
                <div
                  className="table-scroll"
                  role="region"
                  aria-label="Tabela com rolagem horizontal"
                  tabIndex={0}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Etapa</th>
                        <th>Situação</th>
                        <th>Tentativas</th>
                        <th>Próxima tentativa</th>
                        <th>Ação</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.reminders.map((job) => (
                        <tr key={job.id}>
                          <td>{reminderStage(job.stage)}</td>
                          <td>
                            <Badge status={job.status} />
                          </td>
                          <td>{job.attempts_count}</td>
                          <td>{nextAttempt(job)}</td>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => onReminder(job.id)}
                            >
                              Ver tentativas
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty title="Nenhum lembrete planejado">
                  Aguardando a próxima etapa pela data comercial.
                </Empty>
              )}
            </section>
          </>
        )
      )}
      {action && data && (
        <Modal
          title={
            action === "pay"
              ? "Registrar pagamento integral"
              : "Cancelar este título"
          }
          busy={busy}
          onClose={() => setAction(null)}
        >
          <p>
            {data.external_receivable_id} · {data.customer_name}
          </p>
          <p className="modal-amount">{money(data.amount_cents)}</p>
          <p>
            {action === "pay"
              ? `O título ${data.external_receivable_id} será quitado pelo valor integral. A baixa usa a data comercial atual e cancela os lembretes pendentes.`
              : "O título sai da carteira em aberto, sem registrar pagamento."}
          </p>
          {error && (
            <div id="cancellation-error">
              <Alert>{error}</Alert>
            </div>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit(event.currentTarget);
            }}
          >
            {action === "pay" ? (
              <label>
                Observação (opcional)
                <textarea
                  name="note"
                  disabled={busy}
                  maxLength={500}
                  placeholder="Ex.: recebimento no ERP"
                />
              </label>
            ) : (
              <label>
                Motivo do cancelamento
                <textarea
                  name="reason"
                  disabled={busy}
                  aria-invalid={!!error}
                  aria-describedby={error ? "cancellation-error" : undefined}
                  minLength={3}
                  maxLength={500}
                  required
                  placeholder="Motivo"
                />
              </label>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => setAction(null)}
              >
                Voltar
              </button>
              <button
                type="submit"
                className={`button ${action === "cancel" ? "danger" : ""}`}
                disabled={busy}
              >
                {busy
                  ? "Registrando…"
                  : action === "pay"
                    ? "Confirmar pagamento"
                    : "Confirmar cancelamento"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
