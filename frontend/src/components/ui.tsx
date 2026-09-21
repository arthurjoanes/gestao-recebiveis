"use client";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

const labels: Record<string, string> = {
  open: "Em aberto",
  paid: "Pago",
  canceled: "Cancelado",
  overdue: "Vencido",
  pending: "Pendente",
  processing: "Processando",
  sent: "Entregue",
  retry_scheduled: "Nova tentativa",
  failed: "Falhou",
  superseded: "Ultrapassado",
  skipped: "Ultrapassado",
  confirmed: "Confirmado",
  rejected: "Rejeitado",
  preview: "Prévia",
  uploaded: "Prévia",
  valid: "Válido",
  new: "Novo",
  existing: "Já existente",
  duplicate: "Repetido",
  invalid: "Inválido",
  conflict: "Conflito",
  blocked: "Bloqueado",
  authorized: "Autorizada",
  success: "Sucesso",
  transient: "Falha transitória",
  permanent: "Falha permanente",
  response_lost: "Resposta perdida",
  unknown: "Reconciliação pendente",
  accepted: "Aceita",
  transient_error: "Falha transitória",
  permanent_error: "Falha permanente",
  uncertain: "Reconciliação pendente",
};
export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge badge-${status}`}>{labels[status] ?? status}</span>
  );
}
export function Alert({
  children,
  success = false,
}: {
  children: ReactNode;
  success?: boolean;
}) {
  return (
    <div
      className={`alert ${success ? "alert-success" : "alert-error"}`}
      role={success ? "status" : "alert"}
    >
      {children}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      Carregando…
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span aria-hidden="true">
        <Icon name="titles" />
      </span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Pagination({
  page,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination">
      <span>
        {total} registro{total === 1 ? "" : "s"} · Página {page} de {pages}
      </span>
      <div>
        <button
          className="button secondary small"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Anterior
        </button>
        <button
          className="button secondary small"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Próxima
        </button>
      </div>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="modal-title"
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button, input, select, textarea, a[href], summary, [tabindex]:not([tabindex="-1"])',
          ),
        ).filter(
          (element) =>
            !element.matches(":disabled") &&
            element.getClientRects().length > 0,
        );
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="modal-heading">
        <h2 id="modal-title">{title}</h2>
        <button
          aria-label="Fechar diálogo"
          className="icon-button"
          disabled={busy}
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Icon({
  name,
}: {
  name:
    | "overview"
    | "titles"
    | "imports"
    | "reminders"
    | "demo"
    | "refresh"
    | "logout"
    | "close"
    | "right"
    | "left"
    | "upload"
    | "menu"
    | "account";
}) {
  const paths = {
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
    account: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21v-2a8 8 0 0 1 16 0v2" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5" />
        <path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1" />
      </>
    ),
    logout: (
      <>
        <path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
    right: <path d="M4 12h16m-6-6 6 6-6 6" />,
    left: <path d="M20 12H4m6-6-6 6 6 6" />,
    upload: <path d="M12 17V3m-5 5 5-5 5 5M4 17v4h16v-4" />,
    overview: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    titles: (
      <>
        <rect x="5" y="3" width="14" height="18" rx="2" />
        <path d="M9 8h6M9 12h6M9 16h3" />
      </>
    ),
    imports: (
      <>
        <path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5" />
      </>
    ),
    reminders: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6" />
      </>
    ),
    demo: (
      <>
        <path d="m9 3 12 9-12 9V3Z" />
        <path d="M3 3v18" />
      </>
    ),
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
