import type { CSSProperties } from "react";
import type { Aging } from "@/lib/types";
import { money, titleCount } from "@/lib/format";
import { portfolioShare } from "@/lib/portfolio-share";

export function AgingChart({ data }: { data: Aging }) {
  const overdue = data.buckets
    .filter((bucket) => bucket.key !== "current")
    .reduce((sum, bucket) => sum + BigInt(bucket.remaining_cents), 0n);
  const share = portfolioShare(overdue.toString(), data.open_cents);
  return (
    <section
      className="panel aging-analysis"
      aria-label="Distribuição do saldo por atraso"
    >
      <div className="section-heading">
        <div>
          <h2>Saldo por atraso</h2>
          <p>Por prazo de atraso · vencimentos selecionados</p>
        </div>
        <div className="aging-share">
          <strong>
            {share.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%
          </strong>
          <span>do saldo está vencido</span>
        </div>
      </div>
      {BigInt(data.open_cents) === 0n ? (
        <p className="padded">Nenhum saldo em aberto neste período.</p>
      ) : (
        <ol className="aging-chart">
          {data.buckets.map((bucket) => {
            const percentage = portfolioShare(
              bucket.remaining_cents,
              data.open_cents,
            );
            return (
              <li key={bucket.key}>
                <div className="aging-bar-label">
                  <strong>{bucket.label}</strong>
                  <span>{titleCount(bucket.title_count)}</span>
                </div>
                <div className="aging-track" aria-hidden="true">
                  <span
                    className={
                      bucket.key === "current"
                        ? "aging-bar current"
                        : "aging-bar"
                    }
                    style={{ "--share": percentage / 100 } as CSSProperties}
                  />
                </div>
                <div className="aging-bar-value">
                  <strong>{money(bucket.remaining_cents)}</strong>
                  <span>
                    {percentage.toLocaleString("pt-BR", {
                      maximumFractionDigits: 2,
                    })}
                    % do saldo
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
