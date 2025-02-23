import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Research Translation Loop.spec",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Research Translation Loop" })
      .click();

    try {
      await page
        .getByTestId("anchor-popover-anchor-input-api_key")
        .last()
        .fill(process.env.ANTHROPIC_API_KEY ?? "");
    } catch (e) {
      console.log("There's API already added");
    }

    await page.waitForSelector('[data-testid="dropdown_str_model_name"]', {
      timeout: 5000,
    });

    await page.getByTestId("dropdown_str_model_name").click();

    await page.keyboard.press("Enter");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.getByTestId("input-chat-playground").fill("This is a test");

    await page.getByTestId("button-send").click();

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(300);
  },
);
