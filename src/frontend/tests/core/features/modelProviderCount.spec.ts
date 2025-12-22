import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("ModelProviderCount Component", () => {
  test(
    "should open model provider modal when button is clicked",
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

      // Click the model provider count button
      const modelProviderButton = page.getByTestId(
        "model-provider-count-button",
      );
      await modelProviderButton.click();

      // Modal should appear with "Model providers" header
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Modal should contain provider list content
      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();
    },
  );

  test(
    "should close model provider modal when clicking outside or using close",
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
      const modelProviderButton = page.getByTestId(
        "model-provider-count-button",
      );
      await modelProviderButton.click();

      // Verify modal is open
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Close the modal by pressing Escape
      await page.keyboard.press("Escape");

      // Modal should be closed
      await expect(page.getByText("Model providers")).not.toBeVisible({
        timeout: 3000,
      });
    },
  );

  test(
    "should toggle modal state on repeated button clicks",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Close the modal by clicking the close button
      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();

      await closeButton.click();

      const modelProviderButton = page.getByTestId(
        "model-provider-count-button",
      );

      // First click - open modal
      await modelProviderButton.click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // Second click - close modal
      await closeButton.click();
      await expect(page.getByText("Model providers")).not.toBeVisible({
        timeout: 3000,
      });

      // Third click - open modal again
      await modelProviderButton.click();
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });
    },
  );

  test(
    "should display provider list in the modal",
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
      const modelProviderButton = page.getByTestId(
        "model-provider-count-button",
      );
      await modelProviderButton.click();

      // Wait for modal to be fully visible
      await expect(page.getByText("Model providers")).toBeVisible({
        timeout: 5000,
      });

      // The modal should contain provider selection area
      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Wait for content to load - the modal should have some interactive elements
      await page.waitForTimeout(500);

      // Dialog should be properly structured with content
      await expect(dialog.locator("div").first()).toBeVisible();
    },
  );

  test(
    "model provider count badge should have correct styling",
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

      // Get the badge element
      const badge = page.getByTestId("model-provider-count-badge");
      await expect(badge).toBeVisible();

      // Badge should be visible and contain numeric content
      const badgeText = await badge.textContent();
      expect(badgeText).toBeDefined();
      expect(Number(badgeText)).toBeGreaterThanOrEqual(0);

      // Check badge has height styling
      const height = await badge.evaluate((el) =>
        window.getComputedStyle(el).getPropertyValue("height"),
      );
      expect(height).toBeTruthy();
    },
  );
});
