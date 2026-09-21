"use client";
import { useState } from "react";
import { date } from "@/lib/format";

export interface OverviewFilters {
  q: string;
  due_from: string;
  due_to: string;
  received_from: string;
  received_to: string;
}
export const emptyOverviewFilters: OverviewFilters = {
  q: "",
  due_from: "",
  due_to: "",
  received_from: "",
  received_to: "",
};

export function portfolioScope(
  filters: Pick<OverviewFilters, "due_from" | "due_to">,
) {
  if (!filters.due_from && !filters.due_to) return "Todos os vencimentos";
  return `Vencimento: ${filters.due_from ? date(filters.due_from) : "sem início"} a ${filters.due_to ? date(filters.due_to) : "sem fim"}`;
}

export function OverviewFilterForm({
  filters,
  businessDate,
  onApply,
}: {
  filters: OverviewFilters;
  businessDate?: string;
  onApply: (filters: OverviewFilters) => void;
}) {
  const [draft, setDraft] = useState(filters);
  const [errors, setErrors] = useState({ due: "", received: "" });
  const applied = [
    filters.q && `Busca: ${filters.q}`,
    portfolioScope(filters),
    filters.received_from || filters.received_to
      ? `Recebimento: ${filters.received_from ? date(filters.received_from) : "início do mês"} a ${filters.received_to ? date(filters.received_to) : "data comercial"}`
      : "recebimentos do mês comercial",
  ]
    .filter(Boolean)
    .join(" · ");
  function update(name: keyof OverviewFilters, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }
  return (
    <details className="panel overview-filter-panel">
      <summary>
        <span>Filtros da carteira e dos recebimentos</span>
        <small>
          {!filters.q && !filters.due_from && !filters.due_to
            ? "Carteira completa · "
            : ""}
          {applied}
        </small>
      </summary>
      <form
        className="filters overview-filters"
        onReset={(event) => {
          event.preventDefault();
          setDraft(emptyOverviewFilters);
          setErrors({ due: "", received: "" });
          onApply(emptyOverviewFilters);
        }}
        onSubmit={(event) => {
          event.preventDefault();
          const start =
            draft.received_from ||
            (businessDate ? businessDate.slice(0, 8) + "01" : "");
          const end = draft.received_to || businessDate;
          const nextErrors = {
            due:
              draft.due_from && draft.due_to && draft.due_from > draft.due_to
                ? "Vencimento inicial deve ser anterior ou igual ao final."
                : "",
            received:
              start && end && start > end
                ? "Recebimento inicial deve ser anterior ou igual ao final."
                : "",
          };
          setErrors(nextErrors);
          if (nextErrors.due || nextErrors.received) {
            (
              event.currentTarget.elements.namedItem(
                nextErrors.due ? "due_from" : "received_from",
              ) as HTMLInputElement
            )?.focus();
            return;
          }
          onApply({ ...draft, q: draft.q.trim() });
          const panel = event.currentTarget.closest("details");
          panel?.removeAttribute("open");
          panel?.querySelector("summary")?.focus();
        }}
      >
        <label className="search-field">
          Cliente ou título
          <input
            name="q"
            type="search"
            maxLength={200}
            placeholder="Buscar na carteira"
            value={draft.q}
            onChange={(event) => update("q", event.target.value)}
          />
          <small>Busca aplicada à carteira e aos recebimentos.</small>
        </label>
        <fieldset>
          <legend>Vencimento</legend>
          <p className="filter-help">Filtra os títulos da carteira.</p>
          <div className="date-pair">
            <label>
              De
              <input
                type="date"
                name="due_from"
                min="0001-01-01"
                max="9999-12-31"
                value={draft.due_from}
                onChange={(event) => update("due_from", event.target.value)}
                aria-invalid={!!errors.due}
                aria-describedby={errors.due ? "overview-due-error" : undefined}
              />
            </label>
            <label>
              Até
              <input
                type="date"
                name="due_to"
                min="0001-01-01"
                max="9999-12-31"
                value={draft.due_to}
                onChange={(event) => update("due_to", event.target.value)}
                aria-invalid={!!errors.due}
                aria-describedby={errors.due ? "overview-due-error" : undefined}
              />
            </label>
          </div>
          {errors.due && (
            <p className="field-error" role="alert" id="overview-due-error">
              {errors.due}
            </p>
          )}
        </fieldset>
        <fieldset>
          <legend>Data do recebimento</legend>
          <p className="filter-help">
            Filtra pagamentos pela data comercial da baixa.
          </p>
          <div className="period-shortcuts" aria-label="Atalhos de recebimento">
            <button
              type="button"
              className="text-button"
              disabled={!businessDate}
              onClick={() =>
                setDraft({
                  ...draft,
                  received_from: businessDate!,
                  received_to: businessDate!,
                })
              }
            >
              Hoje
            </button>
            <button
              type="button"
              className="text-button"
              disabled={!businessDate}
              onClick={() =>
                setDraft({
                  ...draft,
                  received_from: businessDate!.slice(0, 8) + "01",
                  received_to: businessDate!,
                })
              }
            >
              Este mês
            </button>
            <button
              type="button"
              className="text-button"
              onClick={(event) =>
                (
                  event.currentTarget.form?.elements.namedItem(
                    "received_from",
                  ) as HTMLInputElement
                )?.focus()
              }
            >
              Personalizado
            </button>
          </div>
          <div className="date-pair">
            <label>
              De
              <input
                type="date"
                name="received_from"
                min="0001-01-01"
                max="9999-12-31"
                value={draft.received_from}
                onChange={(event) =>
                  update("received_from", event.target.value)
                }
                aria-invalid={!!errors.received}
                aria-describedby={
                  errors.received ? "overview-received-error" : undefined
                }
              />
            </label>
            <label>
              Até
              <input
                type="date"
                name="received_to"
                min="0001-01-01"
                max="9999-12-31"
                value={draft.received_to}
                onChange={(event) => update("received_to", event.target.value)}
                aria-invalid={!!errors.received}
                aria-describedby={
                  errors.received ? "overview-received-error" : undefined
                }
              />
            </label>
          </div>
          <small>Em branco: mês comercial até hoje.</small>
          {errors.received && (
            <p
              className="field-error"
              role="alert"
              id="overview-received-error"
            >
              {errors.received}
            </p>
          )}
        </fieldset>
        <div className="button-group">
          <button className="button" type="submit" disabled={!businessDate}>
            Aplicar filtros
          </button>
          <button className="text-button" type="reset">
            Limpar filtros
          </button>
        </div>
      </form>
    </details>
  );
}
