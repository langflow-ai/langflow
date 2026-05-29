import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
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
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await initialGPTsetup(page);

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await disableInspectPanel(page);
    await page.getByText(TEXTS.componentChatInput, { exact: true }).click();
    await openAdvancedOptions(page);
    await closeAdvancedOptions(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

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

    await page.getByTestId("playground-close-button").click();

    await enableInspectPanel(page);
  },
);
