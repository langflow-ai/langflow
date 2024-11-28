import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "Custom Component Generator",
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
    await page.getByTestId("template-custom-component-generator").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }

    await page.getByText("Anthropic", { exact: true }).last().click();
    await page.keyboard.press("Delete");

    await page.getByTestId("sidebar-search-input").fill("OpenAI");

    await page
      .getByTestId("modelsOpenAI")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-openai").click();
      });

    await page
      .getByTestId("handle-prompt-shownode-prompt message-right")
      .first()
      .click();
    await page
      .getByTestId("handle-openaimodel-shownode-input-left")
      .first()
      .click();

    await page
      .getByTestId("handle-openaimodel-shownode-text-right")
      .first()
      .click();

    await page
      .getByTestId("handle-chatoutput-shownode-text-left")
      .first()
      .click();

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

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ");
    expect(concatAllText.length).toBeGreaterThan(100);
    expect(await page.getByTestId("chat-code-tab").isVisible()).toBe(true);
    expect(concatAllText.toLowerCase()).toContain("langflow");
  },
);
