"use client";
import { RouteLink } from "@/lib/workspace-route";
import { useState } from "react";
import { query } from "@/lib/api";
import { date, instant, money } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import {
  OverviewFilterForm,
  type OverviewFilters,
  portfolioScope,
} from "./overview-filters";
import type { PortfolioFilters } from "./receivables";
import type { Aging, Overview, Page, Receivable } from "@/lib/types";
import { AgingChart } from "./aging-chart";
import { Alert, Badge, Empty, Icon, Loading } from "@/components/ui";

export function OverviewView({
  onOpen,
  onTitles,
  filters,
  onFiltersChange: setFilters,
}: {
  onOpen: (id: number) => void;
  onTitles: (filters: PortfolioFilters) => void;
  filters: OverviewFilters;
  onFiltersChange: (filters: OverviewFilters) => void;
}) {
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
  const aging = useResource<Aging>(
    `/reports/aging?${query({ q: filters.q, due_from: filters.due_from, due_to: filters.due_to, page_size: 1 })}`,
    revision,
  );
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
          <p>Saldo da carteira, vencimentos e pagamentos recebidos.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          <Icon name="refresh" /> Atualizar
        </button>
      </div>
      <OverviewFilterForm
        filters={filters}
        businessDate={data?.business_date}
        onApply={setFilters}
      />
      <div className="overview-ledger">
        {overview.error && <Alert>{overview.error}</Alert>}
        {overview.loading ? (
          <Loading />
        ) : (
          data && (
            <>
              <section
                className="metrics"
                aria-label="Posição da carteira e recebimentos"
              >
                <div className="balance-position">
                  <article className="metric metric-open">
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
                    <RouteLink
                      to={{
                        area: "titles",
                        titleId: null,
                        customerId: null,
                        titleOrigin: { kind: "portfolio" },
                        titleFilters: {
                          q: filters.q,
                          due_from: filters.due_from,
                          due_to: filters.due_to,
                          status: "open",
                        },
                      }}
                      className="text-button"
                      onNavigate={() => openTitles("open")}
                    >
                      Ver títulos em aberto <Icon name="right" />
                    </RouteLink>
                  </article>
                  <article className="metric metric-overdue">
                    <div className="metric-label">Vencido</div>
                    <strong>{money(data.overdue_cents)}</strong>
                    <p>{data.overdue_count} títulos · parte do aberto</p>
                    <small>Antes de {date(data.business_date)}</small>
                    <RouteLink
                      to={{
                        area: "titles",
                        titleId: null,
                        customerId: null,
                        titleOrigin: { kind: "portfolio" },
                        titleFilters: {
                          q: filters.q,
                          due_from: filters.due_from,
                          due_to: filters.due_to,
                          status: "overdue",
                        },
                      }}
                      className="text-button"
                      onNavigate={() => openTitles("overdue")}
                    >
                      Ver títulos vencidos <Icon name="right" />
                    </RouteLink>
                  </article>
                  <article className="metric metric-current">
                    <div className="metric-label">Em dia</div>
                    <strong>{money(data.current_cents)}</strong>
                    <p>{data.current_count} títulos · parte do aberto</p>
                    <small>
                      A partir de {date(data.business_date)} · inclui hoje
                    </small>
                    <RouteLink
                      to={{
                        area: "titles",
                        titleId: null,
                        customerId: null,
                        titleOrigin: { kind: "portfolio" },
                        titleFilters: {
                          q: filters.q,
                          due_from: filters.due_from,
                          due_to: filters.due_to,
                          status: "current",
                        },
                      }}
                      className="text-button"
                      onNavigate={() => openTitles("current")}
                    >
                      Ver títulos em dia <Icon name="right" />
                    </RouteLink>
                  </article>
                </div>
                <article className="metric metric-accent">
                  <div className="metric-label">Recebido no período</div>
                  <strong>{money(data.received_cents)}</strong>
                  <p>
                    {data.paid_count}{" "}
                    {data.paid_count === 1 ? "recebimento" : "recebimentos"}
                  </p>
                  <small>
                    Filtrado pela data do pagamento ·{" "}
                    {data.received_from ? date(data.received_from) : "início"} a{" "}
                    {data.received_to ? date(data.received_to) : "hoje"}
                    {filters.q ? ` · Busca: ${filters.q}` : ""}
                  </small>
                  <p className="movement-note">
                    Recebimentos não compõem o saldo em aberto.
                  </p>
                </article>
              </section>
              <p className="footnote position-caption">
                Posição consultada em {instant(data.generated_at)}. A carteira
                usa a data comercial {date(data.business_date)}; os recebimentos
                respeitam seu próprio período.
              </p>
            </>
          )
        )}
        {!overview.loading && data && (
          <div className="overview-collection">
            {aging.error ? (
              <Alert>{aging.error}</Alert>
            ) : aging.loading ? (
              <Loading />
            ) : (
              aging.data && <AgingChart data={aging.data} />
            )}
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Títulos vencidos</h2>
                </div>
                <div className="attention-actions">
                  <RouteLink
                    to={{
                      area: "titles",
                      titleId: null,
                      customerId: null,
                      titleOrigin: { kind: "portfolio" },
                      titleFilters: {
                        q: filters.q,
                        due_from: filters.due_from,
                        due_to: filters.due_to,
                        status: "overdue",
                      },
                    }}
                    className="text-button"
                    onNavigate={() => openTitles("overdue")}
                  >
                    Ver todos os vencidos <Icon name="right" />
                  </RouteLink>
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
                  aria-label="Lista de títulos vencidos"
                  tabIndex={0}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Cliente / título</th>
                        <th>Vencimento</th>
                        <th className="numeric">Saldo</th>
                        <th>Situação</th>
                      </tr>
                    </thead>
                    <tbody>
                      {urgent.data.items.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <RouteLink
                              to={{ area: "titles", titleId: item.id }}
                              className="text-button row-link"
                              onNavigate={() => onOpen(item.id)}
                            >
                              {item.customer_name}
                            </RouteLink>
                            <small>{item.external_receivable_id}</small>
                          </td>
                          <td>{date(item.due_date)}</td>
                          <td className="numeric money">
                            {money(item.remaining_cents)}
                          </td>
                          <td>
                            <Badge status="overdue" />
                            {item.payment_state === "partial" && (
                              <Badge status="partial" />
                            )}
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
          </div>
        )}
      </div>
    </>
  );
}
