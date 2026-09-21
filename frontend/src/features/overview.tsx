"use client";
import { useState } from "react";
import { query } from "@/lib/api";
import { date, money } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import {
  OverviewFilterForm,
  emptyOverviewFilters,
  portfolioScope,
} from "./overview-filters";
import type { PortfolioFilters } from "./receivables";
import type { Overview, Page, Receivable } from "@/lib/types";
import { Alert, Badge, Empty, Icon, Loading } from "@/components/ui";

export function OverviewView({
  onOpen,
  onTitles,
}: {
  onOpen: (id: number) => void;
  onTitles: (filters: PortfolioFilters) => void;
}) {
  const [filters, setFilters] = useState(emptyOverviewFilters);
  const [revision, setRevision] = useState(0);
  const overview = useResource<Overview>(
    `/overview?${query({ ...filters })}`,
    revision,
  );
  const urgent = useResource<Page<Receivable>>(
    `/receivables?${query({ q: filters.q, due_from: filters.due_from, due_to: filters.due_to, status: "overdue", page_size: 5 })}`,
    revision,
  );
  const data = overview.data;
  function openTitles(status: string) {
    onTitles({
      q: filters.q,
      due_from: filters.due_from,
      due_to: filters.due_to,
      status,
    });
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Resumo</h1>
        </div>
        <button
          className="button secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          <Icon name="refresh" /> Atualizar
        </button>
      </div>
      {overview.error && <Alert>{overview.error}</Alert>}
      {overview.loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="metrics">
              <article className="metric">
                <div className="metric-label">Carteira em aberto</div>
                <strong>{money(data.open_cents)}</strong>
                <p>
                  {data.open_count}{" "}
                  {data.open_count === 1
                    ? "título em aberto"
                    : "títulos em aberto"}
                  , incluindo vencidos
                </p>
                <small>
                  {portfolioScope(filters)}
                  {filters.q ? ` · Busca: ${filters.q}` : ""}
                </small>
                <button
                  className="text-button"
                  onClick={() => openTitles("open")}
                >
                  Ver títulos em aberto <Icon name="right" />
                </button>
              </article>
              <article className="metric metric-breakdown">
                <div className="metric-label">Composição do aberto</div>
                <div>
                  <span>
                    Vencido <small>{data.overdue_count} títulos</small>
                  </span>
                  <strong>{money(data.overdue_cents)}</strong>
                </div>
                <button
                  className="text-button"
                  onClick={() => openTitles("overdue")}
                >
                  Ver títulos vencidos <Icon name="right" />
                </button>
                <div>
                  <span>
                    Em dia{" "}
                    <small>{data.current_count} títulos · inclui hoje</small>
                  </span>
                  <strong>{money(data.current_cents)}</strong>
                </div>
                <button
                  className="text-button"
                  onClick={() => openTitles("current")}
                >
                  Ver títulos em dia <Icon name="right" />
                </button>
                <small>
                  Referência: {date(data.business_date)} ·{" "}
                  {portfolioScope(filters)}
                </small>
              </article>
              <article className="metric metric-accent">
                <div className="metric-label">Recebido no período</div>
                <strong>{money(data.received_cents)}</strong>
                <p>
                  {data.paid_count}{" "}
                  {data.paid_count === 1
                    ? "pagamento integral"
                    : "pagamentos integrais"}
                </p>
                <small>
                  Filtrado pela data do pagamento ·{" "}
                  {data.received_from ? date(data.received_from) : "início"} a{" "}
                  {data.received_to ? date(data.received_to) : "hoje"}
                  {filters.q ? ` · Busca: ${filters.q}` : ""}
                </small>
              </article>
            </div>
          </>
        )
      )}
      <OverviewFilterForm
        filters={filters}
        businessDate={data?.business_date}
        onApply={setFilters}
      />
      {!overview.loading && data && (
        <>
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Títulos vencidos</h2>
              </div>
              <div className="attention-actions">
                <span className="count-pill">
                  {data.overdue_count} vencidos
                </span>
                <button
                  className="text-button"
                  onClick={() => openTitles("overdue")}
                >
                  Ver todos os vencidos <Icon name="right" />
                </button>
              </div>
            </div>
            {urgent.error ? (
              <Alert>{urgent.error}</Alert>
            ) : urgent.loading ? (
              <Loading />
            ) : urgent.data?.items.length ? (
              <div
                className="table-scroll"
                role="region"
                aria-label="Tabela com rolagem horizontal"
                tabIndex={0}
              >
                <table>
                  <thead>
                    <tr>
                      <th>Cliente / título</th>
                      <th>Vencimento</th>
                      <th className="numeric">Valor</th>
                      <th>Situação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {urgent.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <button
                            className="text-button row-link"
                            onClick={() => onOpen(item.id)}
                          >
                            {item.customer_name}
                          </button>
                          <small>{item.external_receivable_id}</small>
                        </td>
                        <td>{date(item.due_date)}</td>
                        <td className="numeric money">
                          {money(item.amount_cents)}
                        </td>
                        <td>
                          <Badge status="overdue" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Nenhum título vencido" />
            )}
          </section>
          <p className="footnote">
            {data.canceled_count} títulos cancelados nos filtros atuais.
          </p>
        </>
      )}
    </>
  );
}
