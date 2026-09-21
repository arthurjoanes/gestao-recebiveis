"use client";
import { useState } from "react";
import { query } from "@/lib/api";
import { instant, money, reminderStage, nextAttempt } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { Page, Reminder, ReminderDetail } from "@/lib/types";
import {
  Alert,
  Badge,
  Empty,
  Icon,
  Loading,
  Pagination,
} from "@/components/ui";

export function RemindersView({
  selected,
  onSelect,
  onTitle,
}: {
  selected: number | null;
  onSelect: (id: number | null) => void;
  onTitle: (id: number) => void;
}) {
  const [filters, setFilters] = useState({ q: "", status: "", page: 1 });
  const [revision, setRevision] = useState(0);
  const result = useResource<Page<Reminder>>(
    `/reminders?${query(filters)}`,
    revision,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Lembretes</h1>
        </div>
        <button
          className="button secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          <Icon name="refresh" /> Atualizar
        </button>
      </div>
      <div className="info-banner">
        <strong>D−3 → D0 → D+3 → D+7</strong>
        <span>
          Às 09:00 de São Paulo, até um lembrete por título/dia. Após D+7, não
          há novos lembretes.
        </span>
      </div>
      {selected !== null && (
        <ReminderDetails
          id={selected}
          revision={revision}
          onClose={() => onSelect(null)}
          onTitle={onTitle}
        />
      )}
      <form
        className="panel filters"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          setFilters({
            q: String(form.get("q") ?? ""),
            status: String(form.get("status") ?? ""),
            page: 1,
          });
        }}
      >
        <label className="search-field">
          Cliente ou título
          <input
            type="search"
            name="q"
            maxLength={200}
            placeholder="Buscar um lembrete"
          />
        </label>
        <label>
          Situação
          <select name="status">
            <option value="">Todas</option>
            <option value="pending">Pendente</option>
            <option value="processing">Processando</option>
            <option value="sent">Entregue</option>
            <option value="retry_scheduled">Nova tentativa</option>
            <option value="failed">Falhou</option>
            <option value="canceled">Cancelado</option>
            <option value="superseded">Ultrapassado</option>
          </select>
        </label>
        <button className="button" type="submit">
          Filtrar lembretes
        </button>
      </form>
      <section className="panel">
        {result.error ? (
          <Alert>{result.error}</Alert>
        ) : result.loading ? (
          <Loading />
        ) : result.data?.items.length ? (
          <>
            <div
              className="table-scroll"
              role="region"
              aria-label="Tabela com rolagem horizontal"
              tabIndex={0}
            >
              <table>
                <thead>
                  <tr>
                    <th>Título / cliente</th>
                    <th>Etapa</th>
                    <th>Situação</th>
                    <th>Tentativas</th>
                    <th>Próxima tentativa</th>
                    <th>Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.items.map((job) => (
                    <tr key={job.id}>
                      <td>
                        <button
                          className="text-button row-link"
                          onClick={() => onTitle(job.receivable_id)}
                        >
                          {job.external_receivable_id}
                        </button>
                        <small>{job.customer_name}</small>
                      </td>
                      <td>{reminderStage(job.stage)}</td>
                      <td>
                        <Badge status={job.status} />
                      </td>
                      <td>{job.attempts_count}</td>
                      <td>{nextAttempt(job)}</td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => onSelect(job.id)}
                        >
                          Ver tentativas
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={result.data.page}
              total={result.data.total}
              pageSize={result.data.page_size}
              onChange={(page) => setFilters((value) => ({ ...value, page }))}
            />
          </>
        ) : (
          <Empty title="Nenhum lembrete encontrado">
            Ajuste os filtros ou confira a data comercial em Demonstração.
          </Empty>
        )}
      </section>
    </>
  );
}
function ReminderDetails({
  id,
  revision,
  onClose,
  onTitle,
}: {
  id: number;
  revision: number;
  onClose: () => void;
  onTitle: (id: number) => void;
}) {
  const result = useResource<ReminderDetail>(`/reminders/${id}`, revision);
  const job = result.data;
  return (
    <section className="panel reminder-detail">
      <div className="section-heading">
        <h2>Lembrete #{id}</h2>
        <button className="text-button" onClick={onClose}>
          Fechar detalhe
        </button>
      </div>
      {result.error ? (
        <Alert>{result.error}</Alert>
      ) : result.loading ? (
        <Loading />
      ) : (
        job && (
          <>
            <div className="reminder-summary">
              <div>
                <button
                  className="text-button row-link"
                  onClick={() => onTitle(job.receivable_id)}
                >
                  {job.external_receivable_id}
                </button>
                <p>
                  {job.customer_name} · {money(job.amount_cents)} ·{" "}
                  {reminderStage(job.stage)}
                </p>
              </div>
              <Badge status={job.status} />
            </div>
            {job.last_error && <Alert>{job.last_error}</Alert>}
            {job.cancel_requested && (
              <div className="info-banner">
                Cancelamento após autorização. A tentativa pode terminar; novos
                envios estão bloqueados.
              </div>
            )}
            <dl className="inline-facts">
              <div>
                <dt>Chave idempotente</dt>
                <dd>
                  <code>{job.idempotency_key}</code>
                </dd>
              </div>
              <div>
                <dt>Próxima tentativa</dt>
                <dd>{nextAttempt(job)}</dd>
              </div>
              <div>
                <dt>Lease até</dt>
                <dd>{instant(job.lease_expires_at)}</dd>
              </div>
            </dl>
            {job.attempts.length ? (
              <div
                className="table-scroll"
                role="region"
                aria-label="Tabela com rolagem horizontal"
                tabIndex={0}
              >
                <table>
                  <thead>
                    <tr>
                      <th>Tentativa</th>
                      <th>Autorizada em</th>
                      <th>Finalizada em</th>
                      <th>Resultado</th>
                      <th>Detalhe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {job.attempts.map((attempt) => (
                      <tr key={attempt.id}>
                        <td>#{attempt.number}</td>
                        <td>{instant(attempt.authorized_at)}</td>
                        <td>{instant(attempt.finished_at)}</td>
                        <td>
                          <Badge status={attempt.outcome} />
                        </td>
                        <td>{attempt.error ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="padded muted">Nenhuma tentativa autorizada.</p>
            )}
            {job.delivery ? (
              <div className="delivery-box">
                <p className="eyebrow">Entrega simulada #{job.delivery.id}</p>
                <h3>Aceita em {instant(job.delivery.accepted_at)}</h3>
                <p className="delivery-message">{job.delivery.message}</p>
              </div>
            ) : (
              <p className="padded muted">
                Nenhuma entrega para este lembrete.
              </p>
            )}
          </>
        )
      )}
    </section>
  );
}
