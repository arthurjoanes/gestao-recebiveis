import { expect, test, type Page } from "@playwright/test";
import { parseBrl } from "../src/lib/format";
import {
  PAYMENT_INTENT_PREFIX,
  PAYMENT_INTENT_TTL_MS,
} from "../src/lib/payment-intent";
import type { ReceivableDetail, Session } from "../src/lib/types";

async function login(page: Page, role = "operador") {
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill(`${role}@example.com`);
  await page.getByLabel("Senha", { exact: true }).fill("Recebiveis!2026");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
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
async function openTitle(page: Page, code: string) {
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
}
async function createTitle(page: Page, count = 1) {
  const session: Session = await (
    await page.request.get("/api/v1/auth/session")
  ).json();
  const demo = await (await page.request.get("/api/v1/demo")).json();
  const code = `PARCIAL-${Date.now()}`;
  const csv = `source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\n${Array.from({ length: count }, (_, index) => `e2e,${index === 0 ? code : `${code}-${index + 1}`},${code},Cliente Ficticio Parcial,parcial@example.com,Pagamento parcial e relatorios,1.00,${demo.business_date}\n`).join("")}`;
  const headers = {
    "X-CSRF-Token": session.csrf_token,
    Origin: new URL(page.url()).origin,
  };
  const preview = await page.request.post("/api/v1/imports", {
    headers,
    multipart: {
      file: {
        name: `${code}.csv`,
        mimeType: "text/csv",
        buffer: Buffer.from(csv),
      },
    },
  });
  expect(preview.ok()).toBe(true);
  const batch = await preview.json();
  const confirmation = await page.request.post(
    `/api/v1/imports/${batch.id}/confirm`,
    { headers },
  );
  expect(confirmation.ok()).toBe(true);
  const list = await (
    await page.request.get(`/api/v1/receivables?q=${code}`)
  ).json();
  const title: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${list.items[0].id}`)
  ).json();
  return { session, title, code, headers };
}

test("entrada BRL usa centavos exatos e rejeita formatos ambíguos", () => {
  expect(parseBrl("0,01")).toBe("1");
  expect(parseBrl("00010,5")).toBe("1050");
  expect(parseBrl("90071992547409,93")).toBe("9007199254740993");
  expect(parseBrl("92233720368547758,07")).toBe("9223372036854775807");
  for (const invalid of [
    "0",
    "-1",
    "+1",
    "1.000,00",
    "1.23",
    "1e3",
    "1,001",
    "1,",
    "92233720368547758,08",
    "",
  ])
    expect(() => parseBrl(invalid)).toThrow();
});

test("resposta perdida após commit conserva intenção ao reabrir e recarregar, sem duplicar pagamento ou evento", async ({
  page,
}, info) => {
  await login(page);
  const { session, title, code } = await createTitle(page);
  await openTitle(page, code);
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("partial");
  await page.getByLabel("Valor recebido (R$)").fill("1.000,00");
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.getByLabel("Valor recebido (R$)")).toBeFocused();
  await expect(page.locator("#payment-amount-error")).toContainText(
    "Sem".toLowerCase(),
  );
  await page.getByLabel("Valor recebido (R$)").fill("0,01");
  await page
    .getByLabel("Observação (opcional)")
    .fill("Parcela fictícia de um centavo.");
  let firstPayload: unknown;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      firstPayload = route.request().postDataJSON();
      const response = await route.fetch();
      expect(response.ok()).toBe(true);
      await route.abort("failed");
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Falha na conexão");
  const storageKey = `${PAYMENT_INTENT_PREFIX}${session.user.id}:${title.id}`;
  const stored = await page.evaluate(
    (key) => sessionStorage.getItem(key),
    storageKey,
  );
  expect(stored).not.toBeNull();
  expect(JSON.parse(stored!).payload).toEqual(firstPayload);
  await page
    .getByRole("button", { name: "Fechar diálogo", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Resolver pagamento pendente", exact: true })
    .click();
  await expect(page.getByLabel("Valor recebido (R$)")).toBeDisabled();
  await expect(page.getByLabel("Observação (opcional)")).toHaveValue(
    "Parcela fictícia de um centavo.",
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Resumo", exact: true }),
  ).toBeVisible();
  await openTitle(page, code);
  await page
    .getByRole("button", { name: "Resolver pagamento pendente", exact: true })
    .click();
  let retryPayload: unknown;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      expect(route.request().postDataJSON()).toEqual(firstPayload);
      await route.fulfill({
        status: 403,
        json: {
          code: "csrf_invalid",
          message: "CSRF rejeitado antes de consultar o pagamento.",
        },
      });
    },
    { times: 1 },
  );
  await page
    .getByRole("button", {
      name: "Tentar novamente com a mesma intenção",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText("CSRF rejeitado");
  expect(
    JSON.parse(
      (await page.evaluate((key) => sessionStorage.getItem(key), storageKey))!,
    ).payload,
  ).toEqual(firstPayload);
  await expect(page.getByLabel("Valor recebido (R$)")).toBeDisabled();
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      retryPayload = route.request().postDataJSON();
      await route.continue();
    },
    { times: 1 },
  );
  await page
    .getByRole("button", {
      name: "Tentar novamente com a mesma intenção",
      exact: true,
    })
    .click();
  await expect(page.locator(".alert-success")).toContainText(
    "Pagamento registrado",
  );
  expect(retryPayload).toEqual(firstPayload);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), storageKey),
  ).toBeNull();
  const after: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${title.id}`)
  ).json();
  expect(after.payments).toHaveLength(1);
  expect(after.paid_cents).toBe("1");
  expect(after.remaining_cents).toBe("99");
  expect(
    after.events.filter((event) => event.type === "payment_recorded"),
  ).toHaveLength(1);
  await expect(page.getByText("Parcial", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Cancelar título", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("partial-payment.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("remaining");
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.getByText("Pago", { exact: true })).toBeVisible();
  const paid: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${title.id}`)
  ).json();
  expect(paid.payments).toHaveLength(2);
  expect(paid.payment).toBeNull();
  expect(paid.remaining_cents).toBe("0");
});

test("replay rejeitado após lookup resolve intenção perdida antes de permitir nova parcela", async ({
  page,
}) => {
  await login(page);
  const { session, title, code, headers } = await createTitle(page);
  await openTitle(page, code);
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("partial");
  await page.getByLabel("Valor recebido (R$)").fill("0,50");
  await page
    .getByLabel("Observação (opcional)")
    .fill("Intenção de cinquenta centavos rejeitada.");
  const other = await page.request.post(
    `/api/v1/receivables/${title.id}/payments`,
    {
      headers,
      data: {
        idempotency_key: `other-${Date.now()}`,
        amount_cents: "75",
        note: "Recebimento paralelo confirmado.",
      },
    },
  );
  expect(other.ok()).toBe(true);
  let rejectedPayload:
    { idempotency_key: string; amount_cents: string; note: string } | undefined;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      rejectedPayload = route.request().postDataJSON();
      const response = await route.fetch();
      expect(response.status()).toBe(409);
      expect((await response.json()).code).toBe("invalid_payment_amount");
      await route.abort("failed");
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Falha na conexão");
  const storageKey = `${PAYMENT_INTENT_PREFIX}${session.user.id}:${title.id}`;
  expect(
    JSON.parse(
      (await page.evaluate((key) => sessionStorage.getItem(key), storageKey))!,
    ).payload,
  ).toEqual(rejectedPayload);
  await page
    .getByRole("button", { name: "Fechar diálogo", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Resolver pagamento pendente", exact: true })
    .click();
  await expect(page.getByLabel("Valor recebido (R$)")).toBeDisabled();
  await expect(page.getByLabel("Observação (opcional)")).toBeDisabled();
  let replayPayload: unknown;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      replayPayload = route.request().postDataJSON();
      await route.continue();
    },
    { times: 1 },
  );
  await page
    .getByRole("button", {
      name: "Tentar novamente com a mesma intenção",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "intenção anterior foi rejeitada sem registrar pagamento",
  );
  expect(replayPayload).toEqual(rejectedPayload);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), storageKey),
  ).toBeNull();
  await expect(page.getByLabel("Valor recebido (R$)")).toBeEnabled();
  await expect(page.getByRole("dialog")).toContainText("Saldo atual: R$ 0,25");
  await page.getByLabel("Valor recebido (R$)").fill("0,25");
  await page
    .getByLabel("Observação (opcional)")
    .fill("Nova intenção após rejeição confirmada.");
  let acceptedPayload:
    { idempotency_key: string; amount_cents: string } | undefined;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      acceptedPayload = route.request().postDataJSON();
      await route.continue();
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.getByText("Pago", { exact: true })).toBeVisible();
  expect(acceptedPayload?.idempotency_key).not.toBe(
    rejectedPayload?.idempotency_key,
  );
  expect(acceptedPayload?.amount_cents).toBe("25");
  const after: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${title.id}`)
  ).json();
  expect(after.payments.map((payment) => payment.amount_cents)).toEqual([
    "75",
    "25",
  ]);
  expect(
    after.payments.every((payment) => payment.note !== rejectedPayload?.note),
  ).toBe(true);
  expect(
    after.events.filter((event) => event.type === "payment_recorded"),
  ).toHaveLength(2);
  expect(after.remaining_cents).toBe("0");
  const absentKey = await page.request.post(
    `/api/v1/receivables/${title.id}/payments`,
    { headers, data: rejectedPayload },
  );
  expect(absentKey.status()).toBe(409);
  expect((await absentKey.json()).code).toBe("invalid_transition");
});

test("intenção que expira com diálogo aberto exige histórico e só reenvia chave e conteúdo originais", async ({
  page,
}) => {
  await login(page);
  const { session, title, code, headers } = await createTitle(page);
  const payload = {
    idempotency_key: `expired-${Date.now()}`,
    amount_cents: "30",
    note: "Parcela confirmada com resposta local ambígua.",
  };
  expect(
    (
      await page.request.post(`/api/v1/receivables/${title.id}/payments`, {
        headers,
        data: payload,
      })
    ).ok(),
  ).toBe(true);
  const key = `${PAYMENT_INTENT_PREFIX}${session.user.id}:${title.id}`;
  await page.evaluate(
    ({ key, userId, titleId, payload, ttl }) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({
          version: 1,
          user_id: userId,
          receivable_id: titleId,
          created_at: Date.now() - ttl + 60_000,
          payload,
        }),
      ),
    {
      key,
      userId: session.user.id,
      titleId: title.id,
      payload,
      ttl: PAYMENT_INTENT_TTL_MS,
    },
  );
  await openTitle(page, code);
  await page
    .getByRole("button", { name: "Resolver pagamento pendente", exact: true })
    .click();
  const retry = page.getByRole("button", {
    name: "Tentar novamente com a mesma intenção",
    exact: true,
  });
  await expect(retry).toBeEnabled();
  let replayRequests = 0;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      replayRequests += 1;
      expect(route.request().postDataJSON()).toEqual(payload);
      await route.continue();
    },
  );
  await page.clock.setFixedTime(new Date(Date.now() + 120_000));
  await retry.click();
  await expect(retry).toBeDisabled();
  expect(replayRequests).toBe(0);
  await expect(page.getByRole("dialog")).toContainText("24 horas");
  expect(
    JSON.parse(
      (await page.evaluate((key) => sessionStorage.getItem(key), key))!,
    ).payload,
  ).toEqual(payload);
  await page
    .getByLabel("Conferi o histórico e quero reenviar a mesma intenção.")
    .check();
  await retry.click();
  await expect(page.locator(".alert-success")).toContainText(
    "Pagamento registrado",
  );
  expect(replayRequests).toBe(1);
  const after: ReceivableDetail = await (
    await page.request.get(`/api/v1/receivables/${title.id}`)
  ).json();
  expect(after.payments).toHaveLength(1);
  expect(
    after.events.filter((event) => event.type === "payment_recorded"),
  ).toHaveLength(1);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), key),
  ).toBeNull();
});

test("retorno aging, extrato e título preserva recorte e páginas de cada relatório", async ({
  page,
}) => {
  await login(page);
  const { title, code } = await createTitle(page, 21);
  await navigate(page, "Aging");
  await page.getByLabel("Cliente ou título").fill(code);
  await page.getByLabel("ID do cliente").fill(String(title.customer_id));
  await page.locator('[name="due_from"]').fill(title.due_date);
  await page.locator('[name="due_to"]').fill(title.due_date);
  await page
    .getByRole("button", { name: "Filtrar aging", exact: true })
    .click();
  await expect(page.locator(".pagination")).toContainText("21 registros");
  await page.getByRole("button", { name: "Próxima", exact: true }).click();
  await expect(page.locator(".pagination")).toContainText("Página 2");
  const rowCode = await page.locator(".row-link").first().innerText();
  await page
    .getByRole("button", {
      name: `Extrato do cliente ID ${title.customer_id}`,
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Extrato operacional", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Voltar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Aging da carteira", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue(code);
  await expect(page.getByLabel("ID do cliente")).toHaveValue(
    String(title.customer_id),
  );
  await expect(page.locator('[name="due_from"]')).toHaveValue(title.due_date);
  await expect(page.locator(".pagination")).toContainText("Página 2");
  await page.getByRole("button", { name: rowCode, exact: true }).click();
  await page
    .getByRole("button", { name: "Voltar para o aging", exact: true })
    .click();
  await expect(page.locator(".pagination")).toContainText("Página 2");
  await page
    .getByRole("button", {
      name: `Extrato do cliente ID ${title.customer_id}`,
      exact: true,
    })
    .click();
  await page.getByLabel("Título ou descrição").fill(code);
  await page
    .getByRole("combobox", { name: "Situação", exact: true })
    .selectOption("open");
  await page.locator('[name="due_from"]').fill(title.due_date);
  await page.locator('[name="due_to"]').fill(title.due_date);
  await page.locator('[name="received_from"]').fill("2000-01-01");
  await page.locator('[name="received_to"]').fill("2000-01-31");
  await page
    .getByRole("button", { name: "Filtrar extrato", exact: true })
    .click();
  await expect(
    page.getByText("Nenhum recebimento neste período", { exact: true }),
  ).toBeVisible();
  const titlePagination = page
    .locator(".customer-statement .pagination")
    .first();
  await titlePagination
    .getByRole("button", { name: "Próxima", exact: true })
    .click();
  await expect(titlePagination).toContainText("Página 2");
  await page.locator(".customer-statement .row-link").first().click();
  await page
    .getByRole("button", { name: "Voltar para o extrato", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Extrato operacional", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Título ou descrição")).toHaveValue(code);
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("open");
  await expect(page.locator('[name="received_from"]')).toHaveValue(
    "2000-01-01",
  );
  await expect(page.locator('[name="received_to"]')).toHaveValue("2000-01-31");
  await expect(titlePagination).toContainText("Página 2");
  await page.getByRole("button", { name: "Voltar", exact: true }).click();
  await expect(page.getByLabel("Cliente ou título")).toHaveValue(code);
  await expect(page.locator(".pagination")).toContainText("Página 2");
});

test("logout e troca de conta limpam intenções, reader consulta relatórios sem mutação", async ({
  page,
}) => {
  await login(page);
  const { session, title, code, headers } = await createTitle(page);
  const key = `${PAYMENT_INTENT_PREFIX}${session.user.id}:${title.id}`;
  const intention = {
    version: 1,
    user_id: session.user.id,
    receivable_id: title.id,
    created_at: Date.now(),
    payload: { idempotency_key: "local-cleanup", note: "" },
  };
  await page.evaluate(
    ({ key, intention }) =>
      sessionStorage.setItem(key, JSON.stringify(intention)),
    { key, intention },
  );
  await page
    .getByRole("button", { name: "Sair da conta", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Entrar", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), key),
  ).toBeNull();
  await login(page);
  await page.evaluate(
    ({ key, intention }) =>
      sessionStorage.setItem(key, JSON.stringify(intention)),
    { key, intention },
  );
  const active: Session = await (
    await page.request.get("/api/v1/auth/session")
  ).json();
  expect(
    (
      await page.request.post("/api/v1/auth/logout", {
        headers: { ...headers, "X-CSRF-Token": active.csrf_token },
      })
    ).ok(),
  ).toBe(true);
  await login(page, "leitor");
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), key),
  ).toBeNull();
  await openTitle(page, code);
  await expect(
    page.getByRole("button", { name: "Registrar pagamento", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Cancelar título", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Extrato do cliente", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Extrato operacional", exact: true }),
  ).toBeVisible();
  await navigate(page, "Aging");
  await expect(
    page.getByRole("heading", { name: "Aging da carteira", exact: true }),
  ).toBeVisible();
});

test("aging mantém recorte no drilldown e extrato imprime posição atual com filtros independentes", async ({
  page,
}, info) => {
  await login(page);
  const { title, code } = await createTitle(page);
  await navigate(page, "Aging");
  await page.getByLabel("Cliente ou título").fill(code);
  await page.getByLabel("ID do cliente").fill(String(title.customer_id));
  await page.locator('[name="due_from"]').fill(title.due_date);
  await page.locator('[name="due_to"]').fill(title.due_date);
  await page
    .getByRole("button", { name: "Filtrar aging", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: code, exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("aging-current.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", {
      name: "Ver títulos da faixa Em dia",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("Faixa de aging")).toHaveValue("current");
  await expect(
    page.getByRole("combobox", { name: "Situação", exact: true }),
  ).toHaveValue("");
  await expect(page.getByLabel("ID do cliente")).toHaveValue(
    String(title.customer_id),
  );
  await expect(page.getByLabel("Cliente ou título")).toHaveValue(code);
  await expect(page.locator('[name="due_from"]')).toHaveValue(title.due_date);
  await page.getByRole("button", { name: code, exact: true }).click();
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("partial");
  await page.getByLabel("Valor recebido (R$)").fill("0,30");
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.locator(".alert-success")).toContainText(
    "Pagamento registrado",
  );
  await page
    .getByRole("button", { name: "Extrato do cliente", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Extrato operacional", exact: true }),
  ).toBeVisible();
  await page.locator('[name="received_from"]').fill("2000-01-01");
  await page.locator('[name="received_to"]').fill("2000-01-31");
  await page
    .getByRole("button", { name: "Filtrar extrato", exact: true })
    .click();
  await expect(
    page.getByText("Nenhum recebimento neste período", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".statement-totals")).toContainText("R$ 0,70");
  await expect(page.locator(".statement-totals")).toContainText("R$ 0,30");
  await page.screenshot({
    path: info.outputPath("customer-statement.png"),
    fullPage: true,
  });
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".desktop-header")).toBeHidden();
  await expect(
    page.getByRole("heading", { name: "Extrato operacional", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("customer-statement-print.png"),
    fullPage: true,
  });
  await page.emulateMedia({ media: "screen" });
  await page.setViewportSize({ width: 320, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("customer-statement-mobile.png"),
    fullPage: true,
  });
});
