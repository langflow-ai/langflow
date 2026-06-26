import { expect } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Memory Chatbot",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Memory Chatbot");
    await initialGPTsetup(page);
    await buildFlowAndWait(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page
      .getByText(TEXTS.labelNoInputMessage, { exact: true })
      .last()
      .isVisible();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Remember that I'm a lion");
    await page.getByTestId("button-send").last().click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("try reproduce the sound I made in words");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").last().click();

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");
    expect(concatAllText.length).toBeGreaterThan(20);

    // Open message logs from session sidebar menu (chat-header-more-menu is hidden in fullscreen)
    await page
      .locator('[data-testid^="session-"][data-testid$="-more-menu"]')
      .first()
      .click();
    await page.getByTestId("message-logs-option").click();

    await expect(page.getByText("timestamp", { exact: true })).toBeVisible();
    await expect(page.getByText("text", { exact: true })).toBeVisible();
    await expect(page.getByText("sender", { exact: true })).toBeVisible();
    await expect(page.getByText("sender_name", { exact: true })).toBeVisible();
    await expect(page.getByText("session_id", { exact: true })).toBeVisible();
    await expect(page.getByText("files", { exact: true })).toBeVisible();
  },
);
