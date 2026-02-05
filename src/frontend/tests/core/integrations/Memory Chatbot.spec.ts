import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Memory Chatbot",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Memory Chatbot" }).click();
    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Remember that I'm a lion");
    await page.getByTestId("button-send").last().click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("try reproduce the sound I made in words");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").last().click();

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");
    expect(concatAllText.length).toBeGreaterThan(20);

    // Open message logs from chat header menu (on default session with messages)
    await page.getByTestId("chat-header-more-menu").click();
    await page.getByTestId("message-logs-option").click();

    await expect(page.getByText("timestamp", { exact: true })).toBeVisible();
    await expect(page.getByText("text", { exact: true })).toBeVisible();
    await expect(page.getByText("sender", { exact: true })).toBeVisible();
    await expect(page.getByText("sender_name", { exact: true })).toBeVisible();
    await expect(page.getByText("session_id", { exact: true })).toBeVisible();
    await expect(page.getByText("files", { exact: true })).toBeVisible();
  },
);
