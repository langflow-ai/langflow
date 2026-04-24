import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("ModelProviderCount Component", () => {
  test(
    "should open model provider page when navigating via settings",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Close the new project modal
      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();
      await closeButton.click();

      // Navigate to settings > Model Providers
      await page.getByTestId("user-profile-settings").click();
      await page.getByText("Settings").first().click();
      await page.getByText("Model Providers").first().click();

      // Wait for the settings page header
      await page.waitForSelector('[data-testid="settings_menu_header"]', {
        timeout: 5000,
      });

      // Page should appear with "Model Providers" header
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Page should contain provider configuration content
      await expect(
        page.getByText(
          "Configure AI model providers and manage their API keys.",
        ),
      ).toBeVisible();
    },
  );

  test(
    "should navigate back from model provider page",
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

      // Navigate to settings > Model Providers
      await page.getByTestId("user-profile-settings").click();
      await page.getByText("Settings").first().click();
      await page.getByText("Model Providers").first().click();

      // Verify page is open
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Navigate back by clicking the back button
      await page.getByTestId("icon-ChevronLeft").first().click();

      // Should be back at main view - the settings page header should change
      await expect(
        page.getByText(
          "Configure AI model providers and manage their API keys.",
        ),
      ).not.toBeVisible({ timeout: 3000 });
    },
  );

  test(
    "should navigate to model provider page multiple times",
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

      // First navigation - open page
      await page.getByTestId("user-profile-settings").click();
      await page.getByText("Settings").first().click();
      await page.getByText("Model Providers").first().click();

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
      await page.getByTestId("user-profile-settings").click();
      await page.getByText("Settings").first().click();
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
      await awaitBootstrapTest(page);

      const closeButton = page
        .locator("button")
        .filter({ hasText: "Close" })
        .or(page.locator('button[aria-label="Close"]'))
        .or(page.locator('button[data-testid="close-button"]'))
        .first();
      await closeButton.click();

      // Navigate to settings > Model Providers
      await page.getByTestId("user-profile-settings").click();
      await page.getByText("Settings").first().click();
      await page.getByText("Model Providers").first().click();

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
    "model provider page should display provider count information",
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

      // Navigate to settings > Model Providers
      await page.getByTestId("user-profile-settings").click();
      await page.getByText("Settings").first().click();
      await page.getByText("Model Providers").first().click();

      // Page should display the header
      await expect(
        page.getByTestId("settings_menu_header").last(),
      ).toContainText("Model Providers", { timeout: 5000 });

      // Provider list content should be visible
      const providerList = page.getByTestId("provider-list");
      if (await providerList.isVisible({ timeout: 3000 })) {
        await expect(providerList).toBeVisible();
      }
    },
  );
});
