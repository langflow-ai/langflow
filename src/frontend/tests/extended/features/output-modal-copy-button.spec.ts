import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

test.describe("Output Modal Copy Button", () => {
  test(
    "user should be able to copy text output from component output modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openBlankFlow(page);

      await addLegacyComponents(page);

      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
        state: "visible",
      });

      // Add a Text Input component
      await page.getByTestId("sidebar-search-input").click();
      await page
        .getByTestId("sidebar-search-input")
        .fill(TEXTS.searchTextInput);

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

      await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
        timeout: 30000,
      });

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
});
