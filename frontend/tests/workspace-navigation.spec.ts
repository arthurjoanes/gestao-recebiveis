import { expect, test } from "@playwright/test";
import { bucketLabel, titleCount } from "../src/lib/format";

test("faixas e contagens usam rótulos de apresentação", () => {
  expect(
    ["current", "1_30", "31_60", "61_90", "over_90"].map(bucketLabel),
  ).toEqual([
    "Em dia (inclui hoje)",
    "1–30 dias",
    "31–60 dias",
    "61–90 dias",
    "Acima de 90 dias",
  ]);
  expect([0, 1, 2].map(titleCount)).toEqual([
    "0 títulos",
    "1 título",
    "2 títulos",
  ]);
});

// Presentation contract: deterministic API fixtures, no financial mutation.
const title = {
  id: 41,
  source_system: "fixture",
  external_receivable_id: "AUDIT-41",
  customer_id: 9,
  customer_name: "São José",
  customer_email: "synthetic@example.com",
  description: "Consulta sintética",
  amount_cents: "1000",
  paid_cents: "0",
  remaining_cents: "1000",
  payment_state: "unpaid",
  due_date: "2026-08-01",
  status: "open",
  overdue: true,
  scenario: "success",
};
const session = {
  user: {
    id: 1,
    email: "synthetic@example.com",
    name: "Operador",
    role: "operator",
  },
  csrf_token: "fixture",
};

test("URL preserva filtro, detalhe, histórico nativo e nova aba sem enviar pagamento", async ({
  page,
  context,
}) => {
  const mutations: string[] = [];
  let authenticated = false;
  await context.route(/\/api\/v[12]\//, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() !== "GET") mutations.push(url.pathname);
    if (url.pathname.endsWith("/auth/login")) {
      authenticated = true;
      return route.fulfill({ json: session });
    }
    if (url.pathname.endsWith("/auth/session"))
      return route.fulfill({
        status: authenticated ? 200 : 401,
        json: authenticated ? session : { code: "unauthorized" },
      });
    if (url.pathname.endsWith("/demo"))
      return route.fulfill({
        json: {
          enabled: true,
          business_now: "2026-08-17T10:00:00-03:00",
          business_date: "2026-08-17",
          worker_enabled: false,
          policy: "fixture",
        },
      });
    if (url.pathname.endsWith("/receivables/41"))
      return route.fulfill({
        json: {
          ...title,
          payment: null,
          payments: [],
          reminders: [],
          events: [],
          history: Object.fromEntries(
            ["payments", "reminders", "events"].map((key) => [
              key,
              { total: 0, page: 1, page_size: 20 },
            ]),
          ),
        },
      });
    if (url.pathname.endsWith("/receivables")) {
      expect(
        url.searchParams.get("aging_bucket")
          ? url.searchParams.get("status")
          : "open",
      ).toBe("open");
      return route.fulfill({
        json: { items: [title], total: 1, page: 1, page_size: 20 },
      });
    }
    return route.fulfill({ status: 404, json: { code: "fixture_missing" } });
  });
  await page.goto("/?area=titles&t_q=AUDIT&t_status=paid&t_aging_bucket=1_30");
  await page
    .getByRole("button", { name: "Usar operador", exact: true })
    .click();
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "AUDIT-41", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("open");
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".filter-scope")).toContainText("Aging: 1–30 dias");
  await expect(page.locator(".portfolio-heading")).toContainText(
    "1 título nos filtros atuais",
  );
  const listURL = page.url();
  await page.getByRole("link", { name: "AUDIT-41", exact: true }).click();
  await expect(page).toHaveURL(/title=41/);
  await expect(
    page.getByRole("button", { name: "Registrar pagamento", exact: true }),
  ).toBeVisible();
  const detailURL = page.url();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Registrar pagamento", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(listURL);
  await expect(
    page.getByRole("link", { name: "AUDIT-41", exact: true }),
  ).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(detailURL);
  await page.goBack();
  const href = await page
    .getByRole("link", { name: "AUDIT-41", exact: true })
    .getAttribute("href");
  const other = await context.newPage();
  await other.goto(href!);
  await expect(
    other.getByRole("button", { name: "Registrar pagamento", exact: true }),
  ).toBeVisible();
  await other.close();
  expect(mutations).toEqual(["/api/v1/auth/login"]);
  for (const width of [900, 901, 1024, 1100, 1101]) {
    await page.setViewportSize({ width, height: 950 });
    const styles = await page
      .locator(".portfolio-workbench")
      .evaluate((element) => ({
        columns:
          getComputedStyle(element).gridTemplateColumns.split(" ").length,
        overflow: document.documentElement.scrollWidth > innerWidth,
      }));
    expect(styles.columns).toBe(width <= 1100 ? 1 : 2);
    expect(styles.overflow).toBe(false);
    if (width > 900 && width <= 1100) {
      const filters = await page
        .locator(".portfolio-filters")
        .evaluate((element) => ({
          display: getComputedStyle(element).display,
          columns:
            getComputedStyle(element).gridTemplateColumns.split(" ").length,
        }));
      expect(filters).toEqual({ display: "grid", columns: 2 });
    }
  }
});
