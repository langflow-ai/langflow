import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import {
  closeAdvancedOptions,
  disableInspectPanel,
  enableInspectPanel,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

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

    await disableInspectPanel(page);
    await page.getByText("Chat Input", { exact: true }).click();
    await openAdvancedOptions(page);
    await closeAdvancedOptions(page);

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Use Playwright's native setInputFiles() for reliable file upload
    const filePath = path.resolve(__dirname, "../../assets/chain.png");
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);

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

    await page.getByTestId("playground-btn-flow-io").last().click();

    await enableInspectPanel(page);
  },
);
