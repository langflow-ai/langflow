import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Output Modal Copy Button", () => {
  test(
    "user should be able to copy text output from component output modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
        state: "visible",
      });

      // Add a Text Input component
      await page.getByTestId("sidebar-search-input").click();
      await page.getByTestId("sidebar-search-input").fill("text input");

      await page.waitForSelector('[data-testid="input_outputText Input"]', {
        timeout: 3000,
        state: "visible",
      });

      await page
        .getByTestId("input_outputText Input")
        .hover()
        .then(async () => {
          await page.getByTestId("add-component-button-text-input").click();
        });

      await page.waitForTimeout(500);

      // Fill in some test text
      await page
        .getByTestId("textarea_str_input_value")
        .fill("Test content to copy");

      // Run the component
      await page.getByTestId("button_run_text input").click();

      await page.waitForSelector("text=built successfully", { timeout: 30000 });

      // Open the output modal
      await page.locator('[data-testid^="output-inspection-"]').first().click();

      await page.waitForSelector("text=Component Output", { timeout: 30000 });

      // Verify the copy button exists
      const copyButton = page.getByTestId("copy-output-button");
      await expect(copyButton).toBeVisible();

      // Click the copy button
      await copyButton.click();

      // Verify the success message appears
      await page.waitForSelector("text=Copied to clipboard", {
        timeout: 5000,
      });

      // Verify the check icon appears (button changes state)
      await expect(
        copyButton.locator('[data-testid="icon-Check"]'),
      ).toBeVisible();

      // Wait for the icon to revert back to copy icon
      await page.waitForTimeout(2500);
      await expect(
        copyButton.locator('[data-testid="icon-Copy"]'),
      ).toBeVisible();
    },
  );

  test(
    "copy button should work with JSON output from API Request component",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector('[data-testid="disclosure-data sources"]', {
        timeout: 3000,
        state: "visible",
      });

      await page.getByTestId("disclosure-data sources").click();

      await page
        .getByTestId("data_sourceAPI Request")
        .hover()
        .then(async () => {
          await page.getByTestId("add-component-button-api-request").click();

          await page.waitForTimeout(500);

          await page
            .getByTestId("popover-anchor-input-url_input")
            .first()
            .fill("https://httpbin.org/json");
        });

      await page.getByTestId("button_run_api request").click();

      await page.waitForSelector("text=Running", {
        timeout: 30000,
        state: "visible",
      });

      await page.waitForSelector("text=built successfully", { timeout: 30000 });

      await page
        .getByTestId("output-inspection-api response-apirequest")
        .click();

      await page.waitForSelector("text=Component Output", { timeout: 30000 });

      // Verify the copy button exists and click it
      const copyButton = page.getByTestId("copy-output-button");
      await expect(copyButton).toBeVisible();

      await copyButton.click();

      // Verify the success message appears
      await page.waitForSelector("text=Copied to clipboard", {
        timeout: 5000,
      });
    },
  );
});
