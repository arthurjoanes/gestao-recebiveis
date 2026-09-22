import { resolve } from "node:path";
import { test, expect, type Page } from "@playwright/test";
import { money } from "../src/lib/format";

test.afterEach(async ({ page, baseURL }) => {
  const response = await page.request.get("/api/v1/auth/session");
  if (!response.ok()) return;
  const session = await response.json();
  if (session.user.role !== "operator") return;
  const paused = await page.request.post("/api/v1/demo/worker", {
    data: { enabled: false },
    headers: {
      "X-CSRF-Token": session.csrf_token,
      Origin: new URL(baseURL!).origin,
    },
  });
  expect(paused.ok()).toBe(true);
});

async function login(page: Page, role: "operador" | "leitor" = "operador") {
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill(`${role}@example.com`);
  await page.getByLabel("Senha", { exact: true }).fill("Recebiveis!2026");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(
    page.getByRole("heading", { name: "Resumo", exact: true }),
  ).toBeVisible();
}
async function navigate(page: Page, name: string) {
  if (await page.getByRole("button", { name: "Menu", exact: true }).isVisible())
    await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name, exact: true })
    .click();
}

async function fillSearch(page: Page, value: string) {
  const search = page.getByLabel("Cliente ou título");
  if (!(await search.isVisible()))
    await page
      .getByRole("button", { name: "Filtrar carteira", exact: true })
      .click();
  await search.fill(value);
}

test("BRL conserva centavos pequenos e inteiros acima da precisão de Number", () => {
  expect(money("1")).toBe("R$ 0,01");
  expect(money("30")).toBe("R$ 0,30");
  expect(money("9007199254740993")).toBe("R$ 90.071.992.547.409,93");
});

test("layout financeiro em cinco larguras, dados longos, diálogo e foco", async ({
  page,
}, info) => {
  await login(page);
  const viewports = [
    { width: 1440, height: 900 },
    { width: 1366, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 320, height: 844 },
  ];
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await expect(
      page.getByText("Carteira em aberto", { exact: false }),
    ).toBeVisible();
    expect(
      await page
        .locator(".row-link")
        .first()
        .evaluate((element) => parseFloat(getComputedStyle(element).fontSize)),
    ).toBeGreaterThanOrEqual(14);
    expect(
      await page
        .locator("td small")
        .first()
        .evaluate((element) => parseFloat(getComputedStyle(element).fontSize)),
    ).toBeGreaterThanOrEqual(12);
    for (const metric of [
      ".metric-open",
      ".metric-overdue",
      ".metric-current",
      ".metric-accent",
    ])
      await expect(page.locator(metric)).toBeVisible();
    const firstAmount = await page
      .locator(".metric > strong")
      .first()
      .boundingBox();
    expect(firstAmount?.y, `saldo visível em ${viewport.width}px`).toBeLessThan(
      480,
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      `overflow em ${viewport.width}px`,
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`overview-${viewport.width}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  const demo = await (await page.request.get("/api/v1/demo")).json();
  const key = `LAYOUT-${Date.now()}`;
  const customer =
    "Distribuidora Fictícia de Materiais para Comércio e Serviços da Região de São Paulo com Nome de Cadastro Extenso";
  const csv = `source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\ne2e,${key},${key},${customer},layout@example.com,Descrição fictícia extensa para verificar a leitura do título e a apresentação completa sem cortar dados financeiros,90071992547409.93,${demo.business_date}\n`;
  await navigate(page, "Importações");
  await page.getByLabel("Arquivo CSV").setInputFiles({
    name: "layout.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  await expect(page.locator(".alert-success")).toContainText(
    "Importação confirmada",
  );
  await navigate(page, "Títulos");
  await fillSearch(page, key);
  await page.getByRole("button", { name: "Filtrar títulos" }).click();
  await page.getByRole("button", { name: key, exact: true }).click();
  await expect(
    page.getByText("R$ 90.071.992.547.409,93", { exact: true }),
  ).toBeVisible();
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      `detalhe longo em ${viewport.width}px`,
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`detail-long-${viewport.width}.png`),
      fullPage: true,
    });
  }
  const payment = page.getByRole("button", {
    name: "Registrar pagamento",
    exact: true,
  });
  await payment.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(payment).toBeFocused();
  const undersized = await page
    .locator("button:visible, input:visible, select:visible, textarea:visible")
    .evaluateAll((elements) =>
      elements
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.width < 24 || rect.height < 24;
        })
        .map((element) => element.textContent),
    );
  expect(undersized).toEqual([]);
  await page
    .getByRole("button", { name: "Cancelar título", exact: true })
    .click();
  await page.getByLabel("Motivo do cancelamento").fill("   ");
  await page.getByRole("button", { name: "Confirmar cancelamento" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "pelo menos 3 caracteres",
  );
  await expect(page.getByLabel("Motivo do cancelamento")).toBeFocused();
  expect(
    await page
      .getByRole("dialog")
      .evaluate((dialog) => dialog.scrollWidth <= dialog.clientWidth),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("cancel-dialog-320.png"),
    fullPage: false,
  });
  await page
    .getByLabel("Motivo do cancelamento")
    .fill("Encerramento do título fictício utilizado para verificar o layout.");
  await page.getByRole("button", { name: "Confirmar cancelamento" }).click();
  await expect(page.locator(".alert-success")).toContainText(
    "Título cancelado",
  );
});

test("filtros recolhidos preservam o recorte aplicado no resumo", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const filters = page.locator(".overview-filter-panel");
  await expect(filters).not.toHaveAttribute("open");
  await filters.locator("summary").click();
  await fillSearch(page, "TIT-0001");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(filters).not.toHaveAttribute("open");
  await expect(filters.locator("summary")).toContainText("Busca: TIT-0001");
  await expect(page.locator(".metric").first()).toContainText(
    "1 título em aberto",
  );
  await filters.locator("summary").click();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue("TIT-0001");
  await page.getByRole("button", { name: "Limpar filtros" }).click();
  await expect(filters.locator("summary")).toContainText("Carteira completa");
  await expect(page.getByLabel("Cliente ou título")).toHaveValue("");
});

test("importar, repetir, simular retry, pagar e conferir histórico real", async ({
  page,
}, info) => {
  await login(page);
  await expect(
    page.getByText("Carteira em aberto", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(
      process.env.PLAYWRIGHT_OUTPUT_DIR ?? "test-results",
      "overview.png",
    ),
    fullPage: true,
  });
  await navigate(page, "Demonstração");
  const pause = page.getByRole("button", {
    name: "Pausar processamento",
    exact: true,
  });
  if (await pause.isVisible()) {
    await pause.click();
    await expect(
      page.getByRole("heading", { name: "Worker pausado" }),
    ).toBeVisible();
  }
  const demo = await (await page.request.get("/api/v1/demo")).json();
  const key = `WEB-${Date.now()}`;
  const csv = `source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\ne2e,${key},${key},Cliente Ficticio Navegador,cliente-web@example.com,Jornada completa no navegador,0.30,${demo.business_date}\n`;
  await navigate(page, "Importações");
  await page.getByLabel("Arquivo CSV").setInputFiles({
    name: `${key}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(
    page
      .getByRole("region", { name: "Prévia do lote" })
      .getByText("R$ 0,30")
      .first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  await expect(page.locator(".alert-success")).toContainText(
    "Importação confirmada",
  );
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(
    page
      .getByRole("region", { name: "Prévia do lote" })
      .getByText("Já existente", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  await expect(page.locator(".alert-success")).toContainText(
    "Importação confirmada",
  );
  await page.screenshot({
    path: info.outputPath("import-confirmed.png"),
    fullPage: true,
  });
  await navigate(page, "Títulos");
  await fillSearch(page, key);
  await page.getByRole("button", { name: "Filtrar títulos" }).click();
  await expect(
    page.getByRole("button", { name: key, exact: true }),
  ).toHaveCount(1);
  await navigate(page, "Demonstração");
  await page.getByLabel("Buscar título em aberto").fill(key);
  await page
    .getByRole("button", { name: "Buscar título", exact: true })
    .click();
  const title = page.getByRole("combobox", { name: "Título", exact: true });
  await expect(
    title.locator("option", { hasText: `${key} · Cliente Ficticio Navegador` }),
  ).toHaveCount(1);
  await title.selectOption({ label: `${key} · Cliente Ficticio Navegador` });
  await page
    .getByRole("combobox", { name: "Cenário", exact: true })
    .selectOption("transient");
  await page.getByRole("button", { name: "Aplicar cenário" }).click();
  await expect(page.locator(".alert-success")).toContainText(
    "Cenário configurado",
  );
  await page.getByRole("button", { name: "Retomar processamento" }).click();
  await expect(
    page.getByRole("heading", { name: "Worker ativo" }),
  ).toBeVisible();
  await navigate(page, "Lembretes");
  await fillSearch(page, key);
  await page.getByRole("button", { name: "Filtrar lembretes" }).click();
  await expect(async () => {
    await page.getByRole("button", { name: "Atualizar", exact: true }).click();
    await expect(
      page.locator("tbody .badge").filter({ hasText: "Entregue" }),
    ).toBeVisible({
      timeout: 1000,
    });
  }).toPass({ timeout: 30_000, intervals: [1000, 2000] });
  await page.getByRole("button", { name: "Ver tentativas" }).click();
  await expect(page.getByRole("heading", { name: /Aceita em/ })).toBeVisible();
  await expect(
    page.getByText("Falha transitória", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("reminder-retry.png"),
    fullPage: true,
  });
  await navigate(page, "Demonstração");
  await page.getByRole("button", { name: "Pausar processamento" }).click();
  await expect(
    page.getByRole("heading", { name: "Worker pausado" }),
  ).toBeVisible();
  await navigate(page, "Títulos");
  await fillSearch(page, key);
  await page.getByRole("button", { name: "Filtrar títulos" }).click();
  await page.getByRole("button", { name: key, exact: true }).click();
  await page.getByRole("button", { name: "Registrar pagamento" }).click();
  await page
    .getByLabel("Observação (opcional)")
    .fill("Pagamento fictício conferido no teste de navegador.");
  await page.getByRole("button", { name: "Confirmar pagamento" }).click();
  await expect(page.locator(".alert-success")).toContainText(
    "Pagamento registrado",
  );
  await expect(page.getByText("Pago", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Linha do tempo" }),
  ).toBeVisible();
  await expect(page.locator(".timeline")).toContainText(/pagamento/i);
  await page.screenshot({
    path: info.outputPath("title-paid.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("title-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await navigate(page, "Resumo");
  await expect(
    page.getByText("Carteira em aberto", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(
      process.env.PLAYWRIGHT_OUTPUT_DIR ?? "test-results",
      "mobile.png",
    ),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("leitor consulta sem controles de mutação e navega com teclado", async ({
  page,
}) => {
  await login(page, "leitor");
  await expect(
    page.getByText("Somente leitura", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ver todos os vencidos" }).click();
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("overdue");
  await expect(page.locator("tbody .badge").first()).toHaveText("Vencido");
  expect(
    (await page.locator("tbody .badge").allTextContents()).every(
      (value) => value === "Vencido",
    ),
  ).toBe(true);
  await navigate(page, "Títulos");
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("");
  await navigate(page, "Importações");
  await expect(
    page.getByText("Importação exige perfil operador.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByLabel("Arquivo CSV")).toHaveCount(0);
  await navigate(page, "Demonstração");
  await expect(
    page.getByRole("button", { name: "Avançar relógio" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Aplicar cenário" }),
  ).toBeDisabled();
  await page.keyboard.press("Control+Home");
  await page.getByRole("button", { name: "Sair da conta" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
});

test("sessão expirada volta ao login e mostra a recuperação", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/v1/receivables?**", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        code: "session_expired",
        message: "Sessão expirada",
      }),
    }),
  );
  await navigate(page, "Títulos");
  await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: "Sessão expirada" }),
  ).toBeVisible();
});

test("CSV inválido e conflito bloqueiam lote sem alterar totais", async ({
  page,
}, info) => {
  await login(page);
  const demo = await (await page.request.get("/api/v1/demo")).json();
  const key = `CONFLICT-WEB-${Date.now()}`;
  const header =
    "source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\n";
  const row = (id: string, amount: string) =>
    `e2e,${id},${key},Cliente Ficticio Conflito,conflito-web@example.com,Lote de verificacao,${amount},${demo.business_date}\n`;
  async function upload(content: string, name: string) {
    await page.getByLabel("Arquivo CSV").setInputFiles({
      name,
      mimeType: "text/csv",
      buffer: Buffer.from(content),
    });
    await page.getByRole("button", { name: "Analisar arquivo" }).click();
    await expect(
      page
        .getByRole("region", { name: "Prévia do lote" })
        .getByRole("heading", { name, exact: true }),
    ).toBeVisible();
  }
  await navigate(page, "Importações");
  await upload(header + row(key, "12.34"), "baseline.csv");
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  await expect(
    page.locator(".alert-success").filter({ hasText: "Importação confirmada" }),
  ).toBeVisible();
  const before = await (await page.request.get("/api/v1/overview")).json();
  await upload(header + row(`${key}-BAD`, "1.234"), "invalido.csv");
  await expect(
    page.getByRole("heading", { name: /erro\(s\) no arquivo/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirmar importação" }),
  ).toBeDisabled();
  await upload(
    header + row(`${key}-NEW`, "10.00") + row(key, "99.99"),
    "conflitante.csv",
  );
  await expect(
    page.getByRole("heading", { name: /erro\(s\) no arquivo/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirmar importação" }),
  ).toBeDisabled();
  await expect(
    page
      .getByRole("region", { name: "Prévia do lote" })
      .getByText("existing_conflict", { exact: true }),
  ).toBeVisible();
  const after = await (await page.request.get("/api/v1/overview")).json();
  for (const field of [
    "open_cents",
    "overdue_cents",
    "received_cents",
    "open_count",
    "paid_count",
  ])
    expect(after[field]).toBe(before[field]);
  const newTitle = await (
    await page.request.get(`/api/v1/receivables?q=${key}-NEW`)
  ).json();
  expect(newTitle.total).toBe(0);
  await page.screenshot({
    path: info.outputPath("import-conflict.png"),
    fullPage: true,
  });
});

test("erro de rede permite tentar novamente e busca vazia explica resultado", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/v1/receivables?**", (route) =>
    route.abort("connectionfailed"),
  );
  await navigate(page, "Títulos");
  await expect(
    page.getByRole("alert").filter({ hasText: "Falha na conexão" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Nenhum título encontrado" }),
  ).toHaveCount(0);
  await page.unroute("**/api/v1/receivables?**");
  await fillSearch(page, `SEM-RESULTADO-${Date.now()}`);
  await page.getByRole("button", { name: "Filtrar títulos" }).click();
  await expect(
    page.getByRole("heading", { name: "Nenhum título encontrado" }),
  ).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: "Falha na conexão" }),
  ).toHaveCount(0);
  await navigate(page, "Demonstração");
  const selector = page.getByRole("combobox", { name: "Título", exact: true });
  await expect(selector).toBeEnabled();
  expect(await selector.locator("option").count()).toBeGreaterThan(1);
  let release = () => {};
  const delayed = new Promise<void>((resolve) => {
    release = resolve;
  });
  const staleQuery = `ATRASADA-${Date.now()}`;
  await page.route("**/api/v1/receivables?**", async (route) => {
    if (new URL(route.request().url()).searchParams.get("q") === staleQuery)
      await delayed;
    await route.continue();
  });
  await page.getByLabel("Buscar título em aberto").fill(staleQuery);
  await page
    .getByRole("button", { name: "Buscar título", exact: true })
    .click();
  await expect(selector).toBeDisabled();
  await expect(selector.locator("option")).toHaveCount(1);
  await page.getByLabel("Buscar título em aberto").fill("TIT-0001");
  await page
    .getByRole("button", { name: "Buscar título", exact: true })
    .click();
  await expect(
    selector.locator("option").filter({ hasText: "TIT-0001" }),
  ).toHaveCount(1);
  const lateResponse = page.waitForResponse(
    (response) => new URL(response.url()).searchParams.get("q") === staleQuery,
  );
  release();
  await lateResponse;
  await expect(
    selector.locator("option").filter({ hasText: "TIT-0001" }),
  ).toHaveCount(1);
});

test("menu móvel tem cinco destinos, prende foco e devolve foco ao fechar", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await login(page);
  const menu = page.getByRole("button", { name: "Menu", exact: true });
  await menu.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Menu" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("navigation").getByRole("button")).toHaveCount(
    5,
  );
  for (const name of [
    "Resumo",
    "Títulos",
    "Importações",
    "Lembretes",
    "Demonstração",
  ]) {
    const bounds = await dialog
      .getByRole("button", { name, exact: true })
      .boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(320);
    expect(bounds!.height).toBeGreaterThanOrEqual(44);
  }
  await dialog
    .getByRole("button", { name: "Demonstração", exact: true })
    .focus();
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Fechar diálogo" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(
    dialog.getByRole("button", { name: "Demonstração", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await page.keyboard.press("Enter");
  await dialog
    .getByRole("button", { name: "Demonstração", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Demonstração", exact: true }),
  ).toBeVisible();
  await expect(page.locator("#main-content")).toBeFocused();
  const clock = page.getByLabel("Nova data e hora comercial");
  await clock.fill("2026-01-01T10:00");
  await page.getByRole("button", { name: "Avançar relógio" }).click();
  await expect(clock).toHaveAttribute("aria-invalid", "true");
  await expect(clock).toBeFocused();
  await page.getByRole("button", { name: "Abrir conta" }).click();
  await expect(page.getByRole("dialog", { name: "Conta" })).toContainText(
    "operador@example.com",
  );
  await page.screenshot({
    path: info.outputPath("mobile-account.png"),
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Abrir conta" })).toBeFocused();
  await navigate(page, "Resumo");
  await menu.click();
  await page.screenshot({
    path: info.outputPath("mobile-menu.png"),
    fullPage: false,
  });
});

test("intervalos inválidos mantêm saldo válido, formulário aberto e erro associado", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const metric = page.locator(".metric").first();
  await expect(metric).toContainText("Carteira em aberto");
  const before = await metric.textContent();
  const filters = page.locator(".overview-filter-panel");
  const metricsBox = await page.locator(".metrics").boundingBox();
  const filtersBox = await filters.boundingBox();
  // O recorte antecede o livro financeiro e permanece recolhido na abertura.
  expect(filtersBox!.y + filtersBox!.height).toBeLessThanOrEqual(metricsBox!.y);
  await filters.locator("summary").click();
  let requests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/overview?")) requests++;
  });
  await page.locator('[name="due_from"]').fill("2026-08-17");
  await page.locator('[name="due_to"]').fill("2026-08-16");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(filters).toHaveAttribute("open");
  await expect(page.locator('[name="due_from"]')).toBeFocused();
  await expect(page.locator('[name="due_from"]')).toHaveAttribute(
    "aria-describedby",
    "overview-due-error",
  );
  await expect(page.locator("#overview-due-error")).toContainText(
    "Vencimento inicial deve ser anterior ou igual ao final.",
  );
  await expect(metric).toHaveText(before!);
  expect(requests).toBe(0);
  await filters.screenshot({
    path: info.outputPath("invalid-period-inline.png"),
  });
  await page.locator('[name="due_to"]').fill("2026-08-17");
  await page.locator('[name="received_from"]').fill("2026-08-18");
  await page.locator('[name="received_to"]').fill("2026-08-17");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.locator('[name="received_from"]')).toBeFocused();
  await expect(page.locator("#overview-received-error")).toBeVisible();
  await expect(metric).toHaveText(before!);
  expect(requests).toBe(0);
  await page.getByRole("button", { name: "Limpar filtros" }).click();
  await expect(page.locator('[aria-invalid="true"]')).toHaveCount(0);
  await expect(page.locator('[name="due_from"]')).toHaveValue("");
  const demo = await (await page.request.get("/api/v1/demo")).json();
  await page.getByRole("button", { name: "Hoje", exact: true }).click();
  await expect(page.locator('[name="received_from"]')).toHaveValue(
    demo.business_date,
  );
  await expect(page.locator('[name="received_to"]')).toHaveValue(
    demo.business_date,
  );
  await page.getByRole("button", { name: "Este mês", exact: true }).click();
  await expect(page.locator('[name="received_from"]')).toHaveValue(
    demo.business_date.slice(0, 8) + "01",
  );
  await page
    .getByRole("button", { name: "Personalizado", exact: true })
    .click();
  await expect(page.locator('[name="received_from"]')).toBeFocused();
  await page.locator('[name="received_from"]').fill("0001-01-01");
  await page.locator('[name="received_to"]').fill("9999-12-31");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(filters).not.toHaveAttribute("open");
  await expect(page.locator(".metric-accent")).toContainText("31/12/9999");
});

test("saldo abre títulos com busca e vencimento preservados e retorno mantém recorte", async ({
  page,
}) => {
  await login(page);
  const overdue = await (
    await page.request.get("/api/v1/receivables?status=overdue&page_size=1")
  ).json();
  const title = overdue.items[0];
  await page.locator(".overview-filter-panel summary").click();
  await fillSearch(page, `  ${title.external_receivable_id}  `);
  await page.locator('[name="due_from"]').fill(title.due_date);
  await page.locator('[name="due_to"]').fill(title.due_date);
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.locator(".metric").first()).toContainText(
    "1 título em aberto",
  );
  await page
    .getByRole("button", { name: "Ver títulos vencidos", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue(
    title.external_receivable_id,
  );
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("overdue");
  await expect(page.locator('[name="due_from"]')).toHaveValue(title.due_date);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: title.external_receivable_id, exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  let releaseReturn!: () => void;
  const delayedReturn = new Promise<void>((resolve) => {
    releaseReturn = resolve;
  });
  await page.route(
    "**/api/v1/receivables?**",
    async (route) => {
      await delayedReturn;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    await page.getByRole("button", { name: "Voltar para títulos" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".loading")).toBeVisible();
    await expect(page.locator("#main-content")).toBeFocused();
  } finally {
    releaseReturn();
  }
  await expect(
    page.getByRole("button", {
      name: title.external_receivable_id,
      exact: true,
    }),
  ).toBeFocused();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue(
    title.external_receivable_id,
  );
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("overdue");
  await expect(page.locator('[name="due_from"]')).toHaveValue(title.due_date);
  await expect(page.locator('[name="due_to"]')).toHaveValue(title.due_date);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "Limpar filtros" }).click();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue("");
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("");
  await page.locator('[name="due_from"]').fill("2026-08-18");
  await page.locator('[name="due_to"]').fill("2026-08-17");
  await page.getByRole("button", { name: "Filtrar títulos" }).click();
  await expect(page.locator("#title-period-error")).toBeVisible();
  await expect(page.locator('[name="due_from"]')).toBeFocused();
  await navigate(page, "Resumo");
  await page
    .getByRole("button", { name: "Ver títulos em dia", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("current");
  await expect(page.locator("tbody .badge").first()).toHaveText("Em aberto");
});

test("prévia pagina 51 registros sem gravar títulos e trata arquivo vazio e grande", async ({
  page,
}) => {
  await login(page);
  await navigate(page, "Importações");
  await expect(
    page.getByRole("button", { name: "Analisar arquivo" }),
  ).toBeDisabled();
  const file = page.getByLabel("Arquivo CSV");
  await file.setInputFiles({
    name: "vazio.csv",
    mimeType: "text/csv",
    buffer: Buffer.alloc(0),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(
    page.getByRole("region", { name: "Prévia do lote" }),
  ).toContainText("Arquivo vazio");
  await expect(
    page.getByRole("button", { name: "Confirmar importação" }),
  ).toBeDisabled();
  await file.setInputFiles({
    name: "grande.csv",
    mimeType: "text/csv",
    buffer: Buffer.alloc(2 * 1024 * 1024 + 1, "x"),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "maior que 2 MiB" }),
  ).toBeVisible();
  const before = await (await page.request.get("/api/v1/overview")).json();
  const key = `PAGES-${Date.now()}`;
  const header =
    "source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\n";
  const rows = Array.from(
    { length: 51 },
    (_, i) =>
      `e2e,${key}-${i},${key},Distribuição São José,preview@example.com,Conferência ${i},0.01,2026-08-17\n`,
  ).join("");
  await file.setInputFiles({
    name: "51-linhas.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(header + rows),
  });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  const preview = page.getByRole("region", { name: "Prévia do lote" });
  await expect(preview.locator("tbody tr")).toHaveCount(50);
  await preview.getByRole("button", { name: "Próxima", exact: true }).click();
  await expect(preview.locator("tbody tr")).toHaveCount(1);
  await expect(preview).toContainText(`${key}-50`);
  await preview.getByRole("button", { name: "Anterior", exact: true }).click();
  await expect(preview.locator("tbody tr")).toHaveCount(50);
  expect(await (await page.request.get("/api/v1/overview")).json()).toEqual(
    before,
  );
});

test("detalhe do lembrete preserva filtros, página, rolagem e foco na fila", async ({
  page,
}) => {
  await login(page);
  await navigate(page, "Lembretes");
  await fillSearch(page, "TIT-");
  await page
    .getByRole("button", { name: "Filtrar lembretes", exact: true })
    .click();
  const list = page.getByRole("region", {
    name: "Fila de lembretes",
    exact: true,
  });
  await expect(list.locator("tbody tr").first()).toBeVisible();
  await list.getByRole("button", { name: "Próxima", exact: true }).click();
  await expect(list.locator(".pagination")).toContainText("Página 2");
  const trigger = list
    .getByRole("button", { name: "Ver tentativas", exact: true })
    .last();
  await trigger.scrollIntoViewIfNeeded();
  const scrollBefore = await list
    .locator(".table-scroll")
    .evaluate((el) => el.scrollTop);
  const titleBefore = await list.locator("tbody tr").last().innerText();
  await trigger.click();
  await expect(page.locator("#reminder-heading")).toBeFocused();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue("TIT-");
  await expect(list.locator(".pagination")).toContainText("Página 2");
  await expect(list.locator("tbody tr").last()).toHaveText(titleBefore, {
    useInnerText: true,
  });
  expect(
    await list.locator(".table-scroll").evaluate((el) => el.scrollTop),
  ).toBe(scrollBefore);
  await page
    .getByRole("button", { name: "Fechar detalhe", exact: true })
    .click();
  await expect(trigger).toBeFocused();
  await expect(page.locator("#reminder-detail")).toHaveCount(0);

  await trigger.click();
  await page.getByRole("button", { name: "Atualizar", exact: true }).click();
  await expect(list.locator(".loading")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Fechar detalhe", exact: true })
    .click();
  await expect(trigger).toBeFocused();

  await trigger.click();
  await fillSearch(page, "sem-correspondencia-na-fila");
  await page
    .getByRole("button", { name: "Filtrar lembretes", exact: true })
    .click();
  await expect(
    list.getByText("Nenhum lembrete encontrado", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Fechar detalhe", exact: true })
    .click();
  await expect(
    list.getByRole("heading", { name: "Fila de envios", exact: true }),
  ).toBeFocused();

  await navigate(page, "Títulos");
  await fillSearch(page, "TIT-0001");
  await page
    .getByRole("button", { name: "Filtrar títulos", exact: true })
    .click();
  await page.getByRole("button", { name: "TIT-0001", exact: true }).click();
  await page
    .getByRole("button", { name: "Ver tentativas", exact: true })
    .first()
    .click();
  await expect(page.locator("#reminder-heading")).toBeFocused();
  await expect(list.locator(".loading")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Fechar detalhe", exact: true })
    .click();
  await expect(list.locator(":focus")).toHaveCount(1);
});

test("voltar do título preserva a página e o foco, com saída para página esvaziada", async ({
  page,
}) => {
  await login(page);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await navigate(page, "Títulos");
    await fillSearch(page, "TIT-");
    await page
      .getByRole("button", { name: "Filtrar títulos", exact: true })
      .click();
    await page.getByRole("button", { name: "Próxima", exact: true }).click();
    await expect(page.locator(".pagination")).toContainText("Página 2");
    const title = await page.locator(".row-link").last().innerText();
    await page.getByRole("button", { name: title, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Voltar para títulos", exact: true })
      .click();
    await expect(page.locator(".pagination")).toContainText("Página 2");
    await expect(page.getByLabel("Cliente ou título")).toHaveValue("TIT-");
    await expect(
      page.getByRole("button", { name: title, exact: true }),
    ).toBeFocused();
  }

  const heldTitle = await page.locator(".row-link").last().innerText();
  await page.getByRole("button", { name: heldTitle, exact: true }).click();
  let releaseReturn!: () => void;
  const delayedReturn = new Promise<void>((resolve) => {
    releaseReturn = resolve;
  });
  await page.route(
    "**/api/v1/receivables?**",
    async (route) => {
      await delayedReturn;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    await page
      .getByRole("button", { name: "Voltar para títulos", exact: true })
      .click();
    await expect(page.locator(".loading")).toBeVisible();
    await fillSearch(page, "TIT-00");
  } finally {
    releaseReturn();
  }
  await expect(page.locator(".pagination")).toContainText("Página 2");
  await expect(page.getByLabel("Cliente ou título")).toBeFocused();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue("TIT-00");

  const title = await page.locator(".row-link").last().innerText();
  await page.getByRole("button", { name: title, exact: true }).click();
  // Resposta controlada: os títulos da segunda página deixaram o recorte enquanto o detalhe estava aberto.
  await page.route("**/api/v1/receivables?**", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, items: [], total: 20, page: 2 },
    });
  });
  await page
    .getByRole("button", { name: "Voltar para títulos", exact: true })
    .click();
  await expect(
    page.getByText("Esta página ficou vazia", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Títulos", exact: true }),
  ).toBeFocused();
  await page.unroute("**/api/v1/receivables?**");
  await page
    .getByRole("button", { name: "Voltar à primeira página", exact: true })
    .click();
  await expect(page.locator(".pagination")).toContainText("Página 1");
  await expect(page.getByLabel("Cliente ou título")).toHaveValue("TIT-");
  await expect(page.locator(".row-link").first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Títulos", exact: true }),
  ).toBeFocused();
});

test("carteira compacta mantém recorte aplicado, validação e retorno ao controle", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await login(page);
  const overview = await (await page.request.get("/api/v1/overview")).json();
  for (const [selector, field] of [
    [".metric-open", "open_cents"],
    [".metric-overdue", "overdue_cents"],
    [".metric-current", "current_cents"],
    [".metric-accent", "received_cents"],
  ]) {
    await expect(page.locator(`${selector} > strong`)).toHaveText(
      money(overview[field]),
    );
    await expect(page.locator(selector)).toBeVisible();
  }
  await navigate(page, "Títulos");
  const search = page.getByLabel("Cliente ou título");
  const toggle = page.getByRole("button", {
    name: "Filtrar carteira",
    exact: true,
  });
  await expect(search).toBeHidden();
  await expect(page.locator(".row-link").first()).toBeVisible();
  await expect(page.locator(".filter-scope")).toContainText(
    "Todas as situações",
  );
  await toggle.focus();
  await page.keyboard.press("Enter");
  await search.fill("TIT-0001");
  // Digitar não altera o recorte nem os resultados antes de enviar o formulário.
  await expect(page.locator(".filter-scope")).not.toContainText("TIT-0001");
  await page
    .getByRole("button", { name: "Filtrar títulos", exact: true })
    .click();
  await expect(toggle).toBeFocused();
  await expect(search).toBeHidden();
  await expect(page.locator(".filter-scope")).toContainText("Busca: TIT-0001");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await toggle.click();
  await page.locator('[name="due_from"]').fill("2026-08-18");
  await page.locator('[name="due_to"]').fill("2026-08-17");
  await page
    .getByRole("button", { name: "Filtrar títulos", exact: true })
    .click();
  await expect(page.locator("#title-period-error")).toBeVisible();
  await expect(page.locator('[name="due_from"]')).toBeFocused();
  await expect(page.locator(".filter-scope")).toContainText(
    "Todos os vencimentos",
  );
  await page
    .getByRole("button", { name: "Limpar filtros", exact: true })
    .click();
  await expect(page.locator("#title-period-error")).toHaveCount(0);
  await expect(search).toHaveValue("");
  await page
    .getByRole("button", { name: "Fechar filtros", exact: true })
    .click();
  await expect(search).toBeHidden();
  await expect(toggle).toBeFocused();
});
