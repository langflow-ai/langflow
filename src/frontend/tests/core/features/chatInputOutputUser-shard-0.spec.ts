import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import {
  closeParametersPanel,
  openParametersPanel,
} from "../../utils/open-advanced-options";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "user must be able to send an image on chat",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page);

    await page.waitForSelector("text=Chat Input", { timeout: 30000 });

    await page.getByRole("application", { name: "Chat Input node" }).click();
    await openParametersPanel(page);
    await closeParametersPanel(page);
    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

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
