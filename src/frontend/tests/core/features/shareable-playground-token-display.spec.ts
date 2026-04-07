import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "shareable playground: bot messages display token usage",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
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

    // Build first
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 120000 });

    // Publish
    await page.getByTestId("publish-button").click();
    await page.waitForSelector('[data-testid="shareable-playground"]', {
      timeout: 10000,
    });
    await page.waitForTimeout(1000);
    await page.getByTestId("publish-switch").click();
    await page.waitForTimeout(2000);

    const pagePromise = context.waitForEvent("page");
    await page.getByTestId("shareable-playground").click();
    const newPage = await pagePromise;
    await newPage.waitForTimeout(3000);

    // Send message
    await newPage.getByPlaceholder("Send a message...").fill("Say hi");
    await newPage.getByTestId("button-send").last().click();

    // Wait for build to complete (Stop button lifecycle)
    const stopButton = newPage.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    await stopButton.waitFor({ state: "hidden", timeout: 120000 });

    // Wait for UI to settle
    await newPage.waitForTimeout(3000);

    // Token count should be visible (Coins icon indicates token display)
    const coinsIcons = await newPage
      .locator('[data-testid="icon-Coins"]')
      .count();
    expect(coinsIcons).toBeGreaterThan(0);

    await newPage.close();
  },
);

test(
  "regular playground: Finished In with token display still works (regression)",
  { tag: ["@release", "@workspace", "@api"] },
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
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await initialGPTsetup(page);

    // Build
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 120000 });

    // Open regular playground
    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 10000,
    });

    // Send message
    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("Say hello briefly");
    await page.keyboard.press("Enter");

    // Wait for AI response
    await page.waitForFunction(
      () =>
        document.querySelectorAll('[data-testid="div-chat-message"]').length >=
        2,
      { timeout: 120000 },
    );

    // "Finished in" should appear (regular playground specific)
    await expect(page.getByText("Finished in")).toBeVisible({
      timeout: 30000,
    });
  },
);
