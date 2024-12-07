import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";

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

    await page.goto("/");

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();

    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await page.getByText("Chat Input", { exact: true }).click();
    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();
    await page.getByText("Close").last().click();

    await page.getByText("Playground", { exact: true }).last().click();

    // Read the image file as a binary string
    const filePath = "tests/assets/chain.png";
    const fileContent = readFileSync(filePath, "base64");

    // Create the DataTransfer and File objects within the browser context
    const dataTransfer = await page.evaluateHandle(
      ({ fileContent }) => {
        const dt = new DataTransfer();
        const byteCharacters = atob(fileContent);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const file = new File([byteArray], "chain.png", { type: "image/png" });
        dt.items.add(file);
        return dt;
      },
      { fileContent },
    );

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Locate the target element
    const element = await page.getByTestId("input-chat-playground");

    // Dispatch the drop event on the target element
    await element.dispatchEvent("drop", { dataTransfer });

    await page.waitForSelector("text=The file size is too large", {
      timeout: 10000,
    });

    await expect(
      page.getByText(
        `The file size is too large. Please select a file smaller than ${maxFileSizeUpload}MB`,
      ),
    ).toBeVisible();
  },
);
