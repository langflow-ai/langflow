import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { uploadFile } from "../../utils/upload-file";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Portfolio Website Code Generator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );
    // TODO: remove this skip once the test is stabilized
    test.skip(true, "Skipping flaky test until it can be stabilized");

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Portfolio Website Code Generator" })
      .click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page, {
      skipAdjustScreenView: true,
      skipSelectGptModel: true,
    });

    await page
      .getByTestId("popover-anchor-input-api_key")
      .last()
      .fill(process.env.ANTHROPIC_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .first()
      .fill(process.env.ANTHROPIC_API_KEY ?? "");

    await uploadFile(page, "resume.txt");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("button-send").click();

    await page.waitForSelector('[data-testid="chat-code-tab"]', {
      timeout: 30000 * 3,
    });

    await page.waitForSelector(".markdown", { timeout: 30000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(200);

    expect(concatAllText).toContain("div");
    expect(concatAllText).toContain("body");
  },
);
