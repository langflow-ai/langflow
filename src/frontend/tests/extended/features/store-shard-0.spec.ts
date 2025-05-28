import { test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("should exists Store", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page, { skipModal: true });

  await page.getByTestId("button-store").isVisible();
  await page.getByTestId("button-store").isEnabled();
});

test("should not have an API key", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page, { skipModal: true });

  await page.getByTestId("button-store").click();

  await page.getByText("API Key Error").isVisible();
});
