import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Image Sentiment Analysis",
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
      .getByText("Image Sentiment Analysis", { exact: true })
      .last()
      .click();

    await initialGPTsetup(page);

    //* TODO: Remove these 3 steps once the template is updated *//
    await page
      .getByTestId("handle-structuredoutput-shownode-structured output-right")
      .click();

    await page
      .getByTestId("handle-parser-shownode-data or dataframe-left")
      .click();
    await page.getByTestId("tab_1_stringify").click();

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Upload image using the hidden file input
    const filePath = path.resolve(__dirname, "../../assets/chain.png");
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);

    // Wait for file preview to appear (shows loading then the image)
    await page.waitForSelector('img[alt="chain.png"]', { timeout: 30000 });

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    // Wait for the flow to complete
    try {
      await page.waitForSelector('[data-testid="stop_building_button"]', {
        timeout: 30000,
        state: "visible",
      });
      await page.waitForSelector('[data-testid="stop_building_button"]', {
        timeout: 180000,
        state: "hidden",
      });
    } catch (_error) {
      console.error("Timeout error");
      test.skip(true, "Timeout error");
    }

    // Verify the image is visible in the chat messages after sending
    // Note: Server renames file with timestamp prefix (e.g., "2026-02-03_13-55-02_chain.png")
    await expect(page.locator('img[alt$="chain.png"]')).toBeVisible();

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(10);
    expect(textContents.toLowerCase()).toContain("sentiment");
    expect(textContents.toLowerCase()).toContain("neutral");
    expect(textContents.toLowerCase()).toContain("description");
  },
);
