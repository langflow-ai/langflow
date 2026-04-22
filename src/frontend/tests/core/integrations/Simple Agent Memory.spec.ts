import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Simple Agent Memory",
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

    // Open Simple Agent template
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Simple Agent" }).first().click();
    await initialGPTsetup(page);

    // Open Playground
    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // 1) First message: introduce the name
    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("Hi, I am John Doe.");
    await page.getByTestId("button-send").click();

    // Wait for generation to complete using stop_building_button
    await page.getByTestId("stop_building_button").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("stop_building_button").waitFor({
      state: "hidden",
      timeout: 180000,
    });

    await page.getByTestId("input-chat-playground").waitFor({
      state: "visible",
      timeout: 100000,
    });

    // 2) Second message: ask for the name in the same session
    await page.getByTestId("input-chat-playground").click();
    await page
      .getByTestId("input-chat-playground")
      .fill("Hi, what is my name?");
    await page.getByTestId("button-send").click();

    // Wait for second response to complete
    await page.getByTestId("stop_building_button").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("stop_building_button").waitFor({
      state: "hidden",
      timeout: 180000,
    });

    // Assert the assistant response mentions "John Doe"
    await page.getByTestId("div-chat-message").last().waitFor({
      state: "visible",
      timeout: 30000,
    });

    const finalText = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();
    expect(finalText.toLowerCase()).toContain("john doe");
  },
);
