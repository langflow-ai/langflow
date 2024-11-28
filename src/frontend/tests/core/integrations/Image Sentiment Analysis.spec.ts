import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";

test(
  "Image Sentiment Analysis",
  { tag: ["@release", "@starter-project"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

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
    await page
      .getByText("Image Sentiment Analysis", { exact: true })
      .last()
      .click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();

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

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Read the image file as a binary string
    const filePath = "src/frontend/tests/assets/chain.png";
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

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    await page.waitForSelector("text=chain.png", { timeout: 30000 });

    await page.getByText("chain.png").isVisible();

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ");
    expect(concatAllText.length).toBeGreaterThan(10);
    expect(concatAllText.toLowerCase()).toContain("sentiment");
    expect(concatAllText.toLowerCase()).toContain("neutral");
    expect(concatAllText.toLowerCase()).toContain("description");
  },
);
