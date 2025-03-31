import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

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
    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();
    await page.getByTestId("showfiles").click();
    await page.getByText("Close").last().click();

    const userQuestion = "What is this image?";
    await page.getByTestId("textarea_str_input_value").fill(userQuestion);

    const filePath = "tests/assets/chain.png";

    await page.click('[data-testid="button_upload_file"]');

    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      page.click('[data-testid="button_upload_file"]'),
    ]);

    await fileChooser.setFiles(filePath);

    await page.keyboard.press("Escape");

    await page.getByTestId("button_run_chat output").click();
    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.waitForSelector("text=chain.png", { timeout: 30000 });

    expect(await page.getByAltText("generated image").isVisible()).toBeTruthy();

    expect(
      await page.getByTestId(`chat-message-User-${userQuestion}`).isVisible(),
    ).toBeTruthy();

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    expect(textContents[0]).toContain("chain");
  },
);
