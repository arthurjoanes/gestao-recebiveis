"use client";
import { useEffect, useState } from "react";
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
import {
  AgingView,
  CustomerStatementView,
  emptyStatementFilters,
} from "@/features/reports";
import { activatePaymentAccount } from "@/lib/payment-intent";

import {
  useWorkspaceRoute,
  WorkspaceRouteContext,
} from "@/lib/workspace-route";

export function Workspace({
  session,
  onLogout,
}: {
  session: Session;
  onLogout: () => void;
}) {
  const [route, setRoute] = useWorkspaceRoute();
  const {
    area,
    titleId,
    customerId,
    statementOrigin,
    titleOrigin,
    agingFilters,
    statementFilters,
    titleFilters,
    reminderId,
  } = route;
  const setArea = (area: Area) => setRoute((value) => ({ ...value, area }));
  const setTitleId = (titleId: typeof route.titleId) =>
    setRoute((value) => ({ ...value, titleId }));
  const setCustomerId = (customerId: typeof route.customerId) =>
    setRoute((value) => ({ ...value, customerId }));
  const setStatementOrigin = (statementOrigin: typeof route.statementOrigin) =>
    setRoute((value) => ({ ...value, statementOrigin }));
  const setTitleOrigin = (titleOrigin: typeof route.titleOrigin) =>
    setRoute((value) => ({ ...value, titleOrigin }));
  const setAgingFilters = (agingFilters: typeof route.agingFilters) =>
    setRoute((value) => ({ ...value, agingFilters }));
  const setTitleFilters = (titleFilters: PortfolioFilters) =>
    setRoute((value) => ({ ...value, titleFilters }));
  const setReminderId = (reminderId: typeof route.reminderId) =>
    setRoute((value) => ({ ...value, reminderId }));
  const [returnToTitle, setReturnToTitle] = useState<number | null>(null);
  const [reportReturnToTitle, setReportReturnToTitle] = useState<number | null>(
    null,
  );
  const [demoRevision, setDemoRevision] = useState(0);
  useEffect(() => {
    activatePaymentAccount(session.user.id);
  }, [session.user.id]);
  useEffect(() => {
    const destination =
      (area === "reminders" && document.getElementById("reminder-heading")) ||
      document.getElementById("main-content");
    destination?.focus({ preventScroll: true });
  }, [area, titleId, customerId]);
  const demo = useResource<Demo>("/demo", demoRevision);
  function navigate(next: Area) {
    setArea(next);
    setStatementOrigin(null);
    setTitleId(null);
    setTitleOrigin({ kind: "portfolio" });
    setCustomerId(null);
    setReturnToTitle(null);
    setReportReturnToTitle(null);
    setTitleFilters({ q: "", status: "", due_from: "", due_to: "" });
    setReminderId(null);
    window.scrollTo({ top: 0 });
  }
  function openTitle(id: number, filters?: PortfolioFilters) {
    setReportReturnToTitle(null);
    setTitleOrigin({ kind: "portfolio" });
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
  return (
    <WorkspaceRouteContext.Provider value={route}>
      <div className={`workspace area-${area}`}>
        <a className="skip-link" href="#main-content">
          Pular para o conteúdo
        </a>
        <WorkspaceNavigation
          area={area}
          session={session}
          onNavigate={navigate}
          onLogout={onLogout}
          loggingOut={false}
          logoutError=""
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
            {demo.error && <Alert>{demo.error}</Alert>}
            {area === "overview" && (
              <OverviewView
                key={JSON.stringify(route.overviewFilters)}
                filters={route.overviewFilters}
                onFiltersChange={(overviewFilters) =>
                  setRoute((value) => ({ ...value, overviewFilters }))
                }
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
                  onFiltersChange={setTitleFilters}
                  returnToTitle={returnToTitle}
                />
              ) : (
                <ReceivableDetailView
                  key={titleId}
                  id={titleId}
                  session={session}
                  onBack={() => {
                    if (titleOrigin.kind === "aging") {
                      setReportReturnToTitle(titleId);
                      setArea("reports");
                      setCustomerId(null);
                    } else if (titleOrigin.kind === "statement") {
                      setReportReturnToTitle(titleId);
                      setArea("reports");
                      setCustomerId(titleOrigin.customerId);
                    } else setReturnToTitle(titleId);
                    setTitleId(null);
                  }}
                  backLabel={
                    titleOrigin.kind === "statement"
                      ? "Voltar para o extrato"
                      : titleOrigin.kind === "aging"
                        ? "Voltar para o aging"
                        : "Voltar para títulos"
                  }
                  onReminder={openReminder}
                  onStatement={(id) => {
                    setReportReturnToTitle(null);
                    if (
                      titleOrigin.kind !== "statement" ||
                      titleOrigin.customerId !== id
                    )
                      setStatementOrigin({ id: titleId, origin: titleOrigin });
                    setCustomerId(id);
                    setArea("reports");
                  }}
                />
              ))}
            {area === "reports" &&
              (customerId === null ? (
                <AgingView
                  key={JSON.stringify(agingFilters)}
                  returnToTitle={reportReturnToTitle}
                  filters={agingFilters}
                  onFiltersChange={setAgingFilters}
                  onTitles={(filters) => {
                    navigate("titles");
                    setTitleFilters(filters);
                  }}
                  onOpen={(id) => {
                    setReportReturnToTitle(null);
                    setTitleOrigin({ kind: "aging" });
                    setArea("titles");
                    setTitleId(id);
                    window.scrollTo({ top: 0 });
                  }}
                  onStatement={(id) => {
                    setReportReturnToTitle(null);
                    setStatementOrigin(null);
                    setCustomerId(id);
                  }}
                />
              ) : (
                <CustomerStatementView
                  returnToTitle={reportReturnToTitle}
                  key={`${customerId}:${JSON.stringify(statementFilters[customerId])}`}
                  customerId={customerId}
                  filters={
                    statementFilters[customerId] ?? emptyStatementFilters
                  }
                  onFiltersChange={(filters) =>
                    setRoute((value) => ({
                      ...value,
                      statementFilters: {
                        ...value.statementFilters,
                        [customerId]: filters,
                      },
                    }))
                  }
                  onOpen={(id) => {
                    setReportReturnToTitle(null);
                    setTitleOrigin({ kind: "statement", customerId });
                    setArea("titles");
                    setTitleId(id);
                    window.scrollTo({ top: 0 });
                  }}
                  onBack={() => {
                    setReportReturnToTitle(null);
                    if (statementOrigin !== null) {
                      setArea("titles");
                      setTitleId(statementOrigin.id);
                      setTitleOrigin(statementOrigin.origin);
                    }
                    setCustomerId(null);
                  }}
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
    </WorkspaceRouteContext.Provider>
  );
}
