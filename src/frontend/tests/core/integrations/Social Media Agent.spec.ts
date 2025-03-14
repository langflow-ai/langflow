import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Social Media Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.APIFY_API_TOKEN,
      "APIFY_API_TOKEN required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Social Media Agent" }).click();

    await initialGPTsetup(page);

    const apifyApiTokenInputCount = await page
      .getByTestId("popover-anchor-input-apify_token")
      .count();

    for (let i = 0; i < apifyApiTokenInputCount; i++) {
      await page
        .getByTestId("popover-anchor-input-apify_token")
        .nth(i)
        .fill(process.env.APIFY_API_TOKEN ?? "");
    }

    await page
      .getByTestId("popover-anchor-input-apify_token")
      .nth(apifyApiTokenInputCount - 1)
      .fill(process.env.APIFY_API_TOKEN ?? "");

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill(
        "Find the TikTok profile of the company OpenAI using Google search, then show me the profile bio and their latest video.",
      );

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    const output = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();
    expect(output).toContain("TikTok");
    expect(output.length).toBeGreaterThan(300);
  },
);
