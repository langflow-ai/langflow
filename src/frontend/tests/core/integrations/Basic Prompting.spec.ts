import { expect } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Basic Prompting (Hello, World)",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Basic Prompting");

    await initialGPTsetup(page);
    await buildFlowAndWait(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByText(TEXTS.labelNoInputMessage, { exact: true })
      .last()
      .isVisible();

    //create a new session - default session can not be deleted
    await page.getByTestId("new-chat").click();
    await expect(page.getByTitle("New Session 0")).toBeVisible();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Say hello as a pirate");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").last().click();

    await page.waitForSelector("text=matey", {
      timeout: 100000,
    });

    await expect(page.getByText("matey").last()).toBeVisible();

    // Open the message logs table view to verify metadata columns
    // (timestamp/text/sender/...). The header chat-menu is hidden in
    // fullscreen, so click the sidebar session more-menu instead.
    await page
      .locator('[data-testid^="session-"][data-testid$="-more-menu"]')
      .last()
      .click();
    await page.getByTestId("message-logs-option").click();

    await expect(
      page.getByText("timestamp", { exact: true }).last(),
    ).toBeVisible();
    await expect(page.getByText("text", { exact: true }).last()).toBeVisible();
    await expect(
      page.getByText("sender", { exact: true }).last(),
    ).toBeVisible();
    await expect(
      page.getByText("sender_name", { exact: true }).last(),
    ).toBeVisible();
    await expect(
      page.getByText("session_id", { exact: true }).last(),
    ).toBeVisible();
    await expect(page.getByText("files", { exact: true }).last()).toBeVisible();
    await expect(page.getByRole("gridcell").last()).toBeVisible();

    // Close the logs panel so the rest of the playground UI is reachable again.
    await page.getByRole("button", { name: TEXTS.close }).click();
    // Use sidebar session more menu (chat-header-more-menu is hidden in fullscreen)
    await page
      .locator('[data-testid^="session-"][data-testid$="-more-menu"]')
      .last()
      .click();
    await page.getByTestId("delete-session-option").click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await expect(
      page.getByTestId("input-chat-playground").last(),
    ).toBeVisible();
  },
);
