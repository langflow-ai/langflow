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

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await initialGPTsetup(page);

    // Open Playground
    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("Hello, how are you?");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    await page.getByTestId("stop_building_button").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("stop_building_button").waitFor({
      state: "hidden",
      timeout: 180000,
    });

    await expect(
      page.locator('[data-testid^="chat-message-User"]').first(),
    ).toHaveText("Hello, how are you?");

    await expect(
      page.locator('[data-testid^="chat-message-AI"]').first(),
    ).not.toBeEmpty();

    // close the playground
    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await disableInspectPanel(page);
    await page.getByText("Chat Input", { exact: true }).click();
    await openAdvancedOptions(page);
    await page.getByTestId("showsender_name").click();
    await closeAdvancedOptions(page);

    await page.getByText("Chat Output", { exact: true }).click();
    await openAdvancedOptions(page);
    await page.getByTestId("showsender_name").click();
    await closeAdvancedOptions(page);

    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(0)
      .fill("TestSenderNameUser");
    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(1)
      .fill("TestSenderNameAI");

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("Are you doing ok?");

    await page.getByTestId("button-send").click();

    await page.getByTestId("stop_building_button").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("stop_building_button").waitFor({
      state: "hidden",
      timeout: 180000,
    });

    await expect(
      page.locator('[data-testid^="chat-message-TestSenderNameUser"]').first(),
    ).toHaveText("Are you doing ok?");

    await expect(
      page.locator('[data-testid^="chat-message-TestSenderNameAI"]').first(),
    ).not.toBeEmpty();

    await page.getByTestId("playground-btn-flow-io").last().click();
    await enableInspectPanel(page);
  },
);
