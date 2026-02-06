import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import {
  closeAdvancedOptions,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

test(
  "user must be able to send an image on chat",
  { tag: ["@release", "@workspace", "@components"] },
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
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await page.getByText("Chat Input", { exact: true }).click();
    await openAdvancedOptions(page);
    await closeAdvancedOptions(page);
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

    // Verify the image is visible in the chat messages after sending
    // Note: Server renames file with timestamp prefix (e.g., "2026-02-03_13-55-02_chain.png")
    await expect(page.locator('img[alt$="chain.png"]')).toBeVisible();
  },
);
