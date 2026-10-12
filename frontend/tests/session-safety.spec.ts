import { expect, test, type Page } from "@playwright/test";
import { PAYMENT_INTENT_PREFIX } from "../src/lib/payment-intent";
import type { ReceivableDetail, Session } from "../src/lib/types";

async function login(page: Page, role = "operador", visit = true) {
  if (visit) await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill(`${role}@example.com`);
  await page.getByLabel("Senha", { exact: true }).fill("Recebiveis!2026");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Resumo", exact: true }),
  ).toBeVisible();
}

async function navigate(page: Page, name: string) {
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name, exact: true })
    .click();
}

async function currentSession(page: Page): Promise<Session> {
  const response = await page.request.get("/api/v1/auth/session");
  expect(response.ok()).toBe(true);
  return response.json();
}

async function publicPage(page: Page) {
  await expect(
    page.getByRole("button", { name: "Entrar", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".workspace")).toHaveCount(0);
  await expect(page.locator("#main-content")).toHaveCount(0);
}

async function openFreshTitle(page: Page, session: Session) {
  const demo = await (await page.request.get("/api/v1/demo")).json();
  // Scheduling continues while sends are paused; keep this title outside its window.
  const dueDate = new Date(`${demo.business_date}T12:00:00Z`);
  dueDate.setUTCDate(dueDate.getUTCDate() + 7);
  const code = `SESSION-TIMEOUT-${Date.now()}`;
  const headers = {
    "X-CSRF-Token": session.csrf_token,
    Origin: new URL(page.url()).origin,
  };
  const csv = `source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\nsession-safety,${code},${code},Cliente Ficticio Timeout,timeout@example.com,Fixture de timeout,1.00,${dueDate.toISOString().slice(0, 10)}\n`;
  const preview = await page.request.post("/api/v1/imports", {
    headers,
    multipart: {
      file: {
        name: "timeout.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv),
      },
    },
  });
  expect(preview.ok()).toBe(true);
  const batch = await preview.json();
  expect(
    (
      await page.request.post(`/api/v1/imports/${batch.id}/confirm`, {
        headers,
      })
    ).ok(),
  ).toBe(true);
  const list = await (
    await page.request.get(`/api/v1/receivables?q=${code}`)
  ).json();
  const title: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${list.items[0].id}`)
  ).json();
  await navigate(page, "Títulos");
  if (!(await page.getByLabel("Cliente ou título").isVisible()))
    await page
      .getByRole("button", { name: "Filtrar carteira", exact: true })
      .click();
  await page.getByLabel("Cliente ou título").fill(code);
  await page
    .getByRole("button", { name: "Filtrar títulos", exact: true })
    .click();
  await page.getByRole("button", { name: code, exact: true }).click();
  await expect(
    page.getByRole("heading", { name: code, exact: true }),
  ).toBeVisible();
  return title;
}

for (const commit of [false, true]) {
  test(`logout local remove conteúdo e intenção quando a resposta falha ${commit ? "após" : "antes do"} commit`, async ({
    page,
  }) => {
    await login(page);
    const session = await currentSession(page);
    const key = `${PAYMENT_INTENT_PREFIX}${session.user.id}:999999`;
    await page.evaluate(
      ({ key, userId }) =>
        sessionStorage.setItem(
          key,
          JSON.stringify({
            version: 1,
            user_id: userId,
            receivable_id: 999999,
            created_at: Date.now(),
            payload: {
              idempotency_key: "session-safety-fixture",
              note: "Fixture fictícia",
              amount_cents: "1",
            },
          }),
        ),
      { key, userId: session.user.id },
    );
    await page.route(
      "**/api/v1/auth/logout",
      async (route) => {
        if (commit) expect((await route.fetch()).ok()).toBe(true);
        await route.abort("failed");
      },
      { times: 1 },
    );
    await page
      .getByRole("button", { name: "Sair da conta", exact: true })
      .click();
    await publicPage(page);
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Não foi possível confirmar o encerramento",
    );
    expect(
      await page.evaluate((key) => sessionStorage.getItem(key), key),
    ).toBeNull();
    expect((await page.request.get("/api/v1/auth/session")).status()).toBe(
      commit ? 401 : 200,
    );
    await page.reload();
    await publicPage(page);
    await login(page, "leitor", false);
    expect((await currentSession(page)).user.role).toBe("reader");
    await expect(
      page.getByText("Somente leitura", { exact: true }),
    ).toBeVisible();
  });
}

test("401 de operação antiga não encerra o acesso de outra conta", async ({
  page,
}) => {
  await login(page);
  await navigate(page, "Demonstração");
  let release!: () => void;
  let started!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const intercepted = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route(
    "**/api/v1/demo/worker",
    async (route) => {
      started();
      await pending;
      await route.fulfill({
        status: 401,
        json: { code: "session_expired", message: "Sessão anterior encerrada" },
      });
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: /^(Retomar|Pausar) processamento$/ })
    .click();
  await intercepted;
  await page
    .getByRole("button", { name: "Sair da conta", exact: true })
    .click();
  await publicPage(page);
  await login(page, "leitor", false);
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/demo/worker") &&
      response.status() === 401,
  );
  release();
  await (await response).finished();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await expect(page.locator(".workspace")).toBeVisible();
  await expect(
    page.getByText("Somente leitura", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Entrar", exact: true }),
  ).toHaveCount(0);
  expect((await currentSession(page)).user.role).toBe("reader");
});

test("200 atrasado da conta anterior não reapresenta uma prévia protegida", async ({
  page,
}) => {
  await login(page);
  await navigate(page, "Importações");
  await page.getByLabel("Arquivo CSV").setInputFiles({
    name: "session-safety.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("fixture fictícia"),
  });
  let release!: () => void;
  let started!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const intercepted = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route(
    "**/api/v1/imports",
    async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      started();
      await pending;
      await route.fulfill({
        status: 200,
        json: {
          id: 999999,
          filename: "PREVIA-CONTA-ANTERIOR",
          status: "preview",
          rows: [],
          errors: [],
          total_rows: 0,
          valid_rows: 0,
        },
      });
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Analisar arquivo", exact: true })
    .click();
  await intercepted;
  await page
    .getByRole("button", { name: "Sair da conta", exact: true })
    .click();
  await publicPage(page);
  await login(page, "leitor", false);
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/imports") && response.status() === 200,
  );
  release();
  await (await response).finished();
  await navigate(page, "Importações");
  await expect(
    page.getByText("PREVIA-CONTA-ANTERIOR", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Analisar arquivo", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Importação exige perfil operador.", { exact: true }),
  ).toBeVisible();
  expect((await currentSession(page)).user.role).toBe("reader");
});

test("403 revalida permissões e retira controles de operador revogados", async ({
  page,
}) => {
  await login(page);
  const session = await currentSession(page);
  await navigate(page, "Demonstração");
  let checks = 0;
  // Responses model a role change without altering the shared demo users.
  await page.route("**/api/v1/auth/session", async (route) => {
    checks += 1;
    await route.fulfill({
      status: 200,
      json: { ...session, user: { ...session.user, role: "reader" } },
    });
  });
  await page.route(
    "**/api/v1/demo/worker",
    (route) =>
      route.fulfill({
        status: 403,
        json: { code: "forbidden", message: "Permissão revogada" },
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: /^(Retomar|Pausar) processamento$/ })
    .click();
  await expect(
    page.getByText("Somente leitura", { exact: true }),
  ).toBeVisible();
  await navigate(page, "Demonstração");
  await expect(
    page.getByRole("button", { name: /^(Retomar|Pausar) processamento$/ }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Avançar relógio", exact: true }),
  ).toBeDisabled();
  expect(checks).toBeGreaterThanOrEqual(1);
});

test("403 com sessão válida conserva o arquivo preenchido e a intenção congelada", async ({
  page,
}) => {
  await login(page);
  const session = await currentSession(page);
  await navigate(page, "Importações");
  const filename = "draft-preservado.csv";
  await page.getByLabel("Arquivo CSV").setInputFiles({
    name: filename,
    mimeType: "text/csv",
    buffer: Buffer.from("fixture fictícia"),
  });
  const key = `${PAYMENT_INTENT_PREFIX}${session.user.id}:999998`;
  const frozen = JSON.stringify({
    version: 1,
    user_id: session.user.id,
    receivable_id: 999998,
    created_at: Date.now(),
    payload: {
      idempotency_key: "fixture-chave-preservada",
      note: "Fixture fictícia",
      amount_cents: "1",
    },
  });
  await page.evaluate(
    ({ key, frozen }) => sessionStorage.setItem(key, frozen),
    { key, frozen },
  );
  let checks = 0;
  await page.route("**/api/v1/auth/session", async (route) => {
    checks += 1;
    await route.continue();
  });
  await page.route(
    "**/api/v1/imports",
    (route) =>
      route.fulfill({
        status: 403,
        json: { code: "csrf_invalid", message: "CSRF rejeitado" },
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Analisar arquivo", exact: true })
    .click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "CSRF rejeitado",
  );
  expect(
    await page
      .getByLabel("Arquivo CSV")
      .evaluate((input) => (input as HTMLInputElement).files?.[0]?.name),
  ).toBe(filename);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBe(
    frozen,
  );
  expect((await currentSession(page)).user.role).toBe("operator");
  expect(checks).toBeGreaterThanOrEqual(1);
});

test("timeout real de pagamento conserva chave e payload sem reenviar automaticamente", async ({
  page,
}) => {
  await login(page);
  const session = await currentSession(page);
  const title = await openFreshTitle(page, session);
  const key = `${PAYMENT_INTENT_PREFIX}${session.user.id}:${title.id}`;
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("partial");
  await page.getByLabel("Valor recebido (R$)").fill("0,01");
  await page
    .getByLabel("Observação (opcional)")
    .fill("Fixture fictícia de timeout");
  let requests = 0;
  let payload: unknown;
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      requests += 1;
      payload = route.request().postDataJSON();
      await pending;
      await route.abort("failed");
    },
  );
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Não recebemos a resposta a tempo",
    { timeout: 35_000 },
  );
  const frozen = await page.evaluate((key) => sessionStorage.getItem(key), key);
  expect(frozen).not.toBeNull();
  expect(JSON.parse(frozen!).payload).toEqual(payload);
  await expect(page.getByLabel("Valor recebido (R$)")).toBeDisabled();
  await expect(page.getByLabel("Observação (opcional)")).toHaveValue(
    "Fixture fictícia de timeout",
  );
  await expect(
    page.getByRole("button", {
      name: "Tentar novamente com a mesma intenção",
      exact: true,
    }),
  ).toBeEnabled();
  expect(requests).toBe(1);
  const after: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${title.id}`)
  ).json();
  expect(after.payments).toEqual(title.payments);
  expect(after.paid_cents).toBe(title.paid_cents);
  expect(after.remaining_cents).toBe(title.remaining_cents);
  expect(after.events).toEqual(title.events);
  release();
});

test("JSON inválido em resposta 200 mostra recuperação e preserva o arquivo", async ({
  page,
}) => {
  await login(page);
  await navigate(page, "Importações");
  const filename = "resposta-invalida.csv";
  await page.getByLabel("Arquivo CSV").setInputFiles({
    name: filename,
    mimeType: "text/csv",
    buffer: Buffer.from("fixture fictícia"),
  });
  await page.route(
    "**/api/v1/imports",
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{resposta incompleta",
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Analisar arquivo", exact: true })
    .click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Recebemos uma resposta inválida",
  );
  expect(
    await page
      .getByLabel("Arquivo CSV")
      .evaluate((input) => (input as HTMLInputElement).files?.[0]?.name),
  ).toBe(filename);
  await expect(
    page.getByRole("button", { name: "Analisar arquivo", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Confirmar importação", exact: true }),
  ).toHaveCount(0);
});
