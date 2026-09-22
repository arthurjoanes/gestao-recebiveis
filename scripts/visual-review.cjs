const fs = require("node:fs");
const { chromium } = require("/app/node_modules/playwright");

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto("http://localhost:3101");
    await page.getByLabel("E-mail", { exact: true }).fill("leitor@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("Recebiveis!2026");
    await page.getByRole("button", { name: "Entrar" }).click();
    await page.getByRole("heading", { name: "Resumo", exact: true }).waitFor();
    await page.locator(".metric > strong").first().waitFor();
    const observations = [];
    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 1366, height: 768 },
      { width: 768, height: 1024 },
      { width: 390, height: 844 },
      { width: 320, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      const result = await page.evaluate(() => ({
        viewport: { width: innerWidth, height: innerHeight },
        documentWidth: document.documentElement.scrollWidth,
        sectionLabels: [
          ...document.querySelectorAll(".page-heading h1, .metric-label"),
        ]
          .filter((element) => element.getClientRects().length > 0)
          .map((element) => ({
            text: element.textContent.trim(),
            fontSize: parseFloat(getComputedStyle(element).fontSize),
          })),
        firstAmountY: document
          .querySelector(".metric > strong")
          .getBoundingClientRect().y,
      }));
      if (
        result.documentWidth > viewport.width ||
        result.firstAmountY >= 480 ||
        result.sectionLabels.length === 0 ||
        result.sectionLabels.some((label) => label.fontSize < 12)
      ) {
        throw new Error(JSON.stringify(result));
      }
      observations.push(result);
      if (process.env.SCREENSHOT_DIR) {
        const names = {
          1440: "overview.png",
          1366: "overview-1366.png",
          768: "overview-tablet.png",
          390: "mobile.png",
          320: "overview-320.png",
        };
        await page.screenshot({
          path: `${process.env.SCREENSHOT_DIR}/${names[viewport.width]}`,
          fullPage: true,
        });
      }
    }
    const evidence = {
      observedAt: new Date().toISOString(),
      application: "http://localhost:3101",
      composeProject: process.env.COMPOSE_PROJECT_NAME || null,
      scope:
        "Read-only reflow check after demo-reader login; separate from the Playwright suite.",
      result: "passed",
      observations,
    };
    fs.writeFileSync(
      "/evidence/reflow.json",
      JSON.stringify(evidence, null, 2) + "\n",
    );
    console.log(JSON.stringify(evidence, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
