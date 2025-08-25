import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Flow Lock Feature", () => {
  test(
    "should lock and unlock a flow and verify UI changes",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Navigate to templates and select a flow to work with
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();

      // Wait for the flow to load
      await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
        timeout: 100000,
      });

      // Verify initially the flow is not locked (no lock icon should be visible)
      const initialLockIcon = page.locator(
        '[data-testid="menu_bar_display"] [data-testid="icon-Lock"]',
      );
      await expect(initialLockIcon).toHaveCount(0);

      // Open flow settings by clicking on the flow name
      await page.getByTestId("menu_bar_display").click();

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
      await page.waitForTimeout(1000);

      const stateAfterClick = await lockSwitch.getAttribute("data-state");
      if (stateAfterClick !== "checked") {
        await lockSwitch.click();
        await page.waitForTimeout(500);
      }
      await expect(lockSwitch).toHaveAttribute("data-state", "checked");

      // Verify that inputs become disabled when locked
      await expect(nameInput).toBeDisabled();
      await expect(descriptionInput).toBeDisabled();

      // Save the settings by clicking the save button
      const saveButton = page.getByTestId("save-flow-settings");

      if (await saveButton.isEnabled({ timeout: 3000 })) {
        await saveButton.click();
      }
      await page.waitForTimeout(1000);

      // Wait for the modal to close by waiting for the popover to be detached
      await page.waitForSelector('[role="dialog"]', {
        state: "detached",
        timeout: 10000,
      });

      // Verify lock icon now appears in the flow header
      const lockIconInHeader = page
        .locator('[data-testid="menu_bar_display"]')
        .locator('[data-testid="icon-Lock"]');
      await expect(lockIconInHeader).toBeVisible();

      // Try to open settings again to unlock
      await page.getByTestId("menu_bar_display").click();

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
      await page.getByTestId("save-flow-settings").isEnabled({ timeout: 3000 });
      await page.getByTestId("save-flow-settings").click();

      // Wait for the modal to close by waiting for the popover to be detached
      await page.waitForSelector('[role="dialog"]', {
        state: "detached",
        timeout: 10000,
      });

      // Verify lock icon is no longer visible in the flow header
      await expect(lockIconInHeader).toHaveCount(0);
    },
  );

  test(
    "should show correct lock/unlock icon in settings based on state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Navigate to templates and select a flow
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();

      // Wait for the flow to load
      await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
        timeout: 100000,
      });

      // Open flow settings
      await page.getByTestId("menu_bar_display").click();
      await page.waitForSelector('[data-testid="lock-flow-switch"]', {
        timeout: 30000,
      });

      // Initially should show unlock icon (flow is unlocked)
      const unlockIcon = page.locator('[data-testid="icon-Unlock"]');
      await expect(unlockIcon).toBeVisible();

      // Lock the flow
      const lockSwitch = page.getByTestId("lock-flow-switch");
      await lockSwitch.click();

      // Should now show lock icon
      const lockIcon = page.locator('[data-testid="icon-Lock"]');
      await expect(lockIcon).toBeVisible();
      await expect(unlockIcon).toHaveCount(0);
    },
  );
});
