import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
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
    await page.getByRole("heading", { name: "News Aggregator" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page, {
      skipAdjustScreenView: true,
      skipAddNewApiKeys: true,
      skipSelectGptModel: true,
    });

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process?.env?.AGENTQL_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(1)
      .fill(process?.env?.OPENAI_API_KEY ?? "");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("input-chat-playground").fill("what is langflow?");

    await page.getByTestId("button-send").click();

    await page.waitForSelector("text=Finished", { timeout: 10000 });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");

    expect(concatAllText.length).toBeGreaterThan(100);

    expect(concatAllText).toContain("Langflow");
    expect(concatAllText).toContain("open-source");
    expect(concatAllText).toContain("framework");
  },
);
