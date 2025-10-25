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

    // 1) First message: introduce the name
    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Hi, I am John Doe.");
    await page.getByTestId("button-send").last().click();

    // Wait for generation to complete
    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    // 2) Second message: ask for the name in the same session
    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Hi, what is my name?");
    await page.getByTestId("button-send").last().click();

    // Wait for second response to complete
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    // Assert the assistant response mentions "John Doe"
    const finalText = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();
    expect(finalText.toLowerCase()).toContain("john doe");
  },
);
