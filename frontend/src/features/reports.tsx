"use client";
import { useEffect, useRef, useState } from "react";
import { query } from "@/lib/api";
import { date, instant, money } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { Aging, CustomerStatement, Receivable } from "@/lib/types";
import type { PortfolioFilters } from "./receivables";
import {
  Alert,
  Badge,
  Empty,
  Icon,
  Loading,
  Pagination,
} from "@/components/ui";

const bucketOptions = [
  { key: "current", label: "Em dia (inclui hoje)" },
  { key: "1_30", label: "1–30 dias" },
  { key: "31_60", label: "31–60 dias" },
  { key: "61_90", label: "61–90 dias" },
  { key: "over_90", label: "Acima de 90 dias" },
];
export const emptyAgingFilters = {
  q: "",
  customer_id: "",
  due_from: "",
  due_to: "",
  bucket: "",
  page: 1,
};
export type AgingFilters = typeof emptyAgingFilters;
type PeriodError = { period: "due" | "received"; message: string } | null;
const situationLabels: Record<string, string> = {
  open: "Em aberto",
  paid: "Pagos",
  canceled: "Cancelados",
  overdue: "Vencidos",
  current: "Em dia",
};
function useReportReturnFocus(
  returnToTitle: number | null | undefined,
  loading: boolean,
  headingId: string,
) {
  const restored = useRef(false);
  useEffect(() => {
    if (returnToTitle == null || restored.current || loading) return;
    restored.current = true;
    const active = document.activeElement;
    if (active && active !== document.body && active.id !== "main-content")
      return;
    const destination =
      document.getElementById(`report-title-open-${returnToTitle}`) ??
      document.getElementById(headingId);
    destination?.focus({ preventScroll: true });
    destination?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [returnToTitle, loading, headingId]);
}
function validPeriod(
  form: HTMLFormElement,
  names: [string, string],
  label: string,
): PeriodError {
  const values = new FormData(form);
  const start = String(values.get(names[0]) ?? "");
  const end = String(values.get(names[1]) ?? "");
  if (start && end && start > end) {
    (form.elements.namedItem(names[0]) as HTMLInputElement)?.focus();
    return {
      period: names[0].startsWith("due") ? "due" : "received",
      message: `${label}: a data inicial deve ser anterior ou igual à final.`,
    };
  }
  return null;
}
function ReportDates({
  name,
  label,
  error,
  from,
  to,
  onEdit,
}: {
  name: "due" | "received";
  label: string;
  error: boolean;
  from: string;
  to: string;
  onEdit: () => void;
}) {
  return (
    <fieldset className="report-filter-group">
      <legend>
        {name === "due" ? "Vencimento dos títulos" : "Período dos recebimentos"}
      </legend>
      <label>
        {label} de
        <input
          name={`${name}_from`}
          defaultValue={from}
          onChange={onEdit}
          type="date"
          min="0001-01-01"
          max="9999-12-31"
          aria-invalid={error}
          aria-describedby={error ? "report-period-error" : undefined}
        />
      </label>
      <label>
        Até ({label.toLowerCase()})
        <input
          name={`${name}_to`}
          defaultValue={to}
          onChange={onEdit}
          type="date"
          min="0001-01-01"
          max="9999-12-31"
          aria-invalid={error}
          aria-describedby={error ? "report-period-error" : undefined}
        />
      </label>
    </fieldset>
  );
}
function PositionCaption({
  generatedAt,
  businessDate,
}: {
  generatedAt: string;
  businessDate: string;
}) {
  return (
    <p className="footnote">
      Posição atual gerada em {instant(generatedAt)} · Data comercial{" "}
      {date(businessDate)}, São Paulo. Cada página mostra a posição no momento
      da consulta; ela pode mudar entre páginas.
    </p>
  );
}
function ReportTitleRows({
  items,
  onOpen,
  onStatement,
}: {
  items: Receivable[];
  onOpen: (id: number) => void;
  onStatement?: (id: number) => void;
}) {
  return (
    <div
      className="table-scroll"
      role="region"
      aria-label="Títulos do relatório"
      tabIndex={0}
    >
      <table className="report-titles-table">
        <thead>
          <tr>
            <th>Título / origem</th>
            <th>Cliente</th>
            <th>Vencimento</th>
            <th className="numeric">Original</th>
            <th className="numeric">Recebido</th>
            <th className="numeric">Saldo nominal</th>
            <th>Situação</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td data-label="Título / origem">
                <button
                  className="text-button row-link"
                  id={`report-title-open-${item.id}`}
                  onClick={() => onOpen(item.id)}
                >
                  {item.external_receivable_id}
                </button>
                <small data-label="Sistema de origem">
                  {item.source_system}
                </small>
              </td>
              <td data-label="Cliente">
                {item.customer_name}
                {onStatement && (
                  <small>
                    <button
                      className="text-button"
                      aria-label={`Extrato do cliente ID ${item.customer_id}`}
                      onClick={() => onStatement(item.customer_id)}
                    >
                      Extrato
                    </button>
                  </small>
                )}
              </td>
              <td data-label="Vencimento">{date(item.due_date)}</td>
              <td data-label="Original" className="numeric money">
                {money(item.amount_cents)}
              </td>
              <td data-label="Recebido" className="numeric money">
                {money(item.paid_cents)}
              </td>
              <td data-label="Saldo" className="numeric money">
                {money(item.remaining_cents)}
              </td>
              <td data-label="Situação">
                <Badge status={item.overdue ? "overdue" : item.status} />
                {item.payment_state === "partial" && <Badge status="partial" />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function AgingView({
  filters,
  onFiltersChange,
  onTitles,
  onOpen,
  onStatement,
  returnToTitle,
}: {
  filters: AgingFilters;
  onFiltersChange: (filters: AgingFilters) => void;
  onTitles: (filters: PortfolioFilters) => void;
  onOpen: (id: number) => void;
  onStatement: (id: number) => void;
  returnToTitle?: number | null;
}) {
  const [error, setError] = useState<PeriodError>(null);
  const [revision, setRevision] = useState(0);
  const result = useResource<Aging>(
    `/reports/aging?${query(filters)}`,
    revision,
  );
  const data = result.data;
  useReportReturnFocus(returnToTitle, result.loading, "aging-heading");
  function drilldown(bucket: string) {
    onTitles({
      q: filters.q,
      customer_id: filters.customer_id,
      due_from: filters.due_from,
      due_to: filters.due_to,
      status: "",
      aging_bucket: bucket,
      page: 1,
    });
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1 id="aging-heading" tabIndex={-1}>
            Aging da carteira
          </h1>
          <p>Saldo residual dos títulos em aberto, por dias de atraso.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          <Icon name="refresh" /> Atualizar
        </button>
      </div>
      <form
        className="panel filters report-filters"
        onReset={(event) => {
          event.preventDefault();
          for (const name of [
            "q",
            "customer_id",
            "due_from",
            "due_to",
            "bucket",
          ])
            (
              event.currentTarget.elements.namedItem(name) as HTMLInputElement
            ).value = "";
          onFiltersChange(emptyAgingFilters);
          setError(null);
        }}
        onSubmit={(event) => {
          event.preventDefault();
          const failure = validPeriod(
            event.currentTarget,
            ["due_from", "due_to"],
            "Vencimento",
          );
          setError(failure);
          if (failure) return;
          const values = new FormData(event.currentTarget);
          onFiltersChange({
            q: String(values.get("q") ?? "").trim(),
            customer_id: String(values.get("customer_id") ?? "").trim(),
            due_from: String(values.get("due_from") ?? ""),
            due_to: String(values.get("due_to") ?? ""),
            bucket: String(values.get("bucket") ?? ""),
            page: 1,
          });
        }}
      >
        <label className="search-field">
          Cliente ou título
          <input
            name="q"
            defaultValue={filters.q}
            type="search"
            maxLength={200}
            placeholder="Nome ou código"
          />
        </label>
        <label>
          ID do cliente
          <input
            name="customer_id"
            defaultValue={filters.customer_id}
            inputMode="numeric"
            pattern="[1-9][0-9]*"
            placeholder="Todos"
          />
        </label>
        <label>
          Faixa de aging
          <select name="bucket" defaultValue={filters.bucket}>
            <option value="">Todas</option>
            {bucketOptions.map((bucket) => (
              <option key={bucket.key} value={bucket.key}>
                {bucket.label}
              </option>
            ))}
          </select>
        </label>
        <ReportDates
          name="due"
          label="Vencimento"
          error={!!error}
          from={filters.due_from}
          to={filters.due_to}
          onEdit={() => setError(null)}
        />
        <button className="button" type="submit">
          Filtrar aging
        </button>
        <button className="text-button" type="reset">
          Limpar filtros
        </button>
        {error && (
          <p className="field-error" id="report-period-error" role="alert">
            {error.message}
          </p>
        )}
      </form>
      {result.error ? (
        <Alert>{result.error}</Alert>
      ) : result.loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <PositionCaption
              generatedAt={data.generated_at}
              businessDate={data.business_date}
            />
            <section className="panel">
              <div className="section-heading">
                <h2>Carteira no recorte</h2>
                <strong className="money">
                  {money(data.open_cents)} · {data.title_count} títulos
                </strong>
              </div>
              <div className="aging-buckets">
                {data.buckets.map((bucket) => (
                  <article key={bucket.key} className="metric">
                    <h3>{bucket.label}</h3>
                    <strong>{money(bucket.remaining_cents)}</strong>
                    <p>{bucket.title_count} títulos</p>
                    <button
                      className="text-button"
                      aria-label={`Ver títulos da faixa ${bucket.label}`}
                      onClick={() => drilldown(bucket.key)}
                    >
                      Ver títulos <Icon name="right" />
                    </button>
                  </article>
                ))}
              </div>
              <p className="padded footnote">
                Faixas inclusivas: hoje e futuro; 1 a 30; 31 a 60; 61 a 90; mais
                de 90 dias. Cada título entra em uma faixa.
              </p>
            </section>
            <section className="panel">
              <div className="section-heading">
                <h2>Títulos do aging</h2>
              </div>
              {data.items.length ? (
                <ReportTitleRows
                  items={data.items}
                  onOpen={onOpen}
                  onStatement={onStatement}
                />
              ) : (
                <Empty title="Nenhum título nesta faixa" />
              )}
              <Pagination
                label="Paginação dos títulos do aging"
                page={data.page}
                total={data.total}
                pageSize={data.page_size}
                onChange={(page) => onFiltersChange({ ...filters, page })}
              />
            </section>
          </>
        )
      )}
    </>
  );
}

export const emptyStatementFilters = {
  q: "",
  status: "",
  due_from: "",
  due_to: "",
  received_from: "",
  received_to: "",
  page: 1,
  payment_page: 1,
};
export type StatementFilters = typeof emptyStatementFilters;
export function CustomerStatementView({
  filters,
  onFiltersChange,
  customerId,
  onOpen,
  onBack,
  returnToTitle,
}: {
  filters: StatementFilters;
  onFiltersChange: (filters: StatementFilters) => void;
  customerId: number;
  onOpen: (id: number) => void;
  onBack: () => void;
  returnToTitle?: number | null;
}) {
  const [error, setError] = useState<PeriodError>(null);
  const [revision, setRevision] = useState(0);
  const result = useResource<CustomerStatement>(
    `/customers/${customerId}/statement?${query(filters)}`,
    revision,
  );
  const data = result.data;
  useReportReturnFocus(returnToTitle, result.loading, "statement-heading");
  return (
    <div className="customer-statement">
      <button className="text-button back-button no-print" onClick={onBack}>
        Voltar
      </button>
      <div className="page-heading">
        <div>
          <h1 id="statement-heading" tabIndex={-1}>
            Extrato operacional
          </h1>
          <p>
            {data
              ? `${data.customer.name} · ${data.customer.source_system} / ${data.customer.external_customer_id} · ID ${data.customer.id}`
              : `Cliente ID ${customerId}`}
          </p>
        </div>
        <div className="button-group no-print">
          <button
            className="button secondary"
            disabled={!data || result.loading}
            onClick={() => window.print()}
          >
            Imprimir extrato
          </button>
          <button
            className="button secondary"
            onClick={() => setRevision((value) => value + 1)}
          >
            <Icon name="refresh" /> Atualizar
          </button>
        </div>
      </div>
      <form
        className="panel filters report-filters no-print"
        onReset={(event) => {
          event.preventDefault();
          for (const name of [
            "q",
            "status",
            "due_from",
            "due_to",
            "received_from",
            "received_to",
          ])
            (
              event.currentTarget.elements.namedItem(name) as HTMLInputElement
            ).value = "";
          onFiltersChange(emptyStatementFilters);
          setError(null);
        }}
        onSubmit={(event) => {
          event.preventDefault();
          const failure =
            validPeriod(
              event.currentTarget,
              ["due_from", "due_to"],
              "Vencimento",
            ) ||
            validPeriod(
              event.currentTarget,
              ["received_from", "received_to"],
              "Recebimento",
            );
          setError(failure);
          if (failure) return;
          const values = new FormData(event.currentTarget);
          onFiltersChange({
            q: String(values.get("q") ?? "").trim(),
            status: String(values.get("status") ?? ""),
            due_from: String(values.get("due_from") ?? ""),
            due_to: String(values.get("due_to") ?? ""),
            received_from: String(values.get("received_from") ?? ""),
            received_to: String(values.get("received_to") ?? ""),
            page: 1,
            payment_page: 1,
          });
        }}
      >
        <label className="search-field">
          Título ou descrição
          <input
            name="q"
            type="search"
            maxLength={200}
            defaultValue={filters.q}
          />
        </label>
        <label>
          Situação
          <select name="status" defaultValue={filters.status}>
            <option value="">Todas</option>
            <option value="open">Em aberto</option>
            <option value="paid">Pagos</option>
            <option value="canceled">Cancelados</option>
            <option value="overdue">Vencidos</option>
            <option value="current">Em dia</option>
          </select>
        </label>
        <ReportDates
          name="due"
          label="Vencimento"
          error={error?.period === "due"}
          from={filters.due_from}
          to={filters.due_to}
          onEdit={() => setError(null)}
        />
        <ReportDates
          name="received"
          label="Recebimento"
          error={error?.period === "received"}
          from={filters.received_from}
          to={filters.received_to}
          onEdit={() => setError(null)}
        />
        <button className="button" type="submit">
          Filtrar extrato
        </button>
        <button className="text-button" type="reset">
          Limpar filtros
        </button>
        {error && (
          <p id="report-period-error" className="field-error" role="alert">
            {error.message}
          </p>
        )}
      </form>
      {result.error ? (
        <Alert>{result.error}</Alert>
      ) : result.loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <PositionCaption
              generatedAt={data.generated_at}
              businessDate={data.business_date}
            />
            <p className="footnote report-scope">
              Recorte de títulos:{" "}
              {situationLabels[filters.status] ?? "todas as situações"} ·
              vencimento{" "}
              {date(filters.due_from) === "—"
                ? "início"
                : date(filters.due_from)}{" "}
              a {date(filters.due_to) === "—" ? "fim" : date(filters.due_to)}
              {filters.q ? ` · Busca: ${filters.q}` : ""}. Recebimentos:{" "}
              {date(data.received_from) === "—"
                ? "início"
                : date(data.received_from)}{" "}
              a{" "}
              {date(data.received_to) === "—" ? "fim" : date(data.received_to)}.
            </p>
            <section className="panel">
              <div className="section-heading">
                <h2>Totais de todo o recorte</h2>
                <span>{data.totals.title_count} títulos</span>
              </div>
              <dl className="statement-totals">
                <div>
                  <dt>Valor original</dt>
                  <dd>{money(data.totals.amount_cents)}</dd>
                </div>
                <div>
                  <dt>Recebido nos títulos</dt>
                  <dd>{money(data.totals.paid_cents)}</dd>
                </div>
                <div>
                  <dt>Saldo nominal</dt>
                  <dd>{money(data.totals.remaining_cents)}</dd>
                </div>
                <div>
                  <dt>Carteira cobrável</dt>
                  <dd>{money(data.totals.open_cents)}</dd>
                </div>
                <div>
                  <dt>Saldo nominal cancelado</dt>
                  <dd>{money(data.totals.canceled_remaining_cents)}</dd>
                </div>
                <div>
                  <dt>Recebido no período</dt>
                  <dd>
                    {money(data.totals.received_cents)} ·{" "}
                    {data.totals.paid_count} recebimentos
                  </dd>
                </div>
              </dl>
            </section>
            <section className="panel">
              <div className="section-heading">
                <h2>Títulos do cliente</h2>
                <span>
                  Página {data.titles.page} · {data.titles.items.length} de{" "}
                  {data.titles.total} títulos
                </span>
              </div>
              {data.titles.items.length ? (
                <ReportTitleRows items={data.titles.items} onOpen={onOpen} />
              ) : (
                <Empty title="Nenhum título no recorte" />
              )}
              <div className="no-print">
                <Pagination
                  label="Paginação dos títulos do cliente"
                  page={data.titles.page}
                  total={data.titles.total}
                  pageSize={data.titles.page_size}
                  onChange={(page) => onFiltersChange({ ...filters, page })}
                />
              </div>
            </section>
            <section className="panel">
              <div className="section-heading">
                <h2>Recebimentos do cliente</h2>
                <span>
                  Página {data.payments.page} · {data.payments.items.length} de{" "}
                  {data.payments.total} recebimentos
                </span>
              </div>
              {data.payments.items.length ? (
                <div
                  className="table-scroll"
                  role="region"
                  aria-label="Recebimentos do extrato"
                  tabIndex={0}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Recebimento / título</th>
                        <th className="numeric">Valor</th>
                        <th>Data comercial</th>
                        <th>Registro</th>
                        <th>Observação</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.payments.items.map((payment) => (
                        <tr key={payment.id}>
                          <td>
                            #{payment.id} ·{" "}
                            <button
                              className="text-button row-link"
                              onClick={() => onOpen(payment.receivable_id)}
                            >
                              {payment.external_receivable_id}
                            </button>
                            <small>{payment.source_system}</small>
                          </td>
                          <td className="numeric money">
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
                <Empty title="Nenhum recebimento neste período" />
              )}
              <div className="no-print">
                <Pagination
                  label="Paginação dos recebimentos do cliente"
                  page={data.payments.page}
                  total={data.payments.total}
                  pageSize={data.payments.page_size}
                  onChange={(payment_page) =>
                    onFiltersChange({ ...filters, payment_page })
                  }
                />
              </div>
            </section>
            <p className="footnote">
              Filtros de vencimento e situação afetam os títulos. O período de
              recebimento afeta a seção de pagamentos e seu total; o saldo atual
              inclui todos os recebimentos. A impressão inclui as páginas
              exibidas e os totais de todo o recorte. Este extrato mostra a
              posição atual, sem saldo de abertura ou posição histórica.
            </p>
          </>
        )
      )}
    </div>
  );
}
