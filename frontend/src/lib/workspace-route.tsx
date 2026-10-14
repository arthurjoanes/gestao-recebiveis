"use client";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { AnchorHTMLAttributes } from "react";
import type { Area } from "@/components/workspace-navigation";
import type { PortfolioFilters } from "@/features/receivables";
const emptyAgingFilters = {
  q: "",
  customer_id: "",
  due_from: "",
  due_to: "",
  bucket: "",
  page: 1,
};
const emptyStatementFilters = {
  q: "",
  status: "",
  due_from: "",
  due_to: "",
  received_from: "",
  received_to: "",
  page: 1,
  payment_page: 1,
};
import type { StatementFilters } from "@/features/reports";

export type TitleOrigin =
  | { kind: "portfolio" }
  | { kind: "aging" }
  | { kind: "statement"; customerId: number };
export const emptyPortfolioFilters: PortfolioFilters = {
  q: "",
  status: "",
  due_from: "",
  due_to: "",
};
export const defaultRoute = {
  area: "overview" as Area,
  titleId: null as number | null,
  customerId: null as number | null,
  reminderId: null as number | null,
  titleOrigin: { kind: "portfolio" } as TitleOrigin,
  statementOrigin: null as { id: number; origin: TitleOrigin } | null,
  titleFilters: emptyPortfolioFilters,
  overviewFilters: {
    q: "",
    due_from: "",
    due_to: "",
    received_from: "",
    received_to: "",
  },
  agingFilters: emptyAgingFilters,
  statementFilters: {} as Record<number, StatementFilters>,
};
export type WorkspaceRoute = typeof defaultRoute;
const areas = new Set([
  "overview",
  "titles",
  "reports",
  "imports",
  "reminders",
  "demo",
]);
const statuses = new Set([
  "",
  "open",
  "paid",
  "canceled",
  "overdue",
  "current",
]);
const buckets = new Set(["", "current", "1_30", "31_60", "61_90", "over_90"]);
function id(value: string | null) {
  return value && /^[1-9]\d*$/.test(value) && Number(value) <= 2147483647
    ? Number(value)
    : null;
}
function filters<T extends object>(
  params: URLSearchParams,
  prefix: string,
  defaults: T,
): T {
  const value = { ...defaults } as Record<string, string | number>;
  for (const [key, initial] of Object.entries(defaults)) {
    const raw = params.get(prefix + key);
    if (raw === null) continue;
    if (key.endsWith("page") || key === "page")
      value[key] = Math.min(id(raw) ?? 1, 10000);
    else if (key === "customer_id") value[key] = id(raw)?.toString() ?? "";
    else if (key === "status") value[key] = statuses.has(raw) ? raw : "";
    else if (key === "bucket" || key === "aging_bucket")
      value[key] = buckets.has(raw) ? raw : "";
    else if (key.endsWith("_from") || key.endsWith("_to")) {
      const parsed = new Date(raw + "T00:00:00Z");
      value[key] =
        /^\d{4}-\d{2}-\d{2}$/.test(raw) &&
        raw >= "0001-01-01" &&
        Number.isFinite(parsed.valueOf()) &&
        parsed.toISOString().slice(0, 10) === raw
          ? raw
          : "";
    } else if (typeof initial === "string")
      value[key] = raw.replaceAll("\0", "").slice(0, 200);
  }
  for (const prefix of ["due", "received"]) {
    if (
      value[prefix + "_from"] &&
      value[prefix + "_to"] &&
      value[prefix + "_from"] > value[prefix + "_to"]
    )
      value[prefix + "_to"] = "";
  }
  if (value.aging_bucket) value.status = "open";
  return value as T;
}
export function readWorkspaceRoute(search: string): WorkspaceRoute {
  const p = new URLSearchParams(search);
  const customerId = id(p.get("customer"));
  const originCustomer = id(p.get("origin_customer"));
  const titleOrigin: TitleOrigin =
    p.get("origin") === "aging"
      ? { kind: "aging" }
      : p.get("origin") === "statement" && originCustomer
        ? { kind: "statement", customerId: originCustomer }
        : { kind: "portfolio" };
  const statementCustomer = customerId ?? originCustomer;
  return {
    ...defaultRoute,
    area: areas.has(p.get("area") ?? "") ? (p.get("area") as Area) : "overview",
    titleId: id(p.get("title")),
    customerId,
    reminderId: id(p.get("reminder")),
    titleOrigin,
    overviewFilters: filters(p, "o_", defaultRoute.overviewFilters),
    statementOrigin: id(p.get("return_title"))
      ? { id: id(p.get("return_title"))!, origin: titleOrigin }
      : null,
    titleFilters: filters(p, "t_", {
      ...emptyPortfolioFilters,
      customer_id: "",
      aging_bucket: "",
      page: 1,
    }),
    agingFilters: filters(p, "a_", emptyAgingFilters),
    statementFilters: statementCustomer
      ? { [statementCustomer]: filters(p, "s_", emptyStatementFilters) }
      : {},
  };
}
export function workspaceHref(route: WorkspaceRoute): string {
  const p = new URLSearchParams();
  p.set("area", route.area);
  if (route.titleId) p.set("title", String(route.titleId));
  if (route.customerId) p.set("customer", String(route.customerId));
  if (route.statementOrigin)
    p.set("return_title", String(route.statementOrigin.id));
  if (route.reminderId) p.set("reminder", String(route.reminderId));
  if (route.titleOrigin.kind !== "portfolio")
    p.set("origin", route.titleOrigin.kind);
  if (route.titleOrigin.kind === "statement")
    p.set("origin_customer", String(route.titleOrigin.customerId));
  const customer =
    route.customerId ??
    (route.titleOrigin.kind === "statement"
      ? route.titleOrigin.customerId
      : null);
  for (const [prefix, values] of [
    ["t_", route.titleFilters],
    ["o_", route.overviewFilters],
    ["a_", route.agingFilters],
    ["s_", customer ? route.statementFilters[customer] : null],
  ] as const) {
    for (const [key, value] of Object.entries(values ?? {}))
      if (value !== "" && value !== undefined && value !== 1)
        p.set(prefix + key, String(value));
  }
  return "/?" + p.toString();
}
export function useWorkspaceRoute() {
  const [route, setRoute] = useState(() =>
    readWorkspaceRoute(
      typeof window === "undefined" ? "" : window.location.search,
    ),
  );
  const restoring = useRef(false);
  const mounted = useRef(false);
  useEffect(() => {
    const restore = () => {
      restoring.current = true;
      setRoute(readWorkspaceRoute(window.location.search));
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    const href = workspaceHref(route);
    if (!mounted.current || restoring.current) {
      mounted.current = true;
      restoring.current = false;
      window.history.replaceState(window.history.state, "", href);
    } else if (window.location.pathname + window.location.search !== href)
      window.history.pushState(null, "", href);
  }, [route]);
  return [route, setRoute] as const;
}
export const WorkspaceRouteContext = createContext(defaultRoute);
export function RouteLink({
  to,
  onNavigate,
  ...props
}: Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "onClick"> & {
  to: Partial<WorkspaceRoute>;
  onNavigate: () => void;
}) {
  const route = useContext(WorkspaceRouteContext);
  const next = { ...route, ...to };
  if (to.titleId && !to.titleOrigin)
    next.titleOrigin =
      route.area === "reports"
        ? route.customerId
          ? { kind: "statement", customerId: route.customerId }
          : { kind: "aging" }
        : { kind: "portfolio" };
  if (to.customerId && route.area === "titles" && route.titleId)
    next.statementOrigin = { id: route.titleId, origin: route.titleOrigin };
  return (
    <a
      {...props}
      href={workspaceHref(next)}
      onClick={(event) => {
        if (
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        )
          return;
        event.preventDefault();
        onNavigate();
      }}
    />
  );
}
