import { expect, test, type Page } from "@playwright/test";
import { PAYMENT_INTENT_PREFIX } from "../src/lib/payment-intent";
import type { ReceivableDetail, Session } from "../src/lib/types";

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill("operador@example.com");
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
    .getByRole("link", { name, exact: true })
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
  await page.getByRole("link", { name: code, exact: true }).click();
  await expect(
    page.getByRole("heading", { name: code, exact: true }),
  ).toBeVisible();
}
async function fixture(page: Page, amount = "1.00", count = 1) {
  const session: Session = await (
    await page.request.get("/api/v1/auth/session")
  ).json();
  const demo = await (await page.request.get("/api/v1/demo")).json();
  const code = `UIUX-${Date.now()}`;
  const headers = {
    "X-CSRF-Token": session.csrf_token,
    Origin: new URL(page.url()).origin,
  };
  const csv = `source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\n${Array.from({ length: count }, (_, index) => `e2e,${index === 0 ? code : `${code}-${index + 1}`},${code},Distribuidora Fictícia de Materiais para Comércio e Serviços com Nome Extenso,uiux@example.com,Conferência exata de recebimento e saldo,${amount},${demo.business_date}\n`).join("")}`;
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
  expect(
    (
      await page.request.post(`/api/v1/imports/${batch.id}/confirm`, {
        headers,
      })
    ).ok(),
  ).toBe(true);
  const list = await (
    await page.request.get(`/api/v2/receivables?q=${code}`)
  ).json();
  const title: ReceivableDetail = await (
    await page.request.get(`/api/v2/receivables/${list.items[0].id}`)
  ).json();
  return { code, session, headers, title };
}

test("confirmação conserva centavos grandes, corrige erro e quitação perdida repete o valor exibido", async ({
  page,
}, info) => {
  await login(page);
  const { code, title, session } = await fixture(page, "90071992547409.93");
  await openTitle(page, code);
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("partial");
  const amount = page.getByLabel("Valor recebido (R$)");
  await amount.fill("1.23");
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(amount).toBeFocused();
  await expect(amount).toHaveAttribute("aria-invalid", "true");
  await amount.fill("0,01");
  await expect(amount).toHaveAttribute("aria-invalid", "false");
  await expect(page.locator("#payment-amount-error")).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Conferência do pagamento", exact: true }),
  ).toContainText("R$ 0,01");
  await expect(page.locator(".payment-preview")).toContainText(
    "R$ 90.071.992.547.409,92",
  );
  await page.getByLabel("Observação (opcional)").fill("Parcela de um centavo.");
  await page.screenshot({
    path: info.outputPath("payment-confirmation-partial.png"),
    fullPage: false,
  });
  await page
    .getByRole("button", { name: "Confirmar pagamento", exact: true })
    .click();
  await expect(page.locator(".alert-success")).toContainText(
    "Pagamento registrado: R$ 0,01",
  );
  await expect(page.locator(".detail-amount")).toHaveText(
    "R$ 90.071.992.547.409,92",
  );
  await page
    .getByRole("button", { name: "Registrar pagamento", exact: true })
    .click();
  await page.getByLabel("Tipo de recebimento").selectOption("remaining");
  await expect(page.locator(".payment-preview")).toContainText(
    "R$ 90.071.992.547.409,92",
  );
  await expect(page.locator(".payment-preview")).toContainText("R$ 0,00");
  let frozen: Record<string, string> | undefined;
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      frozen = route.request().postDataJSON();
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
  expect(frozen?.amount_cents).toBe("9007199254740992");
  const key = `${PAYMENT_INTENT_PREFIX}${session.user.id}:${title.id}`;
  const stored = JSON.parse(
    (await page.evaluate((key) => sessionStorage.getItem(key), key))!,
  );
  expect(stored.preview.remaining_after_cents).toBe("0");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: code, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".detail-amount")).toHaveText("R$ 0,00");
  await page
    .getByRole("button", { name: "Resolver pagamento pendente", exact: true })
    .click();
  await expect(page.locator(".pending-intent-preview")).toContainText(
    "R$ 90.071.992.547.409,92",
  );
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      expect(route.request().postDataJSON()).toEqual(frozen);
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
    "Pagamento registrado: R$ 90.071.992.547.409,92",
  );
  const after: ReceivableDetail = await (
    await page.request.get(`/api/v2/receivables/${title.id}`)
  ).json();
  expect(after.payments).toHaveLength(2);
  expect(
    after.events.filter((event) => event.type === "payment_recorded"),
  ).toHaveLength(2);
  expect(after.remaining_cents).toBe("0");
});

test("replay legado sem valor não inventa quantia a partir do saldo atual", async ({
  page,
}) => {
  await login(page);
  const { code, title, session, headers } = await fixture(page);
  const payload = {
    idempotency_key: `legacy-ui-${Date.now()}`,
    note: "Quitação da interface anterior.",
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
    ({ key, payload, userId, titleId }) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({
          version: 1,
          user_id: userId,
          receivable_id: titleId,
          created_at: Date.now(),
          payload,
        }),
      ),
    { key, payload, userId: session.user.id, titleId: title.id },
  );
  await openTitle(page, code);
  await page
    .getByRole("button", { name: "Resolver pagamento pendente", exact: true })
    .click();
  await expect(page.locator(".pending-intent-preview")).toContainText(
    "Quitação solicitada sem valor explícito",
  );
  await expect(page.locator(".pending-intent-preview")).not.toContainText(
    "R$ 0,00",
  );
  await page.route(
    `**/api/v1/receivables/${title.id}/payments`,
    async (route) => {
      expect(route.request().postDataJSON()).toEqual(payload);
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
    "Pagamento registrado: R$ 1,00",
  );
  expect(
    (await (await page.request.get(`/api/v2/receivables/${title.id}`)).json())
      .payments,
  ).toHaveLength(1);
});

test("extrato distingue datas inválidas, estado traduzido e paginações por seção", async ({
  page,
}, info) => {
  await login(page);
  const { code } = await fixture(page);
  await openTitle(page, code);
  await page
    .getByRole("link", { name: "Extrato do cliente", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Situação", exact: true })
    .selectOption("open");
  await page
    .getByRole("button", { name: "Filtrar extrato", exact: true })
    .click();
  await expect(page.locator(".report-scope")).toContainText("Em aberto");
  await expect(page.locator(".report-scope")).not.toContainText("open");
  await page.getByLabel("Recebimento de", { exact: true }).fill("2026-08-18");
  await page
    .getByLabel("Até (recebimento)", { exact: true })
    .fill("2026-08-17");
  await page
    .getByRole("button", { name: "Filtrar extrato", exact: true })
    .click();
  await expect(
    page.getByLabel("Recebimento de", { exact: true }),
  ).toBeFocused();
  await expect(
    page.getByLabel("Recebimento de", { exact: true }),
  ).toHaveAttribute("aria-invalid", "true");
  await expect(
    page.getByLabel("Vencimento de", { exact: true }),
  ).toHaveAttribute("aria-invalid", "false");
  await expect(
    page.getByLabel("Até (vencimento)", { exact: true }),
  ).toHaveAttribute("aria-invalid", "false");
  await expect(
    page.getByRole("navigation", {
      name: "Paginação dos títulos do cliente",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", {
      name: "Paginação dos recebimentos do cliente",
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("statement-received-field-error.png"),
    fullPage: true,
  });
});

test("retorno de relatório restaura foco da linha e resposta atrasada respeita digitação", async ({
  page,
}) => {
  await login(page);
  const { code, title } = await fixture(page, "1.00", 21);
  await navigate(page, "Aging");
  await page.getByLabel("Cliente ou título").fill(code);
  await page.getByLabel("ID do cliente").fill(String(title.customer_id));
  await page
    .getByRole("button", { name: "Filtrar aging", exact: true })
    .click();
  const pagination = page.getByRole("navigation", {
    name: "Paginação dos títulos do aging",
    exact: true,
  });
  await expect(pagination).toContainText("21 registros");
  await pagination
    .getByRole("button", { name: "Próxima", exact: true })
    .click();
  await expect(pagination).toContainText("Página 2");
  const row = page.locator(".row-link").first();
  const rowCode = await row.innerText();
  await row.click();
  await page
    .getByRole("button", { name: "Voltar para o aging", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: rowCode, exact: true }),
  ).toBeFocused();
  await page.getByRole("link", { name: rowCode, exact: true }).click();
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/api/v2/reports/aging?**",
    async (route) => {
      await held;
      await route.continue();
    },
    { times: 1 },
  );
  try {
    await page
      .getByRole("button", { name: "Voltar para o aging", exact: true })
      .click();
    await page.getByLabel("Cliente ou título").fill(code);
  } finally {
    release();
  }
  await expect(pagination).toContainText("Página 2");
  await expect(page.getByLabel("Cliente ou título")).toBeFocused();
});
