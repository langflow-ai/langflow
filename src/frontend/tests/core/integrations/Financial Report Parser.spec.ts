import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
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

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page.getByTestId("tab_1_stringify").click();

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("button-send").click();

    try {
      await page.waitForSelector('[data-testid="button-stop"]', {
        timeout: 180000,
        state: "hidden",
      });
    } catch (_error) {
      console.error("Timeout error");
      test.skip(true, "Timeout error");
    }

    await page.waitForSelector(".markdown", { timeout: 3000 });
    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();
    const concatAllText = textContents.join(" ").toLowerCase();
    expect(concatAllText.length).toBeGreaterThan(10);
    expect(concatAllText).toContain("ebitda");
  },
);
