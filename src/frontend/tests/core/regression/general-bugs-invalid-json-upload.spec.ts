import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Invalid JSON Upload Error Handling", () => {
  // Helper function to verify the upload error alert appears
  async function verifyErrorAppears(page: Page) {
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: /error.*upload/i })
        .first(),
    ).toBeVisible({ timeout: 10000 });
  }

  test(
    "should show error popup when uploading invalid JSON via upload button",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Navigate to main page
      await page.goto("/");
      await page.waitForSelector('[data-testid="mainpage_title"]', {
        timeout: 30000,
      });

      // Create an invalid JSON file content
      const invalidJsonContent = '{"invalid": }';

      // Wait for the upload button in the sidebar
      await page.waitForSelector('[data-testid="upload-project-button"]', {
        timeout: 10000,
      });

      // Set up file chooser handler before clicking
      const fileChooserPromise = page.waitForEvent("filechooser", {
        timeout: 10000,
      });

      // Click the upload button
      await page.getByTestId("upload-project-button").last().click();

      // Handle the file chooser
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles({
        name: "invalid-flow.json",
        mimeType: "application/json",
        buffer: Buffer.from(invalidJsonContent),
      });

      // Verify error appears
      await verifyErrorAppears(page);
    },
  );

  test(
    "should show error popup when uploading invalid JSON via drag and drop",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Navigate to main page
      await page.goto("/");
      await page.waitForSelector('[data-testid="mainpage_title"]', {
        timeout: 30000,
      });

      // Create invalid JSON file content
      const invalidJsonContent = '{"invalid": json content}';

      const dataTransfer = await page.evaluateHandle((data) => {
        const dt = new DataTransfer();
        const file = new File([data], "invalid-flow.json", {
          type: "application/json",
        });
        dt.items.add(file);
        return dt;
      }, invalidJsonContent);

      await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
        dataTransfer,
      });
      await verifyErrorAppears(page);
    },
  );
});
