"use client";
import { useEffect, useRef, useState } from "react";
import { RouteLink } from "@/lib/workspace-route";
import { query } from "@/lib/api";
import {
  date,
  money,
  bucketOptions,
  bucketLabel,
  titleCount,
} from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { Page, Receivable } from "@/lib/types";
import { ResponsiveFilters } from "@/components/responsive-filters";
import { portfolioScope } from "./overview-filters";
import {
  Alert,
  Badge,
  Empty,
  Icon,
  Loading,
  Pagination,
} from "@/components/ui";

export interface PortfolioFilters {
  q: string;
  status: string;
  due_from: string;
  due_to: string;
  customer_id?: string;
  aging_bucket?: string;
  page?: number;
}
const emptyFilters: PortfolioFilters = {
  q: "",
  status: "",
  due_from: "",
  due_to: "",
  customer_id: "",
  aging_bucket: "",
};
const situationLabels: Record<string, string> = {
  open: "Em aberto",
  overdue: "Vencidos",
  current: "Em dia (inclui hoje)",
  paid: "Pagos",
  canceled: "Cancelados",
};

export function ReceivablesView({
  onOpen,
  initialFilters = emptyFilters,
  returnToTitle,
  onFiltersChange,
}: {
  onOpen: (id: number, filters: PortfolioFilters) => void;
  initialFilters?: PortfolioFilters;
  onFiltersChange: (filters: PortfolioFilters) => void;
  returnToTitle?: number | null;
}) {
  const filters = {
    ...initialFilters,
    page: initialFilters.page ?? 1,
  };
  const setFilters = (
    next: PortfolioFilters | ((previous: typeof filters) => PortfolioFilters),
  ) => onFiltersChange(typeof next === "function" ? next(filters) : next);
  const [selectedBucket, setSelectedBucket] = useState(
    initialFilters.aging_bucket ?? "",
  );
  const [periodError, setPeriodError] = useState("");
  const [revision, setRevision] = useState(0);
  const result = useResource<Page<Receivable>>(
    `/receivables?${query(filters)}`,
    revision,
  );
  const restored = useRef(false);
  useEffect(() => {
    if (returnToTitle == null || restored.current || result.loading) return;
    restored.current = true;
    const active = document.activeElement;
    if (active && active !== document.body && active.id !== "main-content")
      return;
    const title = document.getElementById(`title-open-${returnToTitle}`);
    const destination = title ?? document.getElementById("portfolio-title");
    destination?.focus({ preventScroll: true });
    destination?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [returnToTitle, result.loading]);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1 id="portfolio-title" tabIndex={-1}>
            Títulos
          </h1>
          <p>Consulte vencimentos, confira a situação e registre a baixa.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          <Icon name="refresh" /> Atualizar
        </button>
      </div>
      <section
        className="panel portfolio-panel"
        aria-label="Carteira de títulos"
      >
        <div className="section-heading portfolio-heading">
          <h2>Carteira</h2>
          <span className="muted">
            {result.loading
              ? "Consultando…"
              : result.error
                ? "Consulta indisponível"
                : `${titleCount(result.data?.total ?? 0)} nos filtros atuais`}
          </span>
        </div>
        <div className="portfolio-workbench">
          <ResponsiveFilters
            id="portfolio-filter-fields"
            label="Filtrar carteira"
            scope={[
              filters.q ? `Busca: ${filters.q}` : "Todos os clientes e títulos",
              situationLabels[filters.status] ?? "Todas as situações",
              filters.customer_id ? `Cliente ID ${filters.customer_id}` : "",
              filters.aging_bucket
                ? `Aging: ${bucketLabel(filters.aging_bucket)}`
                : "",
              portfolioScope(filters),
            ]
              .filter(Boolean)
              .join(" · ")}
          >
            {(onApplied) => (
              <form
                className="filters portfolio-filters"
                onReset={(event) => {
                  event.preventDefault();
                  for (const name of [
                    "q",
                    "status",
                    "due_from",
                    "due_to",
                    "customer_id",
                    "aging_bucket",
                  ]) {
                    (
                      event.currentTarget.elements.namedItem(
                        name,
                      ) as HTMLInputElement
                    ).value = "";
                  }
                  setSelectedBucket("");
                  setFilters({ ...emptyFilters, page: 1 });
                  setPeriodError("");
                }}
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const start = String(form.get("due_from") ?? "");
                  const end = String(form.get("due_to") ?? "");
                  if (start && end && start > end) {
                    setPeriodError(
                      "Vencimento inicial deve ser anterior ou igual ao final.",
                    );
                    (
                      event.currentTarget.elements.namedItem(
                        "due_from",
                      ) as HTMLInputElement
                    )?.focus();
                    return;
                  }
                  setPeriodError("");
                  setFilters({
                    q: String(form.get("q") ?? "").trim(),
                    status: form.get("aging_bucket")
                      ? "open"
                      : String(form.get("status") ?? ""),
                    due_from: String(form.get("due_from") ?? ""),
                    due_to: String(form.get("due_to") ?? ""),
                    customer_id: String(form.get("customer_id") ?? "").trim(),
                    aging_bucket: String(form.get("aging_bucket") ?? ""),
                    page: 1,
                  });
                  onApplied();
                }}
              >
                <label className="search-field">
                  Cliente ou título
                  <input
                    name="q"
                    defaultValue={initialFilters.q}
                    type="search"
                    maxLength={200}
                    placeholder="Nome ou código"
                  />
                </label>
                <label>
                  ID do cliente
                  <input
                    name="customer_id"
                    inputMode="numeric"
                    pattern="[1-9][0-9]*"
                    defaultValue={initialFilters.customer_id ?? ""}
                    placeholder="Todos"
                  />
                </label>
                <label>
                  Faixa de aging
                  <select
                    name="aging_bucket"
                    value={selectedBucket}
                    onChange={(event) => {
                      setSelectedBucket(event.target.value);
                      if (event.target.value)
                        (
                          event.currentTarget.form?.elements.namedItem(
                            "status",
                          ) as HTMLSelectElement
                        ).value = "open";
                    }}
                  >
                    <option value="">Todas</option>
                    {bucketOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Situação
                  <select
                    name="status"
                    defaultValue={
                      initialFilters.aging_bucket
                        ? "open"
                        : initialFilters.status
                    }
                    disabled={!!selectedBucket}
                    aria-describedby={
                      selectedBucket ? "aging-open-help" : undefined
                    }
                  >
                    <option value="">Todas</option>
                    <option value="open">Em aberto</option>
                    <option value="overdue">Vencidos</option>
                    <option value="current">Em dia (inclui hoje)</option>
                    <option value="paid">Pagos</option>
                    <option value="canceled">Cancelados</option>
                  </select>
                </label>
                {selectedBucket && (
                  <p id="aging-open-help" className="muted">
                    A faixa de aging consulta somente o saldo em aberto.
                  </p>
                )}
                <label>
                  Vencimento de
                  <input
                    name="due_from"
                    type="date"
                    min="0001-01-01"
                    max="9999-12-31"
                    defaultValue={initialFilters.due_from}
                    aria-invalid={!!periodError}
                    aria-describedby={
                      periodError ? "title-period-error" : undefined
                    }
                  />
                </label>
                <label>
                  Até
                  <input
                    name="due_to"
                    type="date"
                    min="0001-01-01"
                    max="9999-12-31"
                    defaultValue={initialFilters.due_to}
                    aria-invalid={!!periodError}
                    aria-describedby={
                      periodError ? "title-period-error" : undefined
                    }
                  />
                </label>
                <button className="button" type="submit">
                  Filtrar títulos
                </button>
                <button type="reset" className="text-button">
                  Limpar filtros
                </button>
                {periodError && (
                  <p
                    className="field-error"
                    id="title-period-error"
                    role="alert"
                  >
                    {periodError}
                  </p>
                )}
              </form>
            )}
          </ResponsiveFilters>
          <div className="portfolio-results">
            {result.error ? (
              <Alert>{result.error}</Alert>
            ) : result.loading ? (
              <Loading />
            ) : !result.data?.items.length ? (
              <Empty
                title={
                  result.data?.total
                    ? "Esta página ficou vazia"
                    : "Nenhum título encontrado"
                }
              >
                {result.data?.total ? (
                  <>
                    A carteira mudou desde a consulta. Os filtros ainda
                    encontram títulos em outras páginas.
                    <button
                      className="text-button"
                      onClick={() => {
                        document.getElementById("portfolio-title")?.focus();
                        setFilters((value) => ({ ...value, page: 1 }));
                      }}
                    >
                      Voltar à primeira página
                    </button>
                  </>
                ) : (
                  <>
                    Não há registros para esta busca. Limpe os filtros ou
                    confira o arquivo importado.
                  </>
                )}
              </Empty>
            ) : (
              <>
                <div
                  className="table-scroll"
                  role="region"
                  aria-label="Lista da carteira"
                  tabIndex={0}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Título / sistema</th>
                        <th>Cliente</th>
                        <th>Vencimento</th>
                        <th className="numeric">Saldo / recebido / original</th>
                        <th>Situação</th>
                        <th>
                          <span className="sr-only">Ação</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.data.items.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <RouteLink
                              to={{
                                area: "titles",
                                titleId: item.id,
                                titleOrigin: { kind: "portfolio" },
                                titleFilters: filters,
                              }}
                              id={`title-open-${item.id}`}
                              className="text-button row-link"
                              onNavigate={() => onOpen(item.id, filters)}
                            >
                              {item.external_receivable_id}
                            </RouteLink>
                            <small>{item.source_system}</small>
                          </td>
                          <td>
                            {item.customer_name}
                            <small className="truncate">
                              {item.description}
                            </small>
                          </td>
                          <td>{date(item.due_date)}</td>
                          <td className="numeric money">
                            {money(item.remaining_cents)}
                            <small>Recebido {money(item.paid_cents)}</small>
                            <small>Original {money(item.amount_cents)}</small>
                          </td>
                          <td>
                            <Badge
                              status={item.overdue ? "overdue" : item.status}
                            />
                            {item.payment_state === "partial" && (
                              <Badge status="partial" />
                            )}
                          </td>
                          <td>
                            <RouteLink
                              to={{
                                area: "titles",
                                titleId: item.id,
                                titleOrigin: { kind: "portfolio" },
                                titleFilters: filters,
                              }}
                              className="text-button"
                              aria-label={`Abrir título ${item.external_receivable_id}`}
                              onNavigate={() => onOpen(item.id, filters)}
                            >
                              Detalhe
                            </RouteLink>
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
                  onChange={(page) =>
                    setFilters((value) => ({ ...value, page }))
                  }
                />
              </>
            )}
          </div>
        </div>
      </section>
    </>
  );
}
