import { test } from "@playwright/test";

test("should exists Store", { tag: ["@release"] }, async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").isVisible();
  await page.getByTestId("button-store").isEnabled();
});

test("should not have an API key", { tag: ["@release"] }, async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("API Key Error").isVisible();
});
