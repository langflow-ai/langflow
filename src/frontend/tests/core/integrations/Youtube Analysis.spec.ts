import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "YouTube Analysis",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    test.skip(
      !process?.env?.YOUTUBE_API_KEY,
      "YOUTUBE_API_KEY required to run this test",
    );
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
    await openStarterProject(page, "YouTube Analysis");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process.env.YOUTUBE_API_KEY ?? "");

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 120000,
    });

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.waitForSelector("text=Finished", { timeout: 10000 });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");

    expect(concatAllText.length).toBeGreaterThan(200);
    expect(concatAllText).toContain("Recommendations");
    expect(concatAllText).toContain("Synthesis");
    expect(concatAllText).toContain("Audience Reception");
    expect(concatAllText).toContain("Content Summary");
  },
);
