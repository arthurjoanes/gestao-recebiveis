import { expect, test } from "@playwright/test";
import { portfolioShare } from "../src/lib/portfolio-share";

test("participação do saldo preserva centavos grandes e arredonda duas casas", () => {
  expect(portfolioShare("1", "3")).toBe(33.33);
  expect(portfolioShare("2", "3")).toBe(66.67);
  expect(portfolioShare("9007199254740993", "18014398509481986")).toBe(50);
  expect(portfolioShare("0", "0")).toBe(0);
  expect(portfolioShare("0", "100")).toBe(0);
  expect(portfolioShare("100", "100")).toBe(100);
});
