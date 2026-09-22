"use client";
import { useState } from "react";
import { query } from "@/lib/api";
import { date, money } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { Page, Receivable } from "@/lib/types";
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
}
const emptyFilters: PortfolioFilters = {
  q: "",
  status: "",
  due_from: "",
  due_to: "",
};

export function ReceivablesView({
  onOpen,
  initialFilters = emptyFilters,
}: {
  onOpen: (id: number, filters: PortfolioFilters) => void;
  initialFilters?: PortfolioFilters;
}) {
  const [filters, setFilters] = useState({
    ...initialFilters,
    page: 1,
  });
  const [periodError, setPeriodError] = useState("");
  const [revision, setRevision] = useState(0);
  const result = useResource<Page<Receivable>>(
    `/receivables?${query(filters)}`,
    revision,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Títulos</h1>
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
                : `${result.data?.total ?? 0} títulos nos filtros atuais`}
          </span>
        </div>
        <form
          className="filters"
          onReset={(event) => {
            event.preventDefault();
            for (const name of ["q", "status", "due_from", "due_to"]) {
              (
                event.currentTarget.elements.namedItem(name) as HTMLInputElement
              ).value = "";
            }
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
              status: String(form.get("status") ?? ""),
              due_from: String(form.get("due_from") ?? ""),
              due_to: String(form.get("due_to") ?? ""),
              page: 1,
            });
          }}
        >
          <label className="search-field">
            Cliente ou título
            <input
              name="q"
              defaultValue={initialFilters.q}
              type="search"
              maxLength={200}
              placeholder="Nome, descrição ou código"
            />
          </label>
          <label>
            Situação
            <select name="status" defaultValue={initialFilters.status}>
              <option value="">Todas</option>
              <option value="open">Em aberto</option>
              <option value="overdue">Vencidos</option>
              <option value="current">Em dia (inclui hoje)</option>
              <option value="paid">Pagos</option>
              <option value="canceled">Cancelados</option>
            </select>
          </label>
          <label>
            Vencimento de
            <input
              name="due_from"
              type="date"
              min="0001-01-01"
              max="9999-12-31"
              defaultValue={initialFilters.due_from}
              aria-invalid={!!periodError}
              aria-describedby={periodError ? "title-period-error" : undefined}
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
              aria-describedby={periodError ? "title-period-error" : undefined}
            />
          </label>
          <button className="button" type="submit">
            Filtrar títulos
          </button>
          <button type="reset" className="text-button">
            Limpar filtros
          </button>
          {periodError && (
            <p className="field-error" id="title-period-error" role="alert">
              {periodError}
            </p>
          )}
        </form>
        {result.error ? (
          <Alert>{result.error}</Alert>
        ) : result.loading ? (
          <Loading />
        ) : !result.data?.items.length ? (
          <Empty title="Nenhum título encontrado">
            Não há registros para esta busca. Limpe os filtros ou confira o
            arquivo importado.
          </Empty>
        ) : (
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
                    <th>Título / sistema</th>
                    <th>Cliente</th>
                    <th>Vencimento</th>
                    <th className="numeric">Valor</th>
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
                        <button
                          className="text-button row-link"
                          onClick={() => onOpen(item.id, filters)}
                        >
                          {item.external_receivable_id}
                        </button>
                        <small>{item.source_system}</small>
                      </td>
                      <td>
                        {item.customer_name}
                        <small className="truncate">{item.description}</small>
                      </td>
                      <td>{date(item.due_date)}</td>
                      <td className="numeric money">
                        {money(item.amount_cents)}
                      </td>
                      <td>
                        <Badge
                          status={item.overdue ? "overdue" : item.status}
                        />
                      </td>
                      <td>
                        <button
                          className="text-button"
                          aria-label={`Abrir título ${item.external_receivable_id}`}
                          onClick={() => onOpen(item.id, filters)}
                        >
                          Detalhe
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
        )}
      </section>
    </>
  );
}
