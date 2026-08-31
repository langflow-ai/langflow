import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test.describe("Token Usage Tracking", () => {
  test(
    "node badge should show token count after running an LLM flow",
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

      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();

      await page.waitForSelector('[data-testid="input-chat-playground"]', {
        timeout: 100000,
      });

      await page.getByTestId("input-chat-playground").fill("Say hi");
      await page.getByTestId("button-send").click();

      // Wait for a bot reply to appear
      await page.waitForSelector('[data-testid="div-chat-message"]', {
        timeout: 60000,
      });

      // Close the playground sliding panel
      await page.getByTestId("playground-close-button").click();

      // Any LLM node badge should display token count (matches node-token-count-*)
      const tokenBadge = page.locator('[data-testid^="node-token-count-"]');
      await expect(tokenBadge).toBeVisible({ timeout: 30000 });

      // Token count should be a non-empty number/formatted string
      const tokenText = await tokenBadge.textContent();
      expect(tokenText?.trim()).toMatch(/^\d/);
    },
  );

  test(
    "chat message should show token count alongside run duration",
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

      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();

      await page.waitForSelector('[data-testid="input-chat-playground"]', {
        timeout: 100000,
      });

      await page.getByTestId("input-chat-playground").fill("Say hi");
      await page.getByTestId("button-send").click();

      // Wait for bot message to finish streaming
      await page.waitForSelector('[data-testid="div-chat-message"]', {
        timeout: 60000,
      });

      // Token usage badge should appear in the chat message header
      await expect(page.getByTestId("chat-message-token-usage")).toBeVisible({
        timeout: 30000,
      });

      // Token count should be a non-empty number/formatted string
      const tokenText = await page
        .getByTestId("chat-message-token-usage")
        .textContent();
      expect(tokenText?.trim()).toMatch(/^\d/);

      // Run duration is shown alongside the token usage (folds in the
      // regular-playground regression that lived in shareable-playground-token-display).
      await expect(page.getByText("Finished in")).toBeVisible({
        timeout: 30000,
      });
    },
  );
});
