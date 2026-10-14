import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { AxeResults, RunOptions } from "axe-core";

const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

test("texto ampliado por CSS mantém navegação e números operáveis", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Usar operador", exact: true })
    .click();
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.locator(".metric-open strong")).toBeVisible();
  // This is text enlargement in the page, not native browser zoom.
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => {
      function enlarge(rules: CSSRuleList) {
        for (const rule of rules) {
          if (rule instanceof CSSStyleRule && rule.style.fontSize) {
            rule.style.setProperty(
              "font-size",
              `calc(${rule.style.fontSize} * 2)`,
              "important",
            );
          } else if (rule instanceof CSSImportRule && rule.styleSheet) {
            enlarge(rule.styleSheet.cssRules);
          }
          if (rule instanceof CSSGroupingRule) enlarge(rule.cssRules);
        }
      }
      for (const sheet of document.styleSheets) enlarge(sheet.cssRules);
    });
    expect(
      await page
        .locator("body")
        .evaluate((element) => getComputedStyle(element).fontSize),
    ).toBe("30px");
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
    const open = page.locator(".metric-open strong");
    await expect(open).toContainText("R$");
    if (
      await page.getByRole("button", { name: "Menu", exact: true }).isVisible()
    )
      await page.getByRole("button", { name: "Menu", exact: true }).click();
    await page
      .getByRole("navigation", { name: "Navegação principal" })
      .getByRole("link", { name: "Aging", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Carteira no recorte", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Aging da carteira", exact: true }),
    ).toBeVisible();
    await page.goto("/?area=overview");
    await expect(page.locator(".metric-open strong")).toBeVisible();
  }
});

test("relatórios e confirmação permanecem acessíveis nas cinco larguras", async ({
  page,
}) => {
  const scans: unknown[] = [];
  await page.goto("/");
  await page
    .getByRole("button", { name: "Usar operador", exact: true })
    .click();
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.locator(".metric-open strong")).toBeVisible();
  async function navigate(name: string) {
    if (
      await page.getByRole("button", { name: "Menu", exact: true }).isVisible()
    )
      await page.getByRole("button", { name: "Menu", exact: true }).click();
    await page
      .getByRole("navigation", { name: "Navegação principal" })
      .getByRole("link", { name, exact: true })
      .click();
  }
  async function scan(name: string, width: number) {
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(width);
    await page.evaluate(axeSource);
    const result = await page.evaluate(async () => {
      const runtime = window as typeof window & {
        axe: {
          run: (context: Document, options: RunOptions) => Promise<AxeResults>;
        };
      };
      const value = await runtime.axe.run(document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"],
        },
      });
      return {
        violations: value.violations,
        incomplete: value.incomplete.map(({ id, nodes }) => ({
          id,
          targets: nodes.map((node) => node.target),
        })),
        passes: value.passes.length,
      };
    });
    scans.push({ name, width, ...result });
    expect(result.violations, `${name}, ${width}px`).toEqual([]);
  }
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await navigate("Resumo");
    await expect(page.locator(".metric-open strong")).toBeVisible();
    await scan("resumo", width);
    await navigate("Títulos");
    if (
      !(await page.getByLabel("Cliente ou título", { exact: true }).isVisible())
    )
      await page
        .getByRole("button", { name: "Filtrar carteira", exact: true })
        .click();
    if (width <= 1100) {
      await page
        .getByLabel("Cliente ou título", { exact: true })
        .fill("TIT-000");
      await page
        .getByRole("button", { name: "Filtrar títulos", exact: true })
        .click();
      await expect(
        page.getByRole("link", { name: "TIT-0009", exact: true }),
      ).toBeAttached();
      const list = page.locator(".portfolio-results .table-scroll");
      const lastAmount = page
        .locator(".portfolio-results tbody tr")
        .last()
        .locator("td.numeric");
      const boundary = await list.boundingBox();
      const amountBox = await lastAmount.boundingBox();
      expect(boundary).not.toBeNull();
      expect(amountBox).not.toBeNull();
      expect(amountBox!.y + amountBox!.height).toBeLessThanOrEqual(
        boundary!.y + boundary!.height + 1,
      );
    }
    if (
      !(await page.getByLabel("Cliente ou título", { exact: true }).isVisible())
    )
      await page
        .getByRole("button", { name: "Filtrar carteira", exact: true })
        .click();
    await page
      .getByLabel("Cliente ou título", { exact: true })
      .fill("TIT-0001");
    await page
      .getByRole("button", { name: "Filtrar títulos", exact: true })
      .click();
    const row = page.getByRole("row").filter({ hasText: "TIT-0001" });
    await expect(row).toBeVisible();
    const amounts = row.locator("td.numeric");
    expect(
      await amounts.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= innerWidth;
      }),
    ).toBe(true);
    await page.getByRole("link", { name: "TIT-0001", exact: true }).click();
    await page
      .getByRole("button", { name: "Registrar pagamento", exact: true })
      .click();
    await expect(
      page.getByRole("region", { name: "Conferência do pagamento" }),
    ).toBeVisible();
    await scan("confirmação", width);
    await page
      .getByRole("button", { name: "Fechar diálogo", exact: true })
      .click();
    await page
      .getByRole("link", { name: "Extrato do cliente", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Totais de todo o recorte" }),
    ).toBeVisible();
    await scan("extrato", width);
    await navigate("Aging");
    await expect(
      page.getByRole("heading", { name: "Carteira no recorte" }),
    ).toBeVisible();
    await scan("aging", width);
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page
      .getByRole("button", { name: "Atualizar", exact: true })
      .evaluate((element) => getComputedStyle(element).transitionDuration),
  ).toBe("0s");
  await test.info().attach("accessibility.json", {
    body: JSON.stringify(scans, null, 2),
    contentType: "application/json",
  });
});

test("Firefox percorre consulta, título e extrato com perfil leitor", async ({
  playwright,
  baseURL,
}) => {
  const browser = await playwright.firefox.launch({ channel: undefined });
  try {
    const page = await browser.newPage({
      baseURL,
      viewport: { width: 390, height: 900 },
      locale: "pt-BR",
      timezoneId: "America/Sao_Paulo",
    });
    await page.goto("/");
    await page
      .getByRole("button", { name: "Usar leitor", exact: true })
      .click();
    await page.getByRole("button", { name: "Entrar", exact: true }).click();
    await expect(page.locator(".metric-open strong")).toBeVisible();
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    await page
      .getByRole("navigation", { name: "Navegação principal" })
      .getByRole("link", { name: "Aging", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Títulos do aging" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "TIT-0001", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Registrar pagamento", exact: true }),
    ).toHaveCount(0);
    await page
      .getByRole("link", { name: "Extrato do cliente", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Totais de todo o recorte" }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await test.info().attach("firefox-extrato.png", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });
  } finally {
    await browser.close();
  }
});
