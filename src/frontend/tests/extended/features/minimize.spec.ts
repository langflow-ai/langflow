import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to minimize and expand a component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector("data-testid=inputsText Input", {
      timeout: 3000,
    });

    await page
      .getByTestId("inputsText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.getByTestId("zoom_out").click();
    await page
      .locator('//*[@id="react-flow-id"]')
      .hover()
      .then(async () => {
        await page.mouse.down();
        await page.mouse.move(-800, 300);
      });

    await page.mouse.up();

    await adjustScreenView(page);

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector("data-testid=minimize-button-modal", {
      timeout: 3000,
    });

    await page.getByTestId("minimize-button-modal").first().click();

    await expect(
      page.locator(".react-flow__handle-left.no-show").first(),
    ).toBeVisible({ timeout: 3000 });

    await expect(
      page.locator(".react-flow__handle-right.no-show").first(),
    ).toBeVisible();

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector("data-testid=expand-button-modal", {
      timeout: 3000,
    });

    await page.getByTestId("expand-button-modal").first().click();

    await expect(page.locator(".react-flow__handle-left").first()).toBeVisible({
      timeout: 3000,
    });

    await expect(
      page.locator(".react-flow__handle-right").first(),
    ).toBeVisible();
  },
);
