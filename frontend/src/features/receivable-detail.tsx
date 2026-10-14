"use client";
import { RouteLink } from "@/lib/workspace-route";
import { useEffect, useState } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import {
  brlInput,
  date,
  instant,
  money,
  parseBrl,
  reminderStage,
  nextAttempt,
} from "@/lib/format";
import {
  clearPaymentIntent,
  PAYMENT_INTENT_TTL_MS,
  readPaymentIntent,
  savePaymentIntent,
} from "@/lib/payment-intent";
import { useResource } from "@/lib/use-resource";
import type { Payment, ReceivableDetail, Session } from "@/lib/types";
import {
  Alert,
  Badge,
  Empty,
  Icon,
  Loading,
  Modal,
  Pagination,
} from "@/components/ui";

export function ReceivableDetailView({
  id,
  session,
  onBack,
  onReminder,
  onStatement,
  backLabel = "Voltar para títulos",
}: {
  id: number;
  session: Session;
  onBack: () => void;
  onReminder: (id: number) => void;
  onStatement: (customerId: number) => void;
  backLabel?: string;
}) {
  const [revision, setRevision] = useState(0);
  const [historyPages, setHistoryPages] = useState({
    payments: 1,
    events: 1,
    reminders: 1,
  });
  const result = useResource<ReceivableDetail>(
    `/receivables/${id}?payment_page=${historyPages.payments}&event_page=${historyPages.events}&reminder_page=${historyPages.reminders}`,
    revision,
  );
  const [action, setAction] = useState<"pay" | "cancel" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [local, setLocal] = useState(() => {
    try {
      const intent = readPaymentIntent(session.user.id, id);
      return {
        intent,
        expired:
          !!intent && Date.now() - intent.created_at >= PAYMENT_INTENT_TTL_MS,
        error: "",
      };
    } catch (failure) {
      return { intent: null, expired: false, error: errorMessage(failure) };
    }
  });
  const [paymentMode, setPaymentMode] = useState("remaining");
  const [amountError, setAmountError] = useState("");
  const [noteError, setNoteError] = useState("");
  const [historyChecked, setHistoryChecked] = useState(false);
  const [amountDraft, setAmountDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const data = result.data;
  useEffect(() => {
    if (amountError && action === "pay" && !busy && !local.intent)
      document.getElementById("payment-amount")?.focus();
  }, [amountError, action, busy, local.intent]);
  let draftAmount: string | null = null;
  if (data && !local.intent && !local.error) {
    try {
      draftAmount =
        paymentMode === "remaining"
          ? data.remaining_cents
          : parseBrl(amountDraft);
      if (
        BigInt(draftAmount) <= 0n ||
        BigInt(draftAmount) > BigInt(data.remaining_cents)
      )
        draftAmount = null;
    } catch {
      draftAmount = null;
    }
  }
  function openPayment() {
    setAction("pay");
    setError("");
    setAmountError("");
    setNoteError("");
    setHistoryChecked(false);
    if (local.intent)
      setLocal((value) => ({
        ...value,
        expired: Date.now() - local.intent!.created_at >= PAYMENT_INTENT_TTL_MS,
      }));
  }
  async function submit(form: HTMLFormElement) {
    const resolvingPending = local.intent !== null;
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
    let intent = local.intent;
    if (action === "pay") {
      const expired =
        !!intent && Date.now() - intent.created_at >= PAYMENT_INTENT_TTL_MS;
      if (expired && !local.expired)
        setLocal((value) => ({ ...value, expired: true }));
      if (local.error || (expired && !historyChecked)) return;
      if (!intent) {
        if (String(values.get("note") ?? "").trim().length > 500) {
          setNoteError("Use até 500 caracteres na observação.");
          (form.elements.namedItem("note") as HTMLTextAreaElement)?.focus();
          return;
        }
        let amount: string;
        try {
          amount =
            paymentMode === "partial"
              ? parseBrl(amountDraft)
              : data!.remaining_cents;
          if (BigInt(amount) <= 0n)
            throw new Error(
              "Não há saldo para este recebimento. Atualize o título.",
            );
          if (data && BigInt(amount) > BigInt(data.remaining_cents))
            throw new Error("O pagamento não pode exceder o saldo atual.");
        } catch (failure) {
          if (paymentMode === "partial") setAmountError(errorMessage(failure));
          else setError(errorMessage(failure));
          (form.elements.namedItem("amount") as HTMLInputElement)?.focus();
          return;
        }
        intent = {
          version: 1,
          user_id: session.user.id,
          receivable_id: id,
          created_at: Date.now(),
          payload: {
            idempotency_key: crypto.randomUUID(),
            note: noteDraft,
            amount_cents: amount,
          },
          preview: {
            remaining_before_cents: data!.remaining_cents,
            remaining_after_cents: (
              BigInt(data!.remaining_cents) - BigInt(amount)
            ).toString(),
          },
        };
        try {
          savePaymentIntent(intent);
          setLocal({ intent, expired: false, error: "" });
        } catch {
          setError(
            "O navegador bloqueou o armazenamento da intenção. Libere o armazenamento da sessão para registrar com segurança.",
          );
          return;
        }
      }
    }
    setBusy(true);
    setError("");
    try {
      if (action === "pay" && intent) {
        const payment = await api<Payment>(
          `/receivables/${id}/payments`,
          {
            method: "POST",
            body: JSON.stringify(intent.payload),
          },
          session.csrf_token,
        );
        if (
          !payment ||
          !Number.isInteger(payment.id) ||
          typeof payment.amount_cents !== "string"
        )
          throw new ApiError(
            0,
            "invalid_response",
            "A resposta não confirmou o recebimento. Tente novamente com a mesma intenção.",
          );
        clearPaymentIntent(session.user.id, id);
        setLocal({ intent: null, expired: false, error: "" });
        setAmountDraft("");
        setNoteDraft("");
        setPaymentMode("remaining");
        setSuccess(
          `Pagamento registrado: ${money(payment.amount_cents)}. Confira o saldo atualizado abaixo.`,
        );
      } else
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
      if (action === "cancel") setSuccess("Título cancelado.");
      setAction(null);
      setRevision((value) => value + 1);
    } catch (failure) {
      setError(errorMessage(failure));
      // Estes códigos de domínio ocorrem após lookup da chave e provam ausência
      // de recebimento. Validação 422 só resolve uma tentativa inicial.
      if (
        action === "pay" &&
        failure instanceof ApiError &&
        ((!resolvingPending && failure.status === 422) ||
          [
            "invalid_payment_amount",
            "invalid_transition",
            "not_found",
          ].includes(failure.code))
      ) {
        clearPaymentIntent(session.user.id, id);
        if (intent) {
          setPaymentMode(intent.payload.amount_cents ? "partial" : "remaining");
          setAmountDraft(
            intent.payload.amount_cents
              ? brlInput(intent.payload.amount_cents)
              : amountDraft,
          );
          setNoteDraft(intent.payload.note);
        }
        setLocal({ intent: null, expired: false, error: "" });
        if (failure.code === "invalid_payment_amount")
          setAmountError(
            "O saldo mudou. Confira o saldo atualizado e informe um valor até esse saldo.",
          );
        if (resolvingPending)
          setError(
            `${errorMessage(failure)} A intenção anterior foi rejeitada sem registrar pagamento. Você pode informar uma nova intenção.`,
          );
        setRevision((value) => value + 1);
        if (["invalid_transition", "not_found"].includes(failure.code))
          setAction(null);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="text-button back-button" onClick={onBack}>
        {backLabel}
      </button>
      {result.error && <Alert>{result.error}</Alert>}
      {error && !action && <Alert>{error}</Alert>}
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
                <RouteLink
                  to={{ area: "reports", customerId: data.customer_id }}
                  className="button secondary"
                  onNavigate={() => onStatement(data.customer_id)}
                >
                  Extrato do cliente
                </RouteLink>
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
                    <h2>
                      {data.status === "canceled"
                        ? "Saldo nominal remanescente"
                        : "Saldo do título"}
                    </h2>
                    <strong className="detail-amount">
                      {money(data.remaining_cents)}
                    </strong>
                    <div className="invoice-state">
                      <Badge status={data.overdue ? "overdue" : data.status} />
                      {data.payment_state === "partial" && (
                        <Badge status="partial" />
                      )}
                      <span>Vencimento: {date(data.due_date)}</span>
                    </div>
                  </div>
                  {(data.status === "open" || local.intent || local.error) &&
                    session.user.role === "operator" && (
                      <div className="invoice-actions">
                        <button className="button" onClick={openPayment}>
                          {local.intent || local.error
                            ? "Resolver pagamento pendente"
                            : "Registrar pagamento"}
                        </button>
                        {data.status === "open" &&
                          data.payment_state === "unpaid" &&
                          !local.intent &&
                          !local.error && (
                            <button
                              className="button danger-outline"
                              onClick={() => {
                                setAction("cancel");
                                setError("");
                              }}
                            >
                              Cancelar título
                            </button>
                          )}
                      </div>
                    )}
                </div>
                <p className="footnote">
                  Recebimentos reduzem o saldo. A quitação cancela lembretes
                  pendentes; uma tentativa já autorizada pode terminar.
                  {data.status === "canceled" &&
                    " Este saldo nominal está fora da carteira cobrável."}
                  {data.payment_state === "partial" &&
                    " Títulos com recebimentos não podem ser cancelados."}
                </p>
                <dl>
                  <div>
                    <dt>Valor original</dt>
                    <dd>{money(data.amount_cents)}</dd>
                  </div>
                  <div>
                    <dt>Recebido</dt>
                    <dd>{money(data.paid_cents)}</dd>
                  </div>
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
                <Pagination
                  {...{
                    page: data.history.events.page,
                    total: data.history.events.total,
                    pageSize: data.history.events.page_size,
                  }}
                  label="Paginação dos eventos"
                  onChange={(page) =>
                    setHistoryPages((value) => ({ ...value, events: page }))
                  }
                />
              </section>
            </div>
            <section className="panel" aria-label="Histórico de recebimentos">
              <div className="section-heading">
                <h2>Recebimentos ({data.history.payments.total})</h2>
              </div>
              {data.payments.length ? (
                <div
                  className="table-scroll"
                  role="region"
                  aria-label="Recebimentos do título"
                  tabIndex={0}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Registro</th>
                        <th>Valor recebido</th>
                        <th>Data comercial</th>
                        <th>Registrado em</th>
                        <th>Observação</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.payments.map((payment) => (
                        <tr key={payment.id}>
                          <td>#{payment.id}</td>
                          <td className="money">
                            {money(payment.amount_cents)}
                          </td>
                          <td>{instant(payment.paid_at)}</td>
                          <td>{instant(payment.recorded_at)}</td>
                          <td>{payment.note || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty title="Nenhum recebimento registrado" />
              )}
              <Pagination
                {...{
                  page: data.history.payments.page,
                  total: data.history.payments.total,
                  pageSize: data.history.payments.page_size,
                }}
                label="Paginação dos recebimentos do título"
                onChange={(page) =>
                  setHistoryPages((value) => ({ ...value, payments: page }))
                }
              />
            </section>
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
              <Pagination
                {...{
                  page: data.history.reminders.page,
                  total: data.history.reminders.total,
                  pageSize: data.history.reminders.page_size,
                }}
                label="Paginação dos lembretes do título"
                onChange={(page) =>
                  setHistoryPages((value) => ({ ...value, reminders: page }))
                }
              />
            </section>
          </>
        )
      )}
      {action && data && (
        <Modal
          title={
            action === "pay"
              ? local.intent
                ? "Resolver pagamento pendente"
                : "Registrar pagamento"
              : "Cancelar este título"
          }
          busy={busy}
          onClose={() => setAction(null)}
        >
          <p>
            {data.external_receivable_id} · {data.customer_name}
          </p>
          <p className="modal-amount">
            Saldo atual: {money(data.remaining_cents)}
          </p>
          {action === "pay" &&
            !local.error &&
            (local.intent ? (
              <section
                className="pending-intent-preview"
                aria-label="Recebimento anterior a conferir"
              >
                <h3>Recebimento anterior a conferir</h3>
                <dl>
                  <div>
                    <dt>Valor da solicitação anterior</dt>
                    <dd>
                      {local.intent.payload.amount_cents
                        ? money(local.intent.payload.amount_cents)
                        : "Quitação solicitada sem valor explícito"}
                    </dd>
                  </div>
                  {local.intent.preview && (
                    <div>
                      <dt>Saldo previsto na posição consultada</dt>
                      <dd>
                        {money(local.intent.preview.remaining_after_cents)}
                      </dd>
                    </div>
                  )}
                </dl>
                <p>
                  A nova tentativa confere o recebimento anterior com a mesma
                  chave. O valor e o saldo confirmados serão apresentados após a
                  resposta.
                  {!local.intent.payload.amount_cents &&
                    " A posição atual não permite reconstruir o valor daquela solicitação."}
                </p>
              </section>
            ) : (
              <section
                className="payment-preview"
                aria-label="Conferência do pagamento"
              >
                <h3>Conferência do pagamento</h3>
                <dl aria-live="polite" aria-atomic="true">
                  <div>
                    <dt>Valor a registrar</dt>
                    <dd>
                      {draftAmount
                        ? money(draftAmount)
                        : "Informe um valor válido"}
                    </dd>
                  </div>
                  <div>
                    <dt>Saldo previsto na posição consultada</dt>
                    <dd>
                      {draftAmount
                        ? money(
                            (
                              BigInt(data.remaining_cents) - BigInt(draftAmount)
                            ).toString(),
                          )
                        : "A calcular"}
                    </dd>
                  </div>
                </dl>
                <p>
                  {!draftAmount
                    ? "Informe um valor válido para conferir o recebimento e o saldo previsto."
                    : draftAmount === data.remaining_cents
                      ? "Este recebimento quita o saldo consultado e cancela os lembretes pendentes."
                      : "Este recebimento mantém o título aberto e reduz o saldo."}{" "}
                  Se outra pessoa registrar um recebimento, o saldo pode mudar.
                  Confira o saldo atualizado após confirmar.
                </p>
              </section>
            ))}
          <p>
            {action === "pay"
              ? "Registre uma parcela ou quite o saldo restante. O recebimento usa a data comercial atual."
              : "O título sai da carteira em aberto, sem registrar pagamento."}
          </p>
          {action === "pay" && local.error && <Alert>{local.error}</Alert>}
          {action === "pay" && local.intent && (
            <div className="info-banner">
              <span>
                Há uma intenção sem confirmação. A nova tentativa conserva a
                mesma chave, valor e observação, inclusive após recarregar esta
                página.
              </span>
              {local.expired && (
                <span>
                  A intenção local completou 24 horas. Confira o histórico antes
                  de reenviar; a chave e os recebimentos continuam no servidor.
                </span>
              )}
            </div>
          )}
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
              <>
                <label>
                  Tipo de recebimento
                  <select
                    name="payment_mode"
                    value={
                      local.intent
                        ? local.intent.payload.amount_cents
                          ? "partial"
                          : "remaining"
                        : paymentMode
                    }
                    disabled={busy || !!local.intent || !!local.error}
                    onChange={(event) => {
                      setPaymentMode(event.target.value);
                      setAmountError("");
                    }}
                  >
                    <option value="remaining">Quitar saldo restante</option>
                    <option value="partial">Informar valor em reais</option>
                  </select>
                </label>
                {(local.intent?.payload.amount_cents ||
                  (!local.intent && paymentMode === "partial")) && (
                  <label>
                    Valor recebido (R$)
                    <input
                      name="amount"
                      id="payment-amount"
                      type="text"
                      inputMode="decimal"
                      maxLength={24}
                      value={
                        local.intent?.payload.amount_cents
                          ? brlInput(local.intent.payload.amount_cents)
                          : amountDraft
                      }
                      onChange={(event) => {
                        setAmountDraft(event.target.value);
                        setAmountError("");
                      }}
                      autoComplete="off"
                      disabled={busy || !!local.intent}
                      aria-invalid={!!amountError}
                      aria-describedby={
                        amountError
                          ? "payment-amount-error"
                          : "payment-amount-help"
                      }
                    />
                    <small id="payment-amount-help">
                      Sem separador de milhar. Ex.: 10,50.
                    </small>
                    {amountError && (
                      <span
                        className="field-error"
                        id="payment-amount-error"
                        role="alert"
                      >
                        {amountError}
                      </span>
                    )}
                  </label>
                )}
                <label>
                  Observação (opcional)
                  <textarea
                    name="note"
                    disabled={busy || !!local.intent || !!local.error}
                    value={local.intent?.payload.note ?? noteDraft}
                    onChange={(event) => {
                      setNoteDraft(event.target.value);
                      setNoteError("");
                    }}
                    autoComplete="off"
                    aria-invalid={!!noteError}
                    aria-describedby={
                      noteError ? "payment-note-error" : undefined
                    }
                    maxLength={500}
                    placeholder="Ex.: recebimento no ERP"
                  />
                  {noteError && (
                    <span
                      id="payment-note-error"
                      className="field-error"
                      role="alert"
                    >
                      {noteError}
                    </span>
                  )}
                </label>
                {local.expired && (
                  <label className="check-field">
                    <input
                      type="checkbox"
                      checked={historyChecked}
                      onChange={(event) =>
                        setHistoryChecked(event.target.checked)
                      }
                      disabled={busy}
                    />{" "}
                    Conferi o histórico e quero reenviar a mesma intenção.
                  </label>
                )}
              </>
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
                disabled={
                  busy ||
                  (action === "pay" &&
                    (!!local.error || (local.expired && !historyChecked)))
                }
              >
                {busy
                  ? "Registrando…"
                  : action === "pay"
                    ? local.intent
                      ? "Tentar novamente com a mesma intenção"
                      : "Confirmar pagamento"
                    : "Confirmar cancelamento"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
