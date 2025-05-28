import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { uploadFile } from "../../utils/upload-file";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Meeting Summary",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.ASSEMBLYAI_API_KEY,
      "ASSEMBLYAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Meeting Summary" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process.env.ASSEMBLYAI_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(3)
      .fill(process.env.ASSEMBLYAI_API_KEY ?? "");

    await uploadFile(page, "test_audio_file.wav");

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");

    expect(concatAllText.length).toBeGreaterThan(50);
    expect(concatAllText).toContain("Pair");
    expect(concatAllText).toContain("beer");
    expect(concatAllText).toContain("Address");
    expect(concatAllText).toContain("Consider");
    expect(concatAllText).toContain("pickle");
    expect(concatAllText).toContain("Note");
    expect(concatAllText).toContain("Recognize");
  },
);
