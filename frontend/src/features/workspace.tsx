"use client";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { instant } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import type { Demo, Session } from "@/lib/types";
import { Alert } from "@/components/ui";
import {
  WorkspaceNavigation,
  type Area,
} from "@/components/workspace-navigation";
import { OverviewView } from "@/features/overview";
import { ReceivablesView, type PortfolioFilters } from "@/features/receivables";
import { ReceivableDetailView } from "@/features/receivable-detail";
import { ImportsView } from "@/features/imports";
import { RemindersView } from "@/features/reminders";
import { DemoView } from "@/features/demo";

export function Workspace({
  session,
  onLogout,
}: {
  session: Session;
  onLogout: () => void;
}) {
  const [area, setArea] = useState<Area>("overview");
  const [titleId, setTitleId] = useState<number | null>(null);
  const [returnToTitle, setReturnToTitle] = useState<number | null>(null);
  const [titleFilters, setTitleFilters] = useState<PortfolioFilters>({
    q: "",
    status: "",
    due_from: "",
    due_to: "",
  });
  const [reminderId, setReminderId] = useState<number | null>(null);
  const [demoRevision, setDemoRevision] = useState(0);
  useEffect(() => {
    const destination =
      (area === "reminders" && document.getElementById("reminder-heading")) ||
      document.getElementById("main-content");
    destination?.focus({ preventScroll: true });
  }, [area, titleId]);
  const demo = useResource<Demo>("/demo", demoRevision);
  const [logoutError, setLogoutError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  function navigate(next: Area) {
    setArea(next);
    setTitleId(null);
    setReturnToTitle(null);
    setTitleFilters({ q: "", status: "", due_from: "", due_to: "" });
    setReminderId(null);
    window.scrollTo({ top: 0 });
  }
  function openTitle(id: number, filters?: PortfolioFilters) {
    if (filters) setTitleFilters(filters);
    setArea("titles");
    setTitleId(id);
    window.scrollTo({ top: 0 });
  }
  function openReminder(id: number) {
    setArea("reminders");
    setReminderId(id);
    window.scrollTo({ top: 0 });
  }
  async function logout() {
    setLoggingOut(true);
    setLogoutError("");
    try {
      await api("/auth/logout", { method: "POST" }, session.csrf_token);
      onLogout();
    } catch (failure) {
      setLogoutError(errorMessage(failure));
    } finally {
      setLoggingOut(false);
    }
  }
  return (
    <div className={`workspace area-${area}`}>
      <a className="skip-link" href="#main-content">
        Pular para o conteúdo
      </a>
      <WorkspaceNavigation
        area={area}
        session={session}
        onNavigate={navigate}
        onLogout={() => void logout()}
        loggingOut={loggingOut}
        logoutError={logoutError}
      />
      <div className="workspace-body">
        <header className="topbar">
          <div>
            <span className="environment-label">Demonstração</span>
            <span>Distribuidora fictícia</span>
          </div>
          <div className="business-clock">
            <span>Data comercial</span>
            <strong>
              {demo.data ? instant(demo.data.business_now) : "Carregando…"}{" "}
              <small>São Paulo</small>
            </strong>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="main-content">
          {logoutError && <Alert>{logoutError}</Alert>}
          {demo.error && <Alert>{demo.error}</Alert>}
          {area === "overview" && (
            <OverviewView
              onOpen={openTitle}
              onTitles={(filters) => {
                navigate("titles");
                setTitleFilters(filters);
              }}
            />
          )}
          {area === "titles" &&
            (titleId === null ? (
              <ReceivablesView
                key={JSON.stringify(titleFilters)}
                onOpen={openTitle}
                initialFilters={titleFilters}
                returnToTitle={returnToTitle}
              />
            ) : (
              <ReceivableDetailView
                key={titleId}
                id={titleId}
                session={session}
                onBack={() => {
                  setReturnToTitle(titleId);
                  setTitleId(null);
                }}
                onReminder={openReminder}
              />
            ))}
          {area === "imports" && <ImportsView session={session} />}
          {area === "reminders" && (
            <RemindersView
              selected={reminderId}
              onSelect={setReminderId}
              onTitle={openTitle}
            />
          )}
          {area === "demo" && (
            <DemoView
              session={session}
              onChange={() => setDemoRevision((value) => value + 1)}
            />
          )}
        </main>
      </div>
    </div>
  );
}
