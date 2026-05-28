import { expect, test } from "../../fixtures";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "News Aggregator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.AGENTQL_API_KEY,
      "AGENTQL_API_KEY required to run this test",
    );
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
    await openStarterProject(page, "News Aggregator");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page, {
      skipAdjustScreenView: true,
      skipAddOpenAiInputKey: true,
    });

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process?.env?.AGENTQL_API_KEY ?? "");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("what is langflow?");

    await page.getByTestId("button-send").click();

    await page.waitForSelector("text=Finished", { timeout: 100000 });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(100);

    expect(concatAllText).toContain("langflow");
  },
);
