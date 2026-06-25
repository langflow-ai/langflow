import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { TEXTS } from "../../utils/constants/texts";

const waitForNotificationFlowEditor = async (page: Page) => {
  const welcomeBackdrop = page.getByTestId("flow-builder-welcome-backdrop");
  const welcomeBackdropVisible = await welcomeBackdrop
    .waitFor({ state: "visible", timeout: 5000 })
    .then(() => true)
    .catch(() => false);

  if (welcomeBackdropVisible) {
    await page.getByTestId("flow-builder-welcome-faux-rail-components").click();
  }

  await expect(page.getByTestId("sidebar-search-input")).toBeVisible({
    timeout: 30000,
  });

  await expect(page.getByTestId("sidebar-options-trigger")).toBeVisible({
    timeout: 30000,
  });
};

const openFlowForNotifications = async (page: Page) => {
  await page.goto("/flows");

  const editorVisible = await page
    .getByTestId("sidebar-search-input")
    .waitFor({ state: "visible", timeout: 5000 })
    .then(() => true)
    .catch(() => false);

  if (editorVisible) {
    await waitForNotificationFlowEditor(page);
    return;
  }

  const firstFlowCard = page.getByTestId("list-card").first();
  const hasFlowCard = await firstFlowCard
    .waitFor({ state: "visible", timeout: 5000 })
    .then(() => true)
    .catch(() => false);

  if (hasFlowCard) {
    await firstFlowCard.click();
  } else {
    await page.getByTestId("new_project_btn_empty_page").click();
  }

  await waitForNotificationFlowEditor(page);
};

test(
  "User should be able to interact notifications tab",
  { tag: ["@release"] },
  async ({ page }) => {
    await openFlowForNotifications(page);

    await addLegacyComponents(page);

    await page.waitForSelector('[data-testid="disclosure-input & output"]', {
      timeout: 30000,
      state: "visible",
    });

    await page.getByTestId("disclosure-input & output").click();
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 30000,
      state: "visible",
    });
    await page
      .getByTestId("input_outputText Input")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-text-input").click();
        await page.getByTestId("button_run_text input").click();
      });

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });
    await page.getByTestId("notification_button").click();

    // Add explicit waits before checking visibility
    await page.waitForSelector('[data-testid="icon-Trash2"]', {
      timeout: 30000,
      state: "visible",
    });

    // Then check visibility
    const notificationsText = page
      .getByText("Notifications", { exact: true })
      .last();
    await expect(notificationsText).toBeVisible();

    const trashIcon = page.getByTestId("icon-Trash2").last();
    await expect(trashIcon).toBeVisible();

    const builtSuccessfullyText = page
      .getByText("Flow built successfully", { exact: true })
      .last();
    await expect(builtSuccessfullyText).toBeVisible();
  },
);
