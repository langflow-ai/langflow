import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "user must interact with chat with Input/Output",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
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

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").fill("Hello, how are you?");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();
    let valueUser = await page.getByTestId("sender_name_user").textContent();

    await page.waitForSelector('[data-testid="sender_name_ai"]', {
      timeout: 100000,
    });

    let valueAI = await page.getByTestId("sender_name_ai").textContent();

    expect(valueUser).toBe("User");
    expect(valueAI).toContain("AI");

    await page.keyboard.press("Escape");

    await page
      .getByTestId("textarea_str_input_value")
      .nth(0)
      .fill(
        "testtesttesttesttesttestte;.;.,;,.;,.;.,;,..,;;;;;;;;;;;;;;;;;;;;;,;.;,.;,.,;.,;.;.,~~çççççççççççççççççççççççççççççççççççççççisdajfdasiopjfaodisjhvoicxjiovjcxizopjviopasjioasfhjaiohf23432432432423423sttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttestççççççççççççççççççççççççççççççççç,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,!",
      );
    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();
    await page.getByText("Close", { exact: true }).click();
    await page.getByText("Chat Input", { exact: true }).click();
    await page.getByTestId("edit-button-modal").click();
    await page.getByTestId("showsender_name").click();
    await page.getByText("Close").last().click();

    await page.getByText("Chat Output", { exact: true }).click();
    await page.getByTestId("edit-button-modal").click();
    await page.getByTestId("showsender_name").click();
    await page.getByText("Close").last().click();

    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(1)
      .fill("TestSenderNameUser");
    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(0)
      .fill("TestSenderNameAI");

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    valueUser = await page
      .getByTestId("sender_name_testsendernameuser")
      .textContent();
    valueAI = await page
      .getByTestId("sender_name_testsendernameai")
      .textContent();

    expect(valueUser).toContain("TestSenderNameUser");
    expect(valueAI).toContain("TestSenderNameAI");

    expect(
      await page
        .getByText(
          "testtesttesttesttesttestte;.;.,;,.;,.;.,;,..,;;;;;;;;;;;;;;;;;;;;;,;.;,.;,.,;.,;.;.,~~çççççççççççççççççççççççççççççççççççççççisdajfdasiopjfaodisjhvoicxjiovjcxizopjviopasjioasfhjaiohf23432432432423423sttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttestççççççççççççççççççççççççççççççççç,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,!",
          { exact: true },
        )
        .isVisible(),
    );
  },
);
