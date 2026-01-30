import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "user should not be able to upload a file larger than the limit",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    const maxFileSizeUpload = 0.001;
    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          max_file_size_upload: maxFileSizeUpload,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await initialGPTsetup(page);

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await page.getByText("Chat Input", { exact: true }).click();
    await page.getByTestId("edit-button-modal").last().click();
    await page.getByText("Close").last().click();

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Read the image file path
    const filePath = path.resolve(__dirname, "../../assets/chain.png");

    // Locate the file input element (it might be hidden)
    const fileInput = page.locator('input[type="file"]').first();
    
    // Set the file on the input
    await fileInput.setInputFiles(filePath);

    // Wait for the error message to appear
    await page.waitForSelector("text=The file size is too large", {
      timeout: 10000,
    });

    await expect(
      page.getByText(
        `The file size is too large. Please select a file smaller than ${(
          maxFileSizeUpload * 1024
        ).toFixed(2)} KB`,
      ),
    ).toBeVisible();
  },
);
