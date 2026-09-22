"use client";
import { useState } from "react";
import { date, instant, money } from "@/lib/format";
import type { ImportBatch } from "@/lib/types";
import { Badge, Pagination } from "@/components/ui";

export function ImportPreview({
  batch,
  canConfirm,
  busy,
  onConfirm,
}: {
  batch: ImportBatch;
  canConfirm: boolean;
  busy: boolean;
  onConfirm: () => void;
}) {
  const [page, setPage] = useState(1);
  const [errorPage, setErrorPage] = useState(1);
  return (
    <section className="panel" aria-label="Prévia do lote">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Lote #{batch.id}</p>
          <h2>{batch.filename}</h2>
          <p>{instant(batch.created_at)}</p>
        </div>
        <Badge status={batch.status} />
      </div>
      <div className="batch-stats">
        <div>
          <span>Linhas</span>
          <strong>{batch.report.row_count}</strong>
        </div>
        <div>
          <span>Novos títulos</span>
          <strong>{batch.report.new_count}</strong>
        </div>
        <div>
          <span>Já existentes</span>
          <strong>{batch.report.existing_count}</strong>
        </div>
        <div>
          <span>Repetidas no lote</span>
          <strong>{batch.report.duplicate_count}</strong>
        </div>
        <div>
          <span>Total do lote</span>
          <strong>{money(batch.report.total_cents)}</strong>
        </div>
      </div>
      {batch.report.errors.length > 0 && (
        <div className="batch-errors" role="alert">
          <h3>{batch.report.errors.length} erro(s) no arquivo</h3>
          <ul>
            {batch.report.errors
              .slice((errorPage - 1) * 50, errorPage * 50)
              .map((item, index) => (
                <li key={`${item.line}-${index}`}>
                  <strong>Linha {item.line}:</strong> {item.message}{" "}
                  <code>{item.code}</code>
                </li>
              ))}
          </ul>
          {batch.report.errors.length > 50 && (
            <Pagination
              page={errorPage}
              pageSize={50}
              total={batch.report.errors.length}
              onChange={setErrorPage}
            />
          )}
        </div>
      )}
      {batch.report.rows.length > 0 && (
        <div
          className="table-scroll preview-table"
          role="region"
          aria-label="Prévia com rolagem horizontal"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Linha</th>
                <th>Título</th>
                <th>Cliente</th>
                <th>Vencimento</th>
                <th className="numeric">Valor</th>
                <th>Conferência</th>
              </tr>
            </thead>
            <tbody>
              {batch.report.rows
                .slice((page - 1) * 50, page * 50)
                .map((item, index) => (
                  <tr key={`${item.line}-${index}`}>
                    <td>{item.line}</td>
                    <td>{item.external_receivable_id || "—"}</td>
                    <td>{item.customer_name || "—"}</td>
                    <td>{date(item.due_date)}</td>
                    <td className="numeric money">
                      {item.amount_cents ? money(item.amount_cents) : "—"}
                    </td>
                    <td>
                      <Badge status={item.status} />
                      {item.message && <small>{item.message}</small>}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      {batch.report.rows.length > 50 && (
        <Pagination
          page={page}
          pageSize={50}
          total={batch.report.rows.length}
          onChange={setPage}
        />
      )}
      {canConfirm && !["confirmed", "rejected"].includes(batch.status) && (
        <div className="panel-footer">
          <p>
            Títulos idênticos serão ignorados. Uma divergência impede a
            confirmação de todo o lote.
          </p>
          <button
            className="button"
            disabled={busy || batch.report.errors.length > 0}
            onClick={onConfirm}
          >
            {busy ? "Confirmando…" : "Confirmar importação"}
          </button>
        </div>
      )}
    </section>
  );
}
