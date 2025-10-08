import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Gmail Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.COMPOSIO_API_KEY,
      "COMPOSIO_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Gmail Agent" }).click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("canvas_controls_dropdown").click();

    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .last()
      .fill(process.env.COMPOSIO_API_KEY ?? "");

    await page.getByTestId("refresh-button-app_names").last().click();

    await page.waitForSelector(
      '[data-testid="popover-anchor-input-auth_status"]',
      {
        timeout: 30000,
        state: "visible",
      },
    );

    const authStatus = await page
      .getByTestId("popover-anchor-input-auth_status")
      .last()
      .inputValue();

    await page.waitForTimeout(500);

    expect(authStatus).toBe("✅");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input-chat-playground")
      .fill("Send an email to johndoe@test.com wishing him a happy birthday!");

    await page.getByTestId("button-send").click();

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 3000,
    });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");

    expect(concatAllText).toContain("email");
    expect(concatAllText).toContain("successfully");
  },
);
