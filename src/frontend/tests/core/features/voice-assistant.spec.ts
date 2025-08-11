import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should able to see and interact with voice assistant",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.getByTestId("playground-btn-flow-io").click();

    await expect(page.getByTestId("voice-button")).toBeVisible();

    await page.getByTestId("voice-button").click();

    try {
      const apiKeyInput = page.getByTestId("popover-anchor-openai-api-key");

      const isVisible = await apiKeyInput
        .isVisible({ timeout: 2000 })
        .catch(() => false);

      if (isVisible) {
        await apiKeyInput.fill(process.env.OPENAI_API_KEY || "");
        await page
          .getByTestId("voice-assistant-settings-modal-save-button")
          .click();
      }
    } catch (e) {
      console.error(e);
    }

    await expect(page.getByTestId("voice-assistant-container")).toBeVisible();
    await page.getByTestId("voice-assistant-settings-icon").click();
    await expect(
      page.getByTestId("voice-assistant-settings-modal-microphone-select"),
    ).toBeVisible();
    await expect(
      page.getByTestId("voice-assistant-settings-modal-header"),
    ).toBeVisible();

    await page.keyboard.press("Escape");

    await page.getByTestId("voice-assistant-close-button").click();

    await expect(
      page.getByTestId("voice-assistant-settings-modal-microphone-select"),
    ).not.toBeVisible();

    await expect(page.getByTestId("input-wrapper")).toBeVisible();
  },
);
