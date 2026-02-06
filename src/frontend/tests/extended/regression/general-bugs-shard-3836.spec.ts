import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { uploadFile } from "../../utils/upload-file";
import {
  closeAdvancedOptions,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

test(
  "user must be able to send an image on chat using advanced tool on ChatInputComponent",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await initialGPTsetup(page);

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await page.getByText("Chat Input", { exact: true }).click();
    await openAdvancedOptions(page);
    await page.getByTestId("showfiles").click();
    await closeAdvancedOptions(page);
    const userQuestion = "What is this image?";
    await page.getByTestId("textarea_str_input_value").fill(userQuestion);

    await uploadFile(page, "chain.png");

    await page.getByTestId("button_run_chat output").click();

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    // await page.waitForSelector("text=chain.png", { timeout: 30000 });

    // expect(await page.getByAltText("generated image").isVisible()).toBeTruthy();

    await expect(page.locator('img[alt$="chain.png"]')).toBeVisible({
      timeout: 100000,
    });

    expect(
      await page.getByTestId(`chat-message-User-${userQuestion}`).isVisible(),
    ).toBeTruthy();
  },
);
