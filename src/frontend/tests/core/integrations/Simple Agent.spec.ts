import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Simple Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(); //@TODO understand this behavior
    test.skip(
      !process?.env?.OPENAI_API_KEY,

      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Simple Agent" }).first().click();
    await initialGPTsetup(page);

    await page.getByTestId("textarea_str_input_value").first().fill("Hello");

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForSelector("text=built successfully", {
      timeout: 10000 * 60 * 3,
    });

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    const textContents = await page.getByTestId("div-chat-message").innerText();

    expect(await page.getByTestId("header-icon").last().isVisible());
    expect(await page.getByTestId("duration-display").last().isVisible());
    expect(await page.getByTestId("icon-check").nth(0).isVisible());
    expect(await page.getByTestId("icon-Check").nth(0).isVisible());
    expect(textContents.length).toBeGreaterThan(10);
  },
);
