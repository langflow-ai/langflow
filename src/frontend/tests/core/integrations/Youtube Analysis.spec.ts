import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Youtube Analysis",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.YOUTUBE_API_KEY,
      "YOUTUBE_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Youtube Analysis" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process.env.YOUTUBE_API_KEY ?? "");

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

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
