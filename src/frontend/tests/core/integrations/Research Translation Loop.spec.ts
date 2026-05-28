import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { selectGptModel } from "../../utils/select-gpt-model";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Research Translation Loop.spec",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Research Translation Loop" })
      .click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page, {
      skipAdjustScreenView: true,
      skipSelectGptModel: true,
    });
    // TODO: Uncomment this when we have a way to test Anthropic
    // await page.getByTestId("dropdown_str_provider").click();
    // await page.getByTestId("Anthropic-1-option").click();

    await selectGptModel(page);

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("input-chat-playground").fill("This is a test");

    await page.getByTestId("button-send").click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 40000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 200000 });
    }

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000 * 3,
    });

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(140);
  },
);
