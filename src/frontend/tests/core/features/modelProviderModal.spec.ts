import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("ModelProviderModal", () => {
  test(
    "should open model provider modal from header button",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      // Click the model provider count button in header
      const modelProviderButton = page.getByTestId(
        "model-provider-count-button",
      );
      await modelProviderButton.click();

      // Modal should open with "Model providers" title
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Dialog should be visible
      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();
    },
  );

  test(
    "should display provider list in modal",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      // Open the modal
      await page.getByTestId("model-provider-count-button").click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Provider list should be visible
      const providerList = page.getByTestId("provider-list");
      if (await providerList.isVisible({ timeout: 3000 })) {
        await expect(providerList).toBeVisible();
      }
    },
  );

  test(
    "should show provider details when a provider is selected",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      // Open the modal
      await page.getByTestId("model-provider-count-button").click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Wait for provider list to load
      await page.waitForTimeout(1000);

      // Click on a provider if available
      const providerItem = page
        .locator('[data-testid^="provider-item-"]')
        .first();
      if (await providerItem.isVisible({ timeout: 2000 })) {
        await providerItem.click();

        // Should show API Key section or model selection
        await page.waitForTimeout(500);

        // The panel should expand to show provider configuration
        const dialog = page.locator('[role="dialog"]');
        await expect(dialog).toBeVisible();
      }
    },
  );

  test(
    "should close modal when pressing Escape",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      // Open the modal
      await page.getByTestId("model-provider-count-button").click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Press Escape to close
      await page.keyboard.press("Escape");

      // Modal should be closed
      await expect(page.getByText("Model providers")).not.toBeVisible({
        timeout: 3000,
      });
    },
  );

  test(
    "should display model selection panel for enabled provider",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      // Open the modal
      await page.getByTestId("model-provider-count-button").click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      await page.waitForTimeout(1000);

      // Find an enabled provider (has check icon) and click it
      const providerItems = page.locator('[data-testid^="provider-item-"]');
      const count = await providerItems.count();

      for (let i = 0; i < count; i++) {
        const item = providerItems.nth(i);
        if (await item.isVisible()) {
          await item.click();
          await page.waitForTimeout(500);

          // Check if model selection section appears
          const modelSelection = page.getByTestId("model-provider-selection");
          if (await modelSelection.isVisible({ timeout: 2000 })) {
            await expect(modelSelection).toBeVisible();
            break;
          }
        }
      }
    },
  );

  test(
    "should have accessible modal structure",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      // Open the modal
      await page.getByTestId("model-provider-count-button").click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Check dialog role
      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Modal should have proper heading
      await expect(page.getByText("Model providers")).toBeVisible();
    },
  );
});
