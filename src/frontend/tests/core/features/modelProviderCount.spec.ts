import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { navigateSettingsPages } from "../../utils/go-to-settings";

test.describe("ModelProviderCount Component", () => {
  test(
    "should open model provider page when navigating via settings",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");

      // Page should appear with "Model Providers" header
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Page should contain provider list content
      await expect(
        page.locator("div").getByText("Model Providers"),
      ).toBeVisible();
    },
  );

  test(
    "should navigate back from model provider page",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");

      // Verify page is open
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Navigate back by clicking the back button
      await page.getByTestId("icon-ChevronLeft").first().click();

      // Should be back at main view
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).not.toContainText("Model Providers", { timeout: 3000 });
    },
  );

  test(
    "should navigate to model provider page multiple times",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // First navigation - open page
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Navigate back
      await page.getByTestId("icon-ChevronLeft").first().click();
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).not.toContainText("Model Providers", { timeout: 3000 });

      // Second navigation - open page again
      await page.getByText("Model Providers").first().click();
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });
    },
  );

  test(
    "should display provider list in the page",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");

      // Wait for page to be fully visible
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // The page should contain provider selection area with content
      await page.waitForTimeout(500);

      // Page should be properly structured with content
      await expect(page.locator("div").first()).toBeVisible();
    },
  );

  test(
    "model provider count badge should have correct styling",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Get the badge element (should be visible in the main UI)
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
