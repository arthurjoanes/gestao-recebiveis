// Captura somente leitura; use NODE_PATH para localizar o Playwright instalado.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium, expect } = require("@playwright/test");

(async () => {
  const output = process.env.DOCS_SCREENSHOT_DIR;
  if (!output) throw new Error("Defina DOCS_SCREENSHOT_DIR em uma pasta nova.");
  fs.mkdirSync(output, { recursive: true });
  if (fs.readdirSync(output).length)
    throw new Error("A pasta de captura deve estar vazia.");
  const browser = await chromium.launch({ headless: true });
  const report = {
    captured_at: new Date().toISOString(),
    source_commit: process.env.SOURCE_COMMIT || null,
    application: process.env.BASE_URL || "http://localhost:3101",
    browser_version: browser.version(),
    capture_method:
      "Capturas nativas de componentes; sem fullPage ou edição de pixels.",
    scope:
      "Aplicação real; operador demo; somente navegação e consultas; carteira preservada.",
    images: [],
    page_errors: [],
  };
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
      locale: "pt-BR",
      timezoneId: "America/Sao_Paulo",
      reducedMotion: "reduce",
    });
    page.on("pageerror", (error) => report.page_errors.push(error.message));
    const focus = {
      "resumo.png": ".metrics",
      "carteira.png": ".portfolio-panel",
      "titulo.png": ".detail-summary",
      "importacoes.png": ".upload-panel",
      "lembretes.png": ".reminder-list",
      "resumo-mobile.png": ".balance-position",
    };
    const capture = async (name) => {
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator(".loading")).toHaveCount(0);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      expect(overflow, `${name}: sem overflow horizontal global`).toBe(false);
      const target = path.join(output, name);
      const region = page.locator(focus[name]);
      const bounds = await region.boundingBox();
      expect(bounds).not.toBeNull();
      if (page.viewportSize().width < 600)
        expect(bounds.height).toBeLessThanOrEqual(650);
      else expect(bounds.height / bounds.width).toBeLessThanOrEqual(1.1);
      await region.screenshot({
        path: target,
        animations: "disabled",
      });
      report.images.push({
        path: name,
        focus: focus[name],
        dimensions: {
          width: fs.readFileSync(target).readUInt32BE(16),
          height: fs.readFileSync(target).readUInt32BE(20),
        },
        dimension_source: "PNG IHDR",
        viewport: page.viewportSize(),
        sha256: crypto
          .createHash("sha256")
          .update(fs.readFileSync(target))
          .digest("hex"),
        overflow: false,
      });
    };
    const navigate = async (name) => {
      const menu = page.getByRole("button", { name: "Menu", exact: true });
      if (await menu.isVisible()) await menu.click();
      await page
        .getByRole("navigation", { name: "Navegação principal" })
        .getByRole("button", { name, exact: true })
        .click();
      await expect(
        page.getByRole("heading", { name, exact: true }).first(),
      ).toBeVisible();
    };
    await page.goto(report.application);
    await page
      .getByLabel("E-mail", { exact: true })
      .fill("operador@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("Recebiveis!2026");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(
      page.getByRole("heading", { name: "Resumo", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".metric > strong").first()).toBeVisible();
    await capture("resumo.png");
    await navigate("Títulos");
    await expect(
      page.getByRole("button", { name: "TIT-0001", exact: true }),
    ).toBeVisible();
    await capture("carteira.png");
    await page.getByRole("button", { name: "TIT-0001", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "TIT-0001", exact: true }),
    ).toBeVisible();
    await capture("titulo.png");
    await navigate("Importações");
    await capture("importacoes.png");
    await navigate("Lembretes");
    await capture("lembretes.png");
    await navigate("Resumo");
    await page.setViewportSize({ width: 390, height: 844 });
    await capture("resumo-mobile.png");
    expect(report.page_errors).toEqual([]);
    fs.writeFileSync(
      path.join(output, "capture.json"),
      JSON.stringify(report, null, 2) + "\n",
    );
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
