import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Custom Component Generator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByTestId("template-custom-component-generator").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="dropdown_str_model_name"]', {
      timeout: 5000,
    });

    await page.getByTestId("dropdown_str_model_name").click();

    await page.keyboard.press("Enter");

    await page.waitForTimeout(1000);

    try {
      await page.waitForSelector("anchor-popover-anchor-input-api_key", {
        timeout: 5000,
      });
      await page
        .getByTestId("anchor-popover-anchor-input-api_key")
        .locator("input")
        .last()
        .fill(process.env.ANTHROPIC_API_KEY ?? "");
    } catch (e) {
      console.log("There's API already added");
    }

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill(
        "Create a custom component that can generate a random number between 1 and 100 and is called Langflow Random Number",
      );

    await page.getByTestId("button-send").last().click();

    await page.waitForTimeout(1000);

    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "hidden", timeout: 30000 * 3 });

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(100);
    expect(await page.getByTestId("chat-code-tab").last().isVisible()).toBe(
      true,
    );
    expect(textContents.toLowerCase()).toContain("langflow");
  },
);
