import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Portfolio Website Code Generator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );

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

    const filePath = path.join(__dirname, "../../assets/test_file.txt");
    await page.getByTestId("button_upload_file").click();

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("button_upload_file").click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(filePath);

    await page.waitForTimeout(2000);

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("button-send").click();

    await page.waitForSelector("text=DOCTYPE html", { timeout: 30000 });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(200);

    expect(concatAllText).toContain("html");
    expect(concatAllText).toContain("<body>");
    expect(concatAllText).toContain("</body>");
    expect(concatAllText).toContain("</html>");
    expect(concatAllText).toContain("responsive");
    expect(concatAllText).toContain("section");
    expect(concatAllText).toContain("header");
    expect(concatAllText).toContain("class=");
  },
);
