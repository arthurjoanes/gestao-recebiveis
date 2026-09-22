"use client";
import { useState } from "react";
import type { Session } from "@/lib/types";
import { Brand } from "./brand";
import { Alert, Icon, Modal } from "./ui";

export type Area = "overview" | "titles" | "imports" | "reminders" | "demo";
const areas: { id: Area; label: string }[] = [
  { id: "overview", label: "Resumo" },
  { id: "titles", label: "Títulos" },
  { id: "imports", label: "Importações" },
  { id: "reminders", label: "Lembretes" },
  { id: "demo", label: "Demonstração" },
];

export function WorkspaceNavigation({
  area,
  session,
  onNavigate,
  onLogout,
  loggingOut,
  logoutError,
}: {
  area: Area;
  session: Session;
  onNavigate: (area: Area) => void;
  onLogout: () => void;
  loggingOut: boolean;
  logoutError: string;
}) {
  const [dialog, setDialog] = useState<"menu" | "account" | null>(null);
  const role =
    session.user.role === "operator" ? "Operador" : "Somente leitura";
  function navigate(next: Area) {
    onNavigate(next);
    setDialog(null);
  }
  const navigation = (
    <nav aria-label="Navegação principal">
      {areas.map((item) => (
        <button
          key={item.id}
          className={area === item.id ? "active" : ""}
          aria-current={area === item.id ? "page" : undefined}
          onClick={() => navigate(item.id)}
        >
          <Icon name={item.id} />
          {item.label}
          {area === item.id && (
            <span className="nav-current" aria-hidden="true" />
          )}
        </button>
      ))}
    </nav>
  );
  return (
    <>
      <header className="desktop-header">
        <div className="masthead">
          <Brand />
          <span className="workspace-label">
            Contas a receber <span>/</span> Carteira em reais
          </span>
          <div className="user-block">
            <span className="user-avatar">
              {session.user.name.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <strong>{session.user.name}</strong>
              <small>{role}</small>
            </div>
            <button
              aria-label="Sair da conta"
              title="Sair"
              className="icon-button"
              disabled={loggingOut}
              onClick={onLogout}
            >
              <Icon name="logout" />
            </button>
          </div>
        </div>
        {navigation}
      </header>
      <header className="mobile-header">
        <Brand />
        <div className="button-group">
          <button
            className="button secondary small"
            aria-haspopup="dialog"
            aria-expanded={dialog === "menu"}
            onClick={() => setDialog("menu")}
          >
            <Icon name="menu" />
            Menu
          </button>
          <button
            className="icon-button"
            aria-label="Abrir conta"
            aria-haspopup="dialog"
            onClick={() => setDialog("account")}
          >
            <Icon name="account" />
          </button>
        </div>
      </header>
      {dialog && (
        <Modal
          title={dialog === "menu" ? "Menu" : "Conta"}
          onClose={() => setDialog(null)}
          busy={loggingOut}
        >
          {dialog === "menu" ? (
            <div className="mobile-navigation">{navigation}</div>
          ) : (
            <div className="account-details">
              {logoutError && <Alert>{logoutError}</Alert>}
              <strong>{session.user.name}</strong>
              <p>{session.user.email}</p>
              <p>{role} · Distribuidora fictícia</p>
              <button
                className="button secondary"
                disabled={loggingOut}
                onClick={onLogout}
              >
                <Icon name="logout" />
                {loggingOut ? "Saindo…" : "Sair da conta"}
              </button>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
