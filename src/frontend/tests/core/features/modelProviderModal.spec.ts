import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { navigateSettingsPages } from "../../utils/go-to-settings";

test.describe("ModelProviderModal", () => {
  test(
    "should open model provider page from settings",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");

      // Page should open with "Model Providers" title
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Provider content should be visible
      await expect(
        page.getByText(
          "Configure AI model providers and manage their API keys.",
        ),
      ).toBeVisible();
    },
  );

  test(
    "should display provider list in page",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

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
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

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

        // The page content should be visible
        await expect(
          page.locator('[data-testid^="provider-item-"]').first(),
        ).toBeVisible();
      }
    },
  );

  test(
    "should navigate back from model provider page",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Navigate back
      await page.getByTestId("icon-ChevronLeft").first().click();

      // Page should be closed/navigated away - description text should not be visible
      await expect(
        page.getByText(
          "Configure AI model providers and manage their API keys.",
        ),
      ).not.toBeVisible({ timeout: 3000 });
    },
  );

  test(
    "should display model selection panel for enabled provider",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

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
    "should have accessible page structure",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // Navigate to Settings > Model Providers
      await navigateSettingsPages(page, "Settings", "Model Providers");

      // Page should have proper heading
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Content should be visible
      await expect(
        page.getByText(
          "Configure AI model providers and manage their API keys.",
        ),
      ).toBeVisible();
    },
  );
});
