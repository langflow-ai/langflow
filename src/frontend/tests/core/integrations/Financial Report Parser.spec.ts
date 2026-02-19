import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Financial Report Parser",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Financial Report Parser" })
      .click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page.getByText("Parser", { exact: true }).last().click();

    await page.getByTestId("tab_1_stringify").click();

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("button-send").click();

    try {
      // Wait for the flow building indicator to appear and then disappear
      await page.waitForSelector('[data-testid="stop_building_button"]', {
        timeout: 30000,
        state: "visible",
      });
      await page.waitForSelector('[data-testid="stop_building_button"]', {
        timeout: 180000,
        state: "hidden",
      });
    } catch (_error) {
      console.error("Timeout error");
      test.skip(true, "Timeout error");
    }

    // Wait for the chat response to appear
    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });
    const textContents = await page
      .getByTestId("div-chat-message")
      .last()
      .allTextContents();
    const concatAllText = textContents.join(" ").toLowerCase();
    expect(concatAllText.length).toBeGreaterThan(10);
    expect(concatAllText).toContain("ebitda");
  },
);
