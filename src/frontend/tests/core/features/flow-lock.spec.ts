import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

const waitForFlowSave = (page: Page) =>
  page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      /\/api\/v1\/flows\/[^/]+$/.test(new URL(response.url()).pathname),
  );

test.describe("Flow Lock Feature", () => {
  test(
    "should lock and unlock a flow and verify UI changes",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openStarterProject(page, TEXTS.templateBasicPrompting);
      await waitForFlowEditorReady(page);

      // Open flow settings by clicking on the flow name
      await page.getByTestId("flow_name").click();

      // Wait for the settings modal to open
      await page.waitForSelector('[data-testid="lock-flow-switch"]', {
        timeout: 30000,
      });

      // Verify the lock switch is initially unchecked
      const lockSwitch = page.getByTestId("lock-flow-switch");
      await expect(lockSwitch).toBeVisible();
      await expect(lockSwitch).toHaveAttribute("data-state", "unchecked");

      // Verify that name and description inputs are enabled when not locked
      const nameInput = page.getByTestId("input-flow-name");
      const descriptionInput = page.getByTestId("input-flow-description");

      await expect(nameInput).toBeEnabled();
      await expect(descriptionInput).toBeEnabled();

      await lockSwitch.click();
      await expect(lockSwitch).toHaveAttribute("data-state", "checked");

      // Verify that inputs become disabled when locked
      await expect(nameInput).toBeDisabled();
      await expect(descriptionInput).toBeDisabled();

      // Save the settings by clicking the save button
      const saveButton = page.getByTestId("save-flow-settings");

      await expect(saveButton).toBeEnabled();
      const [lockResponse] = await Promise.all([
        waitForFlowSave(page),
        saveButton.click(),
      ]);
      expect(lockResponse.ok()).toBe(true);
      await expect(saveButton).toBeHidden({
        timeout: 5000 * 3,
      });

      // Wait for the modal to close by waiting for the popover to be detached
      await page.waitForSelector('[role="dialog"]', {
        state: "detached",
        timeout: 10000,
      });

      // Try to open settings again to unlock
      await page.getByTestId("flow_name").click();

      // Wait for the settings modal to open again
      await page.waitForSelector('[data-testid="lock-flow-switch"]', {
        timeout: 30000,
      });

      // Verify the switch is checked (locked state persisted)
      await expect(lockSwitch).toHaveAttribute("data-state", "checked");

      // Verify inputs are still disabled
      await expect(nameInput).toBeDisabled();
      await expect(descriptionInput).toBeDisabled();

      // Unlock the flow
      await lockSwitch.focus();
      await lockSwitch.press("Space");

      // Verify the switch is now unchecked
      await expect(lockSwitch).toHaveAttribute("data-state", "unchecked");

      // Verify that inputs become enabled again when unlocked
      await expect(nameInput).toBeEnabled();
      await expect(descriptionInput).toBeEnabled();

      // Save the unlocked state by clicking the save button
      await expect(saveButton).toBeEnabled();
      const [unlockResponse] = await Promise.all([
        waitForFlowSave(page),
        saveButton.click(),
      ]);
      expect(unlockResponse.ok()).toBe(true);

      await expect(saveButton).toBeHidden({
        timeout: 5000,
      });

      // Wait for the modal to close by waiting for the popover to be detached
      await page.waitForSelector('[role="dialog"]', {
        state: "detached",
        timeout: 10000,
      });

      await expect(page.getByTestId("icon-Lock")).toBeHidden({
        timeout: 5000,
      });
    },
  );

  test(
    "should show correct lock/unlock icon in settings based on state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openStarterProject(page, TEXTS.templateBasicPrompting);
      await waitForFlowEditorReady(page);

      // Open flow settings
      await page.getByTestId("flow_name").click();
      await page.waitForSelector('[data-testid="lock-flow-switch"]', {
        timeout: 30000,
      });

      // Initially should show unlock icon (flow is unlocked)
      const dialog = page.locator('[role="dialog"]');
      const unlockIcon = dialog.locator('[data-testid="icon-Unlock"]');
      await expect(unlockIcon).toBeVisible();

      // Lock the flow
      const lockSwitch = dialog.getByTestId("lock-flow-switch");
      await lockSwitch.click();

      // Should now show lock icon
      const lockIcon = dialog.locator('[data-testid="icon-Lock"]');
      await expect(lockIcon).toBeVisible({ timeout: 5000 });
      await expect(unlockIcon).toBeHidden({ timeout: 5000 });
    },
  );
});
