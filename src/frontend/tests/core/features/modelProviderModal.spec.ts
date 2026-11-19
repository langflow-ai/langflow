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
      await expect(providerList).toBeVisible({ timeout: 3000 });
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

      // Click the first provider
      const providerItem = page
        .locator('[data-testid^="provider-item-"]')
        .first();
      await expect(providerItem).toBeVisible({ timeout: 2000 });
      await providerItem.click();

      // The provider becomes the selected one
      await expect(providerItem).toHaveAttribute("aria-pressed", "true");
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

      // Click the first provider
      await page.locator('[data-testid^="provider-item-"]').first().click();

      // The model selection section appears
      await expect(page.getByTestId("model-provider-selection")).toBeVisible({
        timeout: 2000,
      });
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

  test(
    "should navigate to model provider page multiple times",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      // Wait for page to be ready
      await page.waitForTimeout(1000);

      // First navigation - open page
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Navigate back
      await page.getByTestId("icon-ChevronLeft").first().click();
      await expect(
        page.getByText(
          "Configure AI model providers and manage their API keys.",
        ),
      ).not.toBeVisible({ timeout: 3000 });

      // Second navigation - open page again
      await navigateSettingsPages(page, "Settings", "Model Providers");
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });
    },
  );
});
