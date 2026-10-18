import { expect, test } from "@playwright/test";

test("gráfico de atraso acompanha o filtro de vencimento e a carteira vazia", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("E-mail", { exact: true }).fill("leitor@example.com");
  await page.getByLabel("Senha", { exact: true }).fill("Recebiveis!2026");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  const chart = page.getByRole("region", {
    name: "Distribuição do saldo por atraso",
  });
  await expect(
    chart.getByRole("heading", { name: "Saldo por atraso" }),
  ).toBeVisible();
  await expect(chart.locator("li")).toHaveCount(5);
  const baseline = await chart.locator(".aging-bar-value").allTextContents();
  await page.locator(".overview-filter-panel summary").click();
  await page.locator('input[name="due_from"]').fill("2099-01-01");
  await page.locator('input[name="due_to"]').fill("2099-01-31");
  await page
    .getByRole("button", { name: "Aplicar filtros", exact: true })
    .click();
  await expect(chart).toContainText("Nenhum saldo em aberto neste período.");
  await expect(chart.locator("li")).toHaveCount(0);
  await page.locator(".overview-filter-panel summary").click();
  await page
    .getByRole("button", { name: "Limpar filtros", exact: true })
    .click();
  await expect(chart.locator(".aging-bar-value")).toHaveText(baseline);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(chart.getByRole("heading")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await chart
      .locator(".aging-bar")
      .first()
      .evaluate((element) => getComputedStyle(element).transitionDuration),
  ).toBe("0s");
});
