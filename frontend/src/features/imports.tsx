"use client";
import { ImportPreview } from "./import-preview";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { instant } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type {
  ImportBatch,
  ImportBatchSummary,
  Page,
  Session,
} from "@/lib/types";
import {
  Alert,
  Badge,
  Empty,
  Icon,
  Loading,
  Pagination,
} from "@/components/ui";

export function ImportsView({ session }: { session: Session }) {
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState(1);
  const batches = useResource<Page<ImportBatchSummary>>(
    `/imports?page=${page}`,
    revision,
  );
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [file, setFile] = useState<File | null>(null);
  async function preview() {
    if (!file) return;
    setError("");
    setSuccess("");
    if (file.size > 2 * 1024 * 1024) {
      setError("Arquivo maior que 2 MiB.");
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      body.set("file", file);
      setBatch(
        await api<ImportBatch>(
          "/imports",
          { method: "POST", body },
          session.csrf_token,
        ),
      );
      setRevision((value) => value + 1);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!batch) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api<ImportBatch>(
        `/imports/${batch.id}/confirm`,
        { method: "POST" },
        session.csrf_token,
      );
      setBatch(updated);
      setRevision((value) => value + 1);
      if (updated.status === "confirmed") setSuccess("Importação confirmada.");
      else setError("Lote rejeitado. Confira os erros.");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  async function open(id: number) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      setBatch(await api<ImportBatch>(`/imports/${id}`));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Importações</h1>
          <p>Confira o arquivo antes de incluir os títulos na carteira.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => setRevision((value) => value + 1)}
        >
          <Icon name="refresh" /> Atualizar
        </button>
      </div>
      <div className="import-workbench">
        <ol className="import-steps" aria-label="Etapas da importação">
          <li aria-current={!batch ? "step" : undefined}>
            <span>1</span>Selecionar arquivo
          </li>
          <li
            aria-current={
              batch && batch.status !== "confirmed" ? "step" : undefined
            }
          >
            <span>2</span>Conferir linhas
          </li>
          <li aria-current={batch?.status === "confirmed" ? "step" : undefined}>
            <span>3</span>Confirmar importação
          </li>
        </ol>
        <div className="import-content">
          {session.user.role === "operator" ? (
            <section className="panel upload-panel">
              <div className="upload-icon" aria-hidden="true">
                <Icon name="upload" />
              </div>
              <div>
                <h2>Importar CSV</h2>
                <p>UTF-8 · separado por vírgulas · até 2 MiB e 5.000 linhas</p>
                <p className="footnote">
                  Valores com ponto decimal (120.50), datas AAAA-MM-DD. A
                  confirmação grava os títulos.
                </p>
                <label className="file-label">
                  Arquivo CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    disabled={busy}
                    onChange={(event) => {
                      setFile(event.target.files?.[0] ?? null);
                      setBatch(null);
                      setError("");
                      setSuccess("");
                    }}
                  />
                </label>
              </div>
              <button
                className="button"
                disabled={busy || !file}
                onClick={() => void preview()}
              >
                {busy ? "Processando…" : "Analisar arquivo"}
              </button>
            </section>
          ) : (
            <div className="info-banner">Importação exige perfil operador.</div>
          )}
          <details className="csv-help">
            <summary>Cabeçalho e regras</summary>
            <code>
              source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date
            </code>
            <p>
              Títulos idênticos são ignorados. Divergências bloqueiam o lote
              inteiro. A confirmação revalida os dados no banco.
            </p>
          </details>
          {error && <Alert>{error}</Alert>}
          {success && <Alert success>{success}</Alert>}
          {batch && (
            <ImportPreview
              key={`${batch.id}-${batch.status}`}
              batch={batch}
              canConfirm={session.user.role === "operator"}
              busy={busy}
              onConfirm={() => void confirm()}
            />
          )}
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Histórico de lotes</h2>
              </div>
            </div>
            {batches.error ? (
              <Alert>{batches.error}</Alert>
            ) : batches.loading ? (
              <Loading />
            ) : batches.data?.items.length ? (
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
                        <th>Lote / arquivo</th>
                        <th>Data</th>
                        <th>Linhas</th>
                        <th>Situação</th>
                        <th>Ação</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batches.data.items.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <strong>#{item.id}</strong> {item.filename}
                          </td>
                          <td>{instant(item.created_at)}</td>
                          <td>{item.row_count}</td>
                          <td>
                            <Badge status={item.status} />
                          </td>
                          <td>
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() => void open(item.id)}
                            >
                              Ver resultado
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  page={page}
                  total={batches.data.total}
                  pageSize={batches.data.page_size}
                  onChange={setPage}
                />
              </>
            ) : (
              <Empty title="Nenhum lote importado">
                Selecione um CSV para conferir a prévia.
              </Empty>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
